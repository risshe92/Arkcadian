"""
Loudness.

- ReplayGain 2.0 track gain and sample peak (rsgain, scan only).
  rsgain only ever scans a temporary copy, so it can never change a real file.
- Integrated loudness (LUFS) and loudness range (LRA, LU), measured
  directly with FFmpeg's EBU R128 filter in one pass. Read-only.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from common import TrackError, Timer, debugger, run, sha256

STEP = "loudness"
D = debugger(STEP)

# ReplayGain 2.0 reference loudness (rsgain default target)
REFERENCE_LUFS = -18.0

# EBU R128
SILENT_LUFS = -70.0          # FFmpeg's floor: integrated loudness at or below this = unmeasurable
LRA_MIN_DURATION_S = 10.0    # LRA needs several 3 s windows; shorter audio gives no LRA
SUMMARY_TOLERANCE = 0.06     # frame value and summary (1 decimal) must agree within this


def ebur128(path: Path, duration: float) -> tuple[float | None, float | None, list[str]]:
    """Integrated loudness (LUFS) and loudness range (LU) of the whole file, one pass.

    Values come from FFmpeg's per-frame metadata (3 decimals, the most precise
    output FFmpeg gives). The final frame holds the values for the whole file.
    The printed summary (1 decimal) is used as a cross-check.
    Returns (lufs, lra, warnings). None = unmeasurable.
    """
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-nostats", "-i", str(path), "-map", "0:a:0",
           "-af", "ebur128=metadata=1:framelog=quiet,ametadata=mode=print:file=-", "-f", "null", "-"]
    with Timer(D, "EBU R128 scan"):
        proc = run(cmd, None)
    D(3, "command: " + " ".join(cmd))
    D(4, lambda: "summary:\n" + (proc.stderr[proc.stderr.rfind("Summary:"):].strip() or "(none)"))
    if proc.returncode != 0:
        raise TrackError(f"ffmpeg ebur128 failed: {proc.stderr.strip()[-300:]}")

    frame_i = re.findall(r"lavfi\.r128\.I=(-?[\d.]+|-?inf|nan)", proc.stdout)
    frame_lra = re.findall(r"lavfi\.r128\.LRA=(-?[\d.]+|-?inf|nan)", proc.stdout)
    summary = proc.stderr[proc.stderr.rfind("Summary:"):]
    sum_i = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    sum_lra = re.search(r"LRA:\s+(-?[\d.]+) LU", summary)
    if not frame_i or not frame_lra:
        raise TrackError("ffmpeg ebur128 gave no loudness values")
    lufs, lra = float(frame_i[-1]), float(frame_lra[-1])
    D(2, f"frame values: I {frame_i[-1]} LUFS, LRA {frame_lra[-1]} LU; "
         f"summary: I {sum_i.group(1) if sum_i else '?'} LUFS, LRA {sum_lra.group(1) if sum_lra else '?'} LU")

    warnings = []
    for name, value, check in (("integrated loudness", lufs, sum_i), ("loudness range", lra, sum_lra)):
        if check and abs(value - float(check.group(1))) > SUMMARY_TOLERANCE:
            warnings.append(f"{name}: frame value {value} and summary {check.group(1)} disagree")

    if not lufs == lufs or lufs in (float("inf"), float("-inf")) or lufs <= SILENT_LUFS:
        warnings.append(f"integrated loudness unmeasurable ({frame_i[-1]} LUFS), not written")
        lufs = lra = None
    elif duration < LRA_MIN_DURATION_S:
        warnings.append(f"loudness range unreliable for {duration:.1f}s of audio, not written")
        lra = None
    elif not lra == lra or lra < 0:
        warnings.append(f"loudness range invalid ({frame_lra[-1]}), not written")
        lra = None
    D(1, f"integrated loudness {lufs} LUFS, loudness range {lra} LU")
    return lufs, lra, warnings


def replaygain(path: Path) -> tuple[float, float]:
    """Returns (track gain in dB, track sample peak)."""
    # rsgain does not accept .aif, so the copy is named .aiff
    ext = ".aiff" if path.suffix.lower() in (".aif", ".aiff") else path.suffix.lower()
    with tempfile.TemporaryDirectory() as td:
        scan = Path(td) / f"scan{ext}"
        shutil.copy2(path, scan)
        before = sha256(scan)
        with Timer(D, "rsgain scan"):
            proc = run(["rsgain", "custom", "-s", "s", "-O", "-q", str(scan)], D)
        if sha256(scan) != before:
            raise TrackError("rsgain changed the scanned file. Check the rsgain command before continuing.")
        D(3, "scanned copy unchanged (sha256 match)")

    if proc.returncode != 0:
        raise TrackError(f"rsgain failed: {proc.stderr.strip()[-300:]}")
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        if ln.startswith("Filename\t") and i + 1 < len(lines):
            cols = lines[i + 1].split("\t")
            D(4, f"rsgain columns: {cols}")
            try:
                gain, peak = float(cols[2]), float(cols[3])
            except (IndexError, ValueError):
                break
            D(2, f"loudness {cols[1]} LUFS")
            D(1, f"gain {gain:.2f} dB, peak {peak:.6f}")
            return gain, peak
    raise TrackError(f"rsgain output not understood: {proc.stdout.strip()[-300:]}")


def lufs_from_gain(gain: float) -> float:
    return REFERENCE_LUFS - gain

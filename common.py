"""
Shared helpers used by every module.

- Step list
- Errors
- Per-step debug output (levels 1-5)
- Running external commands
- GPU device selection
- The Result record for one track
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable

# Step names, in processing order
STEPS = ["silence", "tempo", "beatgrid", "key", "loudness",
         "features", "vocals", "lowend", "bassline", "structure", "energy"]

log = logging.getLogger("dj")


class TrackError(Exception):
    """A problem with one track. Processing continues with the next track."""


class SkipTrack(Exception):
    """The track is skipped on purpose (e.g. already analysed)."""


# ---------------------------------------------------------------------------
# Debug levels
#   1  step start/end and its result
#   2  + settings and intermediate values
#   3  + timings and external commands
#   4  + raw tool output and data summaries
#   5  + full data (every beat, every interval, all probabilities)
# ---------------------------------------------------------------------------

_levels: dict[str, int] = {}


def set_debug_levels(levels: dict[str, int]) -> None:
    _levels.clear()
    _levels.update(levels)


def debug_level(step: str) -> int:
    return _levels.get(step, 0)


def debugger(step: str) -> Callable[..., None]:
    """Returns D(level, message) for one step.

    message can be a string or a function returning a string. A function is
    only called when that level is active, so expensive output costs nothing
    when debugging is off.
    """
    def D(level: int, message) -> None:
        if debug_level(step) >= level:
            text = message() if callable(message) else message
            for line in str(text).splitlines() or [""]:
                log.info(f"  [{step}:D{level}] {line}")
    return D


class Timer:
    """with Timer(D, "label"): ...  logs the time taken at debug level 3."""

    def __init__(self, D: Callable[..., None], label: str) -> None:
        self.D, self.label = D, label

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc) -> None:
        self.D(3, f"{self.label}: {time.perf_counter() - self.t0:.2f}s")


# ---------------------------------------------------------------------------
# External commands and files
# ---------------------------------------------------------------------------


def run(cmd: list[str], D: Callable[..., None] | None = None) -> subprocess.CompletedProcess:
    if D:
        D(3, "command: " + " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if D:
        D(3, f"exit code: {proc.returncode}")
        D(4, lambda: "stdout:\n" + (proc.stdout.strip() or "(empty)"))
        D(4, lambda: "stderr:\n" + (proc.stderr.strip() or "(empty)"))
    return proc


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# GPU
# ---------------------------------------------------------------------------

_device: str | None = None


def device() -> str:
    """cuda if available, else cpu. Checked once."""
    global _device
    if _device is None:
        import torch
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        log.info(f"AI device: {_device}")
    return _device


def free_gpu() -> None:
    if _device == "cuda":
        import torch
        torch.cuda.empty_cache()


def gpu_memory() -> str:
    if _device != "cuda":
        return "cpu"
    import torch
    used = torch.cuda.memory_allocated() / 2**20
    peak = torch.cuda.max_memory_allocated() / 2**20
    return f"GPU memory {used:.0f} MB, peak {peak:.0f} MB"


# ---------------------------------------------------------------------------
# Beat maths (used by tempo.py and beatgrid.py)
# ---------------------------------------------------------------------------

FIT_TOLERANCE = 0.08       # intervals within 8% of the expected interval count as steady
FIT_MIN_RUN = 8            # a steady run needs at least this many intervals


def fit_bpm(beats, reference: float | None = None) -> tuple[float, float]:
    """Precise tempo from steady runs of beats.

    Beat This! places beats on a 0.02 s grid, so single intervals are stepped
    (e.g. 0.46 s = 130.43 BPM). Over a long steady run the steps cancel out:
    tempo = beats in run / time the run takes.

    reference: expected beat interval in seconds. Default: median interval.
    Returns (bpm, share of intervals used).
    """
    import numpy as np
    b = np.asarray(beats, dtype=float)
    iv = np.diff(b)
    if iv.size == 0:
        return 0.0, 0.0
    period = reference if reference else float(np.median(iv))
    ok = np.abs(iv / period - 1) <= FIT_TOLERANCE

    beats_used, time_used = 0, 0.0
    i = 0
    while i < iv.size:
        if not ok[i]:
            i += 1
            continue
        j = i
        while j < iv.size and ok[j]:
            j += 1
        if j - i >= FIT_MIN_RUN:
            beats_used += j - i
            time_used += b[j] - b[i]
        i = j

    if beats_used == 0:
        inliers = iv[ok]
        if inliers.size:
            return 60.0 / float(inliers.mean()), float(inliers.size / iv.size)
        return 60.0 / period, 0.0
    return 60.0 * beats_used / time_used, beats_used / iv.size


# ---------------------------------------------------------------------------
# Result for one track (all times on the timeline of the analysed file)
# ---------------------------------------------------------------------------


@dataclass
class Result:
    duration: float = 0.0
    silence_found: bool | None = None
    music_start: float = 0.0
    music_end: float = 0.0
    trimmed: bool = False
    bpm_exact: float | None = None
    first_downbeat: float | None = None
    tempo_changes: list[tuple[float, float]] | None = None
    key: str | None = None
    rg_gain: float | None = None
    rg_peak: float | None = None
    brightness: float | None = None
    onset_density: float | None = None
    vocal_density: float | None = None
    intro_length: float | None = None
    outro_length: float | None = None
    energy: float | None = None
    # Loudness, low end and bassline
    integrated_loudness: float | None = None     # LUFS, FFmpeg EBU R128
    loudness_range: float | None = None          # LU, FFmpeg EBU R128
    low_end_onset_density: float | None = None   # attacks per second
    low_end_occupancy: float | None = None       # 0-1
    low_end_energy_ratio: float | None = None    # 0-1
    low_end_activity: float | None = None        # 0-1 composite
    bassline_onset_density: float | None = None  # attacks per second
    bassline_occupancy: float | None = None      # 0-1
    bassline_activity: float | None = None       # 0-1 composite
    warnings: list[str] = field(default_factory=list)

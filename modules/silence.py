"""
Silence detection and trimming (FFmpeg).
"""

from __future__ import annotations

import re
from pathlib import Path

from common import TrackError, Timer, debugger, run

STEP = "silence"
D = debugger(STEP)

# Settings
DEFAULT_THRESHOLD_DB = -60.0
MIN_DURATION_S = 0.1     # shorter quiet parts are not counted as silence
EDGE_S = 0.05            # silence within this distance of a file edge touches the edge
MIN_MUSIC_S = 1.0        # less music than this is an error

PCM_CODECS = {
    (".aif", "PCM_16"): "pcm_s16be", (".aif", "PCM_24"): "pcm_s24be",
    (".aif", "PCM_32"): "pcm_s32be", (".aif", "FLOAT"): "pcm_f32be",
    (".aiff", "PCM_16"): "pcm_s16be", (".aiff", "PCM_24"): "pcm_s24be",
    (".aiff", "PCM_32"): "pcm_s32be", (".aiff", "FLOAT"): "pcm_f32be",
    (".wav", "PCM_16"): "pcm_s16le", (".wav", "PCM_24"): "pcm_s24le",
    (".wav", "PCM_32"): "pcm_s32le", (".wav", "FLOAT"): "pcm_f32le",
}
MUXERS = {".flac": "flac", ".aif": "aiff", ".aiff": "aiff", ".wav": "wav"}


def detect(path: Path, duration: float, threshold_db: float) -> tuple[bool, float, float]:
    """Returns (silence_found, music_start, music_end) in seconds."""
    D(2, f"threshold {threshold_db} dB, min duration {MIN_DURATION_S}s, file duration {duration:.3f}s")
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-nostats", "-i", str(path),
           "-af", f"silencedetect=noise={threshold_db}dB:d={MIN_DURATION_S}",
           "-f", "null", "-"]
    with Timer(D, "silencedetect"):
        proc = run(cmd, D)
    if proc.returncode != 0:
        raise TrackError(f"ffmpeg silencedetect failed: {proc.stderr.strip()[-300:]}")

    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", proc.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", proc.stderr)]
    D(4, f"{len(starts)} silent part(s) found")
    D(5, lambda: "\n".join(
        f"silence {s:.3f}s -> {ends[i]:.3f}s" if i < len(ends) else f"silence {s:.3f}s -> end"
        for i, s in enumerate(starts)) or "none")

    music_start, music_end = 0.0, duration
    found = False

    if starts and starts[0] <= EDGE_S:
        if not ends:
            raise TrackError("track is silent from start to end")
        music_start = ends[0]
        found = True
        D(2, f"leading silence: 0.000s -> {music_start:.3f}s")

    if starts:
        last_start = starts[-1]
        last_has_end = len(ends) == len(starts)
        if (not last_has_end or ends[-1] >= duration - EDGE_S) and last_start > music_start:
            music_end = last_start
            found = True
            D(2, f"trailing silence: {music_end:.3f}s -> {duration:.3f}s")

    if music_end - music_start <= MIN_MUSIC_S:
        raise TrackError(f"less than {MIN_MUSIC_S}s of music after silence detection")
    D(1, f"found={found} music {music_start:.3f}s -> {music_end:.3f}s")
    return found, music_start, music_end


def trim(src: Path, dst: Path, start: float, end: float) -> None:
    """Sample-accurate trim. Same format, sample rate, channels and bit depth. No metadata."""
    import soundfile as sf
    info = sf.info(str(src))
    sr = info.samplerate
    s, e = int(round(start * sr)), int(round(end * sr))
    ext = src.suffix.lower()
    D(2, f"trim samples {s} -> {e} ({info.subtype}, {sr} Hz, {info.channels} ch)")

    if ext == ".flac":
        codec_args = ["-c:a", "flac"]
        if info.subtype == "PCM_24":
            codec_args += ["-bits_per_raw_sample", "24"]
    else:
        codec = PCM_CODECS.get((ext, info.subtype))
        if codec is None:
            raise TrackError(f"trim: unsupported sample format {info.subtype}")
        codec_args = ["-c:a", codec]

    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
           "-i", str(src), "-map", "0:a:0", "-map_metadata", "-1",
           "-af", f"atrim=start_sample={s}:end_sample={e},asetpts=PTS-STARTPTS",
           *codec_args, "-fflags", "+bitexact", "-flags:a", "+bitexact",
           "-f", MUXERS[ext], str(dst)]
    with Timer(D, "trim"):
        proc = run(cmd, D)
    if proc.returncode != 0:
        raise TrackError(f"ffmpeg trim failed: {proc.stderr.strip()[-300:]}")

    out = sf.info(str(dst))
    D(4, f"trimmed file: {out.frames} samples, {out.subtype}, {out.samplerate} Hz, {out.channels} ch")
    problems = []
    if out.samplerate != info.samplerate:
        problems.append("sample rate")
    if out.channels != info.channels:
        problems.append("channels")
    if out.subtype != info.subtype:
        problems.append(f"bit depth ({info.subtype} -> {out.subtype})")
    if abs(out.frames - (e - s)) > 1:
        problems.append(f"length ({out.frames} samples, expected {e - s})")
    if problems:
        raise TrackError(f"trim check failed: {', '.join(problems)}")
    D(1, f"trimmed {start:.3f}s from the start, {info.frames / sr - end:.3f}s from the end")

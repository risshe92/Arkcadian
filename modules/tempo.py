"""
Tempo (Beat This! beats -> BPM).

detect_beats() also returns downbeats, which beatgrid.py and structure.py use.
"""

from __future__ import annotations

from common import TrackError, Timer, debugger, device, fit_bpm, free_gpu, gpu_memory

STEP = "tempo"
D = debugger(STEP)

# Settings
CHECKPOINT = "final0"
MIN_BEATS = 8
MIN_CONFIDENCE = 0.5       # below this share of steady beats, the BPM gets a warning
GRID_S = 0.02              # Beat This! time grid (50 frames per second)

_model = None


def _load():
    global _model
    if _model is None:
        from beat_this.inference import Audio2Beats
        with Timer(D, "load Beat This!"):
            _model = Audio2Beats(checkpoint_path=CHECKPOINT, device=device(), dbn=False)
        D(2, f"Beat This! loaded (checkpoint {CHECKPOINT}, {gpu_memory()})")
    return _model


def detect_beats(audio, sr: int, offset: float) -> tuple[list[float], list[float]]:
    """Beat and downbeat times in seconds. offset is added so times match the file timeline."""
    model = _load()
    D(2, f"input {audio.shape[0] / sr:.2f}s at {sr} Hz, offset {offset:.3f}s")
    with Timer(D, "beat tracking"):
        beats, downbeats = model(audio, sr)
    D(3, gpu_memory())
    free_gpu()
    beats = [float(b) + offset for b in beats]
    downbeats = [float(d) + offset for d in downbeats]
    D(4, f"{len(beats)} beats, {len(downbeats)} downbeats")
    D(5, lambda: "beats: " + ", ".join(f"{b:.3f}" for b in beats))
    D(5, lambda: "downbeats: " + ", ".join(f"{d:.3f}" for d in downbeats))
    return beats, downbeats


def bpm(beats: list[float]) -> tuple[float, float]:
    """Returns (bpm, confidence). Confidence = share of beats in steady runs."""
    import numpy as np
    if len(beats) < MIN_BEATS:
        raise TrackError(f"tempo: only {len(beats)} beats detected")
    iv = np.diff(np.asarray(beats))
    median = float(np.median(iv))
    D(4, lambda: f"beat intervals: min {iv.min():.4f}s, median {median:.4f}s, max {iv.max():.4f}s")

    # Two candidates for the main beat interval: the median, and the most common
    # interval (on the 0.02 s grid). The one giving more steady beats wins.
    grid = np.rint(iv / GRID_S).astype(int)
    common = float(np.bincount(grid[grid > 0]).argmax() * GRID_S) if (grid > 0).any() else median
    best = None
    for name, ref in (("median", median), ("most common", common)):
        value, share = fit_bpm(beats, ref)
        D(2, f"reference {name} {ref:.3f}s -> {value:.2f} BPM, {share:.0%} steady beats")
        if best is None or share > best[1]:
            best = (value, share)
    value, share = best

    D(2, f"stepped median value would be {60.0 / median:.2f} BPM")
    quality = "ok" if share >= MIN_CONFIDENCE else "LOW CONFIDENCE"
    D(1, f"BPM {value:.2f} ({share:.0%} steady beats, {quality})")
    return value, share

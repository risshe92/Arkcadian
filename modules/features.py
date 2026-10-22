"""
Brightness (spectral centroid) and onset density (librosa).
"""

from __future__ import annotations

from common import Timer, debugger

STEP = "features"
D = debugger(STEP)

# Settings
SAMPLE_RATE = 22050
QUIET_RMS = 1e-4           # frames quieter than this are left out of brightness


def analyse(mono, sr: int) -> tuple[float, float]:
    """Returns (brightness in Hz, onsets per second)."""
    import librosa
    import numpy as np

    with Timer(D, "resample"):
        y = librosa.resample(mono, orig_sr=sr, target_sr=SAMPLE_RATE, res_type="soxr_hq") \
            if sr != SAMPLE_RATE else mono
    D(2, f"input {y.size / SAMPLE_RATE:.2f}s at {SAMPLE_RATE} Hz")

    with Timer(D, "spectral centroid"):
        centroid = librosa.feature.spectral_centroid(y=y, sr=SAMPLE_RATE)[0]
        rms = librosa.feature.rms(y=y)[0]
    n = min(centroid.size, rms.size)
    loud = rms[:n] > QUIET_RMS
    brightness = float(np.mean(centroid[:n][loud])) if loud.any() else float(np.mean(centroid))
    D(4, lambda: f"centroid: {n} frames, {int(loud.sum())} used, min {centroid.min():.1f}, "
                 f"max {centroid.max():.1f} Hz")
    D(5, lambda: "centroid per frame: " + ", ".join(f"{c:.0f}" for c in centroid))

    with Timer(D, "onset detection"):
        onsets = librosa.onset.onset_detect(y=y, sr=SAMPLE_RATE, units="time")
    density = len(onsets) / (y.size / SAMPLE_RATE)
    D(4, f"{len(onsets)} onsets")
    D(5, lambda: "onsets: " + ", ".join(f"{t:.3f}" for t in onsets))
    D(1, f"brightness {brightness:.1f} Hz, onset density {density:.3f}/s")
    return brightness, density

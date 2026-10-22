"""
Energy. Inputs are normalised to 0-1, then weighted. Output 0-1.
"""

from __future__ import annotations

from common import debugger

STEP = "energy"
D = debugger(STEP)

# Settings
WEIGHTS = {"loudness": 0.4, "brightness": 0.2, "onset_density": 0.2, "tempo": 0.2}
RANGES = {
    "loudness": (-30.0, -6.0),      # LUFS
    "brightness": (500.0, 4000.0),  # Hz
    "onset_density": (0.0, 6.0),    # onsets per second
    "tempo": (60.0, 180.0),         # BPM
}


def calc(lufs: float, brightness: float, onset_density: float, bpm: float) -> float:
    values = {"loudness": lufs, "brightness": brightness, "onset_density": onset_density, "tempo": bpm}
    total = 0.0
    for name, weight in WEIGHTS.items():
        lo, hi = RANGES[name]
        norm = min(1.0, max(0.0, (values[name] - lo) / (hi - lo)))
        total += weight * norm
        D(2, f"{name}: {values[name]:.3f} -> {norm:.3f} x {weight}")
    D(1, f"energy {total:.3f}")
    return total

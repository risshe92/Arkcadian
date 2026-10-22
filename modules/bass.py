"""
Low-end activity and bassline activity.

Low end (step "lowend", DSP only):
  The full mix, band-passed to LOW_BAND (kick, bass, sub-bass together).
  - LOW_END_ONSET_DENSITY_RAW  low-frequency attacks per second
  - LOW_END_OCCUPANCY_RAW      share of the music with active low end (0-1)
  - LOW_END_ENERGY_RATIO_RAW   low-band energy / full-signal energy (0-1)

Bassline (step "bassline", Demucs bass stem + DSP):
  The bass stem from the same Demucs pass used for vocals. Not low-passed,
  so bass harmonics are kept.
  - BASSLINE_ONSET_DENSITY_RAW attacks per second in the bass stem
  - BASSLINE_OCCUPANCY_RAW     share of the music with an active bass stem (0-1)

"Music" = frames where the full mix is above ELIGIBLE_DB (silence is left out).

Composites: LOW_END_ACTIVITY_RAW and BASSLINE_ACTIVITY_RAW. Their 1-5 ratings
are set in tags.py. The rating thresholds were set with the detection settings
below: changing a setting means checking the ratings again.
"""

from __future__ import annotations

from common import Timer, debugger

D_LOW = debugger("lowend")
D_BASS = debugger("bassline")

# Settings
LOW_BAND = (30.0, 150.0)   # Hz, band-pass for the low end
FILTER_ORDER = 4           # Butterworth, run forwards and backwards (no time shift)
ENV_SMOOTH_HZ = 25.0       # envelope = signal power, low-passed at this frequency (about 6 ms time resolution)
HOP_S = 0.005              # envelope sampled every 5 ms
ELIGIBLE_DB = -60.0        # full-mix frames quieter than this are silence, not music
ACTIVE_ABS_DB = -45.0      # a band counts as active above this level (dBFS)...
ACTIVE_REL_DB = 24.0       # ...and when no more than this far below the full mix
ATTACK_RISE_DB = 6.0       # an attack = the envelope rises at least this much...
ATTACK_LOOKBACK_S = 0.035  # ...within this time
ATTACK_MIN_GAP_S = 0.060   # two attacks must be at least this far apart
BEAT_MATCH_S = 0.035       # bass attack this close to a beat counts as "on the beat"


def _envelope_db(x, sr: int):
    """Power envelope in dBFS, one value per hop.

    Signal power low-passed at ENV_SMOOTH_HZ (zero-phase), so short gaps between
    fast bass notes stay visible, while the wave cycles of low notes are smoothed out.
    """
    import numpy as np
    from scipy.signal import butter, sosfiltfilt
    hop = max(1, int(round(HOP_S * sr)))
    x = np.asarray(x, dtype=np.float64)
    if x.size < 4 * hop:
        return np.full(1, -120.0), hop / sr
    sos = butter(2, ENV_SMOOTH_HZ, btype="lowpass", fs=sr, output="sos")
    power = sosfiltfilt(sos, x * x)[::hop]
    return 10 * np.log10(np.maximum(power, 1e-12)), hop / sr


def _attacks(env_db, active, hop_s: float):
    """Frame indices of attacks: a rise of ATTACK_RISE_DB within ATTACK_LOOKBACK_S,
    on an active frame, at least ATTACK_MIN_GAP_S apart (strongest rise wins)."""
    import numpy as np
    k = max(1, int(round(ATTACK_LOOKBACK_S / hop_s)))
    gap = max(1, int(round(ATTACK_MIN_GAP_S / hop_s)))
    n = env_db.size
    if n <= k:
        return np.array([], dtype=int)
    # rise = current level minus the lowest level in the previous k frames
    from numpy.lib.stride_tricks import sliding_window_view
    prev_min = sliding_window_view(env_db[:-1], k).min(axis=1)    # frames k..n-1
    from scipy.ndimage import maximum_filter1d
    rise = np.full(n, 0.0)
    rise[k:] = env_db[k:] - prev_min
    # Keep only the strongest rise within +-gap frames, then enforce the gap in time order
    peak = rise >= maximum_filter1d(rise, size=2 * gap + 1, mode="nearest")
    cand = np.flatnonzero(peak & (rise >= ATTACK_RISE_DB) & active)
    picked: list[int] = []
    for i in cand:
        if not picked or i - picked[-1] >= gap:
            picked.append(int(i))
    return np.asarray(picked, dtype=int)


def _measure(band, full, sr: int, D):
    """(attacks per second, occupancy 0-1, eligible seconds, attack times) for one band."""
    import numpy as np
    band_db, hop_s = _envelope_db(band, sr)
    full_db, _ = _envelope_db(full, sr)
    n = min(band_db.size, full_db.size)
    band_db, full_db = band_db[:n], full_db[:n]
    eligible = full_db > ELIGIBLE_DB
    active = eligible & (band_db > ACTIVE_ABS_DB) & (band_db > full_db - ACTIVE_REL_DB)
    seconds = float(eligible.sum()) * hop_s
    D(4, lambda: f"{n} frames of {hop_s * 1000:.1f} ms, {int(eligible.sum())} eligible, {int(active.sum())} active")
    D(5, lambda: "band dB per frame: " + ", ".join(f"{x:.1f}" for x in band_db))
    if seconds <= 0:
        return None, None, 0.0, []
    hits = _attacks(band_db, active, hop_s)
    times = (hits * hop_s).tolist()
    D(5, lambda: "attacks: " + ", ".join(f"{t:.3f}" for t in times))
    return len(hits) / seconds, float(active.sum() / eligible.sum()), seconds, times


def low_end(mono, sr: int) -> tuple[float | None, float | None, float | None]:
    """Returns (LOW_END_ONSET_DENSITY_RAW, LOW_END_OCCUPANCY_RAW, LOW_END_ENERGY_RATIO_RAW)."""
    import numpy as np
    from scipy.signal import butter, sosfiltfilt
    D_LOW(2, f"band {LOW_BAND[0]:g}-{LOW_BAND[1]:g} Hz, order {FILTER_ORDER}, attack rise {ATTACK_RISE_DB:g} dB, "
             f"active > {ACTIVE_ABS_DB:g} dBFS and within {ACTIVE_REL_DB:g} dB of the mix")
    x = np.asarray(mono, dtype=np.float64)
    if x.size == 0 or not np.any(x):
        D_LOW(1, "silent audio, nothing measured")
        return None, None, None
    sos = butter(FILTER_ORDER, LOW_BAND, btype="bandpass", fs=sr, output="sos")
    with Timer(D_LOW, "band-pass filter"):
        low = sosfiltfilt(sos, x)
    total = float(np.sum(x * x))
    ratio = float(np.sum(low * low) / total) if total > 0 else None
    with Timer(D_LOW, "envelope and attacks"):
        density, occupancy, seconds, _ = _measure(low, x, sr, D_LOW)
    D_LOW(1, f"onsets {density}/s, occupancy {occupancy}, energy ratio {ratio} ({seconds:.1f}s of music)")
    D_LOW(1, f"LOW_END_ACTIVITY_RAW {low_end_activity(density)}")
    return density, occupancy, ratio


# Low-end activity composite.
# The attack rate is averaged over all the music, breakdowns included, so
# persistence is already part of it. Occupancy is not used: it also counts
# sustained pads and sub-bass, so it does not measure rhythmic persistence.
LE_RATE_MAX = 4.0          # attacks/s for full credit (about the collection's 90th percentile)


def low_end_activity(density: float | None) -> float | None:
    """LOW_END_ACTIVITY_RAW = min(1, LOW_END_ONSET_DENSITY_RAW / LE_RATE_MAX)."""
    if density is None:
        return None
    return min(1.0, density / LE_RATE_MAX)


# Bassline activity composite.
# Kick leakage into the bass stem was checked by listening and changed no
# rating, so no leakage correction is applied.
BL_RATE_MAX = 3.0          # attacks/s for full rate credit (about the collection's 90th percentile)
BL_OCC_FULL = 0.4          # occupancy for full presence credit


def bassline_activity(density: float | None, occupancy: float | None) -> float | None:
    """BASSLINE_ACTIVITY_RAW = min(1, density / BL_RATE_MAX) x min(1, occupancy / BL_OCC_FULL)."""
    if density is None or occupancy is None:
        return None
    return min(1.0, density / BL_RATE_MAX) * min(1.0, occupancy / BL_OCC_FULL)


def bassline(bass_stem, mix, sr: int, beats_rel: list[float] | None = None) -> tuple[float | None, float | None, list[str]]:
    """Returns (BASSLINE_ONSET_DENSITY_RAW, BASSLINE_OCCUPANCY_RAW, warnings).

    beats_rel: beat times relative to the start of the audio. Only used for the
    kick-leakage check in the log, never written to tags.
    """
    import numpy as np
    D_BASS(2, f"bass stem, full range (no low-pass), attack rise {ATTACK_RISE_DB:g} dB, "
              f"active > {ACTIVE_ABS_DB:g} dBFS and within {ACTIVE_REL_DB:g} dB of the mix")
    stem = np.asarray(bass_stem, dtype=np.float64)
    if stem.size == 0 or not np.any(stem):
        D_BASS(1, "empty bass stem, nothing measured")
        return None, None, ["bass stem empty, bassline not written"]
    with Timer(D_BASS, "envelope and attacks"):
        density, occupancy, seconds, times = _measure(stem, mix, sr, D_BASS)
    warnings: list[str] = []
    if beats_rel and times:
        b = np.asarray(beats_rel)
        t = np.asarray(times)
        idx = np.clip(np.searchsorted(b, t), 1, b.size - 1)
        nearest = np.minimum(np.abs(t - b[idx - 1]), np.abs(t - b[idx]))
        on_beat = float(np.mean(nearest <= BEAT_MATCH_S))
        D_BASS(1, f"{on_beat:.0%} of bass attacks fall on a beat (kick-leakage check)")
    D_BASS(1, f"onsets {density}/s, occupancy {occupancy} ({seconds:.1f}s of music)")
    D_BASS(1, f"BASSLINE_ACTIVITY_RAW {bassline_activity(density, occupancy)}")
    return density, occupancy, warnings

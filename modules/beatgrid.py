"""
Beat grid (first downbeat and tempo change points).

A tempo change is only accepted when it:
- differs from the current tempo by more than CHANGE_BPM
- lasts at least MIN_SEGMENT_S seconds
- stays inside MIN_BPM - MAX_BPM
- is not a double/half/triplet jump (a beat-tracking error, not a real change)
"""

from __future__ import annotations

import math

from common import TrackError, debugger, fit_bpm

STEP = "beatgrid"
D = debugger(STEP)

# Settings
MIN_BEATS = 8
WINDOW_BEATS = 32          # beats used for the local tempo (8 bars)
INLIER = 0.08              # intervals within 8% of the window median are used
CHANGE_BPM = 1.5           # difference that counts as a tempo change
MIN_SEGMENT_S = 30.0       # a new tempo must last this long
MIN_BPM, MAX_BPM = 60.0, 200.0
TRACKING_ERROR_RATIOS = (2.0, 0.5, 1.5, 2 / 3)
TRACKING_ERROR_TOLERANCE = 0.06
BEATS_PER_BAR = 4
LATE_DOWNBEAT_BEATS = 8    # warn when the first downbeat comes this many beats after the music starts


def _is_tracking_error(new: float, current: float) -> bool:
    ratio = new / current
    return any(abs(ratio / r - 1) <= TRACKING_ERROR_TOLERANCE for r in TRACKING_ERROR_RATIOS)


def _local_tempo(b, iv):
    """Average tempo of each window of WINDOW_BEATS intervals. NaN where the window is not steady."""
    import numpy as np
    w = min(WINDOW_BEATS, iv.size)
    out = np.full(iv.size - w + 1, np.nan)
    for i in range(out.size):
        win = iv[i:i + w]
        med = np.median(win)
        good = win[np.abs(win / med - 1) <= INLIER]
        if good.size >= w // 2:
            out[i] = 60.0 / good.mean()
    return out, w


def _locate_change(iv, start: int, stop: int, old: float, new: float) -> int:
    """First beat where a short 8-beat average is closer to the new tempo than the old one."""
    import numpy as np
    k = 8
    for idx in range(start, max(start + 1, stop)):
        win = iv[idx:idx + k]
        if win.size < k:
            break
        med = np.median(win)
        good = win[np.abs(win / med - 1) <= INLIER]
        if good.size and abs(60.0 / good.mean() - new) < abs(60.0 / good.mean() - old):
            return idx + k // 2
    return start


def _check_downbeats(beats, downbeats, bpm: float, music_start: float) -> list[str]:
    import numpy as np
    warnings = []
    if len(downbeats) >= 4:
        period = 60.0 / bpm
        bar = np.diff(np.asarray(downbeats)) / period
        steady = bar[np.abs(bar - np.rint(bar)) < 0.25]
        per_bar = float(np.median(np.rint(steady))) if steady.size else float("nan")
        share = float(np.mean(np.rint(steady) == BEATS_PER_BAR)) if steady.size else 0.0
        D(2, f"beats per bar: {per_bar:g} ({share:.0%} of bars have {BEATS_PER_BAR} beats)")
        if per_bar != BEATS_PER_BAR:
            warnings.append(f"downbeats are {per_bar:g} beats apart, not {BEATS_PER_BAR}: check by ear")
    first = downbeats[0] if downbeats else None
    if first is not None:
        late = (first - music_start) * bpm / 60.0
        D(2, f"first downbeat {first - music_start:.3f}s ({late:.1f} beats) after the music starts")
        if late > LATE_DOWNBEAT_BEATS:
            warnings.append(f"first downbeat {first - music_start:.1f}s after the music starts: check by ear")
    return warnings


def analyse(beats: list[float], downbeats: list[float], main_bpm: float | None,
            music_start: float) -> tuple[float | None, list[tuple[float, float]] | None, list[str]]:
    """Returns (first_downbeat, tempo_changes, warnings). tempo_changes is None when steady."""
    import numpy as np
    b = np.asarray(beats, dtype=float)
    if b.size < MIN_BEATS:
        raise TrackError(f"beatgrid: only {b.size} beats detected")
    if main_bpm is None:
        main_bpm = fit_bpm(beats)[0]
    D(2, f"main BPM {main_bpm:.2f}; window {WINDOW_BEATS} beats, change {CHANGE_BPM} BPM, "
         f"min segment {MIN_SEGMENT_S:g}s, range {MIN_BPM:g}-{MAX_BPM:g} BPM")

    first_downbeat = float(downbeats[0]) if downbeats else None
    warnings = _check_downbeats(beats, downbeats, main_bpm, music_start)

    iv = np.diff(b)
    local, w = _local_tempo(b, iv)
    D(4, lambda: f"local tempo: {int(np.isnan(local).sum())} unsteady windows of {local.size}")
    D(5, lambda: "local tempo per window: " + ", ".join("-" if math.isnan(x) else f"{x:.2f}" for x in local))

    steady = np.flatnonzero(~np.isnan(local))
    if steady.size == 0:
        D(1, f"first downbeat {first_downbeat}, no steady section, tempo treated as steady")
        return first_downbeat, None, warnings
    # Start from the first steady tempo, not the track average (an average can sit
    # between two real tempos and hide the change). A half/double-time start uses the main BPM.
    seg = float(local[steady[0]])
    if _is_tracking_error(seg, main_bpm) or not MIN_BPM <= seg <= MAX_BPM:
        seg = main_bpm
    D(3, f"starting tempo {seg:.2f} BPM")

    starts = [0]
    i = 0
    while i < local.size:
        x = local[i]
        if math.isnan(x) or abs(x - seg) <= CHANGE_BPM:
            i += 1
            continue
        if not MIN_BPM <= x <= MAX_BPM or _is_tracking_error(x, seg):
            D(5, f"{b[i]:.3f}s: {x:.2f} BPM ignored (out of range or tracking error)")
            i += 1
            continue
        # How long does the new tempo last?
        j = i
        while j < local.size and not math.isnan(local[j]) \
                and abs(local[j] - x) <= 2 * CHANGE_BPM and abs(local[j] - seg) > CHANGE_BPM:
            j += 1
        duration = b[min(j + w // 2, b.size - 1)] - b[i + w // 2]
        if duration < MIN_SEGMENT_S:
            D(4, f"{b[i + w // 2]:.3f}s: {x:.2f} BPM for {duration:.1f}s, too short, ignored")
            i += 1
            continue
        new = float(np.median(local[i:j]))
        at = _locate_change(iv, i, min(i + w + w // 2, iv.size), seg, new)
        if at <= starts[-1]:
            at = i + w // 2
        starts.append(at)
        D(3, f"tempo change at {b[at]:.3f}s: {seg:.2f} -> about {new:.2f} BPM for {duration:.1f}s")
        seg = new
        i = j

    def tempo_of(s: int, e: int) -> float:
        part = b[s:e + 1]
        return fit_bpm(part)[0] if part.size > MIN_BEATS else main_bpm

    # Segments as [start index, end index, bpm]
    bounds = starts + [b.size - 1]
    raw = [[bounds[k], bounds[k + 1], tempo_of(bounds[k], bounds[k + 1])] for k in range(len(starts))]

    # Segments shorter than MIN_SEGMENT_S are merged into a neighbour
    kept: list[list] = []
    carry = None
    for s, e, bpm in raw:
        if len(raw) > 1 and b[e] - b[s] < MIN_SEGMENT_S:
            D(3, f"segment at {b[s]:.3f}s ({b[e] - b[s]:.1f}s) too short, merged")
            if kept:
                kept[-1][1] = e
            elif carry is None:
                carry = s
            continue
        if carry is not None:
            s, carry = carry, None
        kept.append([s, e, bpm])

    # Neighbours with the same tempo are merged, then each tempo is measured again
    merged: list[list] = []
    for s, e, bpm in kept:
        if merged and abs(merged[-1][2] - bpm) <= CHANGE_BPM:
            D(3, f"segment at {b[s]:.3f}s ({bpm:.2f}) merged with the previous one")
            merged[-1][1] = e
            continue
        merged.append([s, e, bpm])
    segments = [(float(b[s]), tempo_of(s, e)) for s, e, _ in merged]

    if len(segments) <= 1:
        D(1, f"first downbeat {first_downbeat}, steady tempo")
        return first_downbeat, None, warnings
    D(1, f"first downbeat {first_downbeat}, {len(segments)} tempo segments")
    D(2, lambda: "segments: " + ", ".join(f"{t:.3f}s:{v:.2f}" for t, v in segments))
    return first_downbeat, segments, warnings

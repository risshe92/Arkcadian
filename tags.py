"""
Tag names, formatting, classification, validation, reading and writing
(TagLib only, via pytaglib).

Rated metrics are written twice:
  <NAME>_RAW  the measured value at full calculated precision
  <NAME>      a DJ rating, integer 1-5, classified from the unrounded raw value
"""

from __future__ import annotations

import math
import re
from pathlib import Path

from common import Result, TrackError, debugger

STEP = "tags"
D = debugger(STEP)

# Optional prefix for custom tags, e.g. "DJ" gives DJ_ENERGY. Empty = no prefix.
TAG_PREFIX = ""

STD_BPM = "BPM"
STD_KEY = "INITIALKEY"
STD_RG_GAIN = "REPLAYGAIN_TRACK_GAIN"
STD_RG_PEAK = "REPLAYGAIN_TRACK_PEAK"
STANDARD = {STD_BPM, STD_KEY, STD_RG_GAIN, STD_RG_PEAK}


def ctag(name: str) -> str:
    """Custom tag name, with the prefix if one is set."""
    return f"{TAG_PREFIX}_{name}" if TAG_PREFIX else name


def owned() -> dict[str, list[str]]:
    """Tags written by each step."""
    return {
        "silence": [ctag("SILENCE_FOUND"), ctag("MUSIC_START"), ctag("MUSIC_END"), ctag("TRIMMED")],
        "tempo": [STD_BPM, ctag("BPM_EXACT")],
        "beatgrid": [ctag("FIRST_DOWNBEAT"), ctag("TEMPO_CHANGES")],
        "key": [STD_KEY],
        "loudness": [STD_RG_GAIN, STD_RG_PEAK] + _raw_and_rating("INTEGRATED_LOUDNESS", "LOUDNESS_RANGE"),
        "features": [ctag("BRIGHTNESS_RAW"), ctag("BRIGHTNESS"),
                     ctag("ONSET_DENSITY_RAW"), ctag("ONSET_DENSITY")],
        "vocals": [ctag("VOCAL_DENSITY_RAW"), ctag("VOCAL_DENSITY")],
        "lowend": [ctag("LOW_END_ONSET_DENSITY_RAW"), ctag("LOW_END_OCCUPANCY_RAW"),
                   ctag("LOW_END_ENERGY_RATIO_RAW"), ctag("LOW_END_ACTIVITY_RAW")]
                  + _rating_name("LOW_END_ACTIVITY"),
        "bassline": [ctag("BASSLINE_ONSET_DENSITY_RAW"), ctag("BASSLINE_OCCUPANCY_RAW"),
                     ctag("BASSLINE_ACTIVITY_RAW")]
                    + _rating_name("BASSLINE_ACTIVITY"),
        "structure": [ctag("INTRO_LENGTH"), ctag("OUTRO_LENGTH")],
        "energy": [ctag("ENERGY_RAW"), ctag("ENERGY")],
    }


# ---------------------------------------------------------------------------
# Loudness, low-end and bassline ratings
# ---------------------------------------------------------------------------
# 4 ascending boundaries (b1, b2, b3, b4): x < b1 -> 1, b1 <= x < b2 -> 2, ..., x >= b4 -> 5
# None = no rating for that metric: only the raw value is written.
RATING_THRESHOLDS: dict[str, tuple[float, float, float, float] | None] = {
    # Anchors: -14 LUFS streaming level, -9 to -7 LUFS club masters.
    "INTEGRATED_LOUDNESS": (-14.0, -11.0, -9.0, -7.0),   # LUFS
    # 1 = flat, 5 = big breakdowns. Not an energy rating.
    "LOUDNESS_RANGE": (4.0, 6.0, 8.0, 11.0),             # LU
    # min(1, LOW_END_ONSET_DENSITY_RAW / 4.0)
    "LOW_END_ACTIVITY": (0.2, 0.4, 0.6, 0.8),            # composite 0-1
    # min(1, BASSLINE_ONSET_DENSITY_RAW / 3.0) x min(1, BASSLINE_OCCUPANCY_RAW / 0.4)
    "BASSLINE_ACTIVITY": (0.2, 0.4, 0.6, 0.8),           # composite 0-1
}

# Raw-only measurements: (minimum, maximum) allowed. None = no limit on that side.
RAW_LIMITS: dict[str, tuple[float | None, float | None]] = {
    "INTEGRATED_LOUDNESS_RAW": (None, None),    # LUFS, finite
    "LOUDNESS_RANGE_RAW": (0.0, None),          # LU
    "LOW_END_ONSET_DENSITY_RAW": (0.0, None),   # per second
    "LOW_END_OCCUPANCY_RAW": (0.0, 1.0),
    "LOW_END_ENERGY_RATIO_RAW": (0.0, 1.0),
    "LOW_END_ACTIVITY_RAW": (0.0, 1.0),
    "BASSLINE_ONSET_DENSITY_RAW": (0.0, None),  # per second
    "BASSLINE_OCCUPANCY_RAW": (0.0, 1.0),
    "BASSLINE_ACTIVITY_RAW": (0.0, 1.0),
}


def _rating_name(metric: str) -> list[str]:
    """The 1-5 field, if the metric has thresholds."""
    return [ctag(metric)] if RATING_THRESHOLDS.get(metric) else []


def _raw_and_rating(*metrics: str) -> list[str]:
    names: list[str] = []
    for m in metrics:
        names.append(ctag(f"{m}_RAW"))
        names += _rating_name(m)
    return names


def classify_threshold(metric: str, value) -> int | None:
    """1-5 from RATING_THRESHOLDS, or None (no thresholds, missing or invalid)."""
    bounds = RATING_THRESHOLDS.get(metric)
    if not bounds or value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    return 1 + sum(x >= b for b in bounds)


def _raw_only(t: dict[str, str], r: Result, name: str, value) -> None:
    """Adds one raw measurement after a range check. Nothing is written if invalid."""
    if value is None:
        return
    lo, hi = RAW_LIMITS[name]
    try:
        x = float(value)
    except (TypeError, ValueError):
        x = float("nan")
    if not math.isfinite(x) or (lo is not None and x < lo) or (hi is not None and x > hi):
        r.warnings.append(f"{name}: invalid value {value!r}, not written")
        return
    t[ctag(name)] = raw_str(x)


# ---------------------------------------------------------------------------
# Classification (raw value -> DJ rating 1-5)
# ---------------------------------------------------------------------------
# Each metric: (kind, boundaries). A rating is 1 + the number of boundaries the
# value has reached (value >= boundary).
#   "unit"     normalised 0-1 value. Valid range 0 <= x <= 1.
#   "physical" measurement >= 0. Exactly 0 gives rating 1; any value above 0
#              starts at rating 2.

CLASSES = {
    "ENERGY":        ("unit", (0.20, 0.40, 0.60, 0.80)),
    "VOCAL_DENSITY": ("unit", (0.20, 0.40, 0.60, 0.80)),
    "BRIGHTNESS":    ("physical", (1500.0, 2200.0, 2800.0)),       # Hz
    "ONSET_DENSITY": ("physical", (2.00, 3.00, 4.50)),             # onsets per second
}


def classify(metric: str, value) -> int | None:
    """DJ rating 1-5 for a raw value, or None if the value is missing or invalid.

    Classifies the unrounded value. Never invents a rating: None, NaN, infinity,
    negative measurements and normalised values outside 0-1 all return None.
    """
    kind, bounds = CLASSES[metric]
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or x < 0:
        return None
    if kind == "unit":
        if x > 1.0:
            return None
        return 1 + sum(x >= b for b in bounds)
    if x == 0:
        return 1
    return 2 + sum(x >= b for b in bounds)


def raw_str(value) -> str:
    """Full-precision decimal text for a raw value. No rounding.

    Uses the shortest text that converts back to exactly the same number, in
    plain decimal form (never 1e-05 style). Values that are exactly float32 (e.g.
    librosa output) use float32 precision, so no meaningless extra digits appear.
    """
    import numpy as np
    x = float(value)
    if not math.isfinite(x):
        raise TrackError(f"raw value is not a finite number: {value}")
    if float(np.float32(x)) == x and not float(x).is_integer():
        return np.format_float_positional(np.float32(x), unique=True, trim="0")
    return np.format_float_positional(x, unique=True, trim="0")


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def _f3(x: float) -> str:
    return f"{x:.3f}"


def build(r: Result, steps: list[str]) -> dict[str, str]:
    t: dict[str, str] = {}
    if "silence" in steps and r.silence_found is not None:
        t[ctag("SILENCE_FOUND")] = "1" if r.silence_found else "0"
        t[ctag("MUSIC_START")] = _f3(r.music_start)
        t[ctag("MUSIC_END")] = _f3(r.music_end)
        t[ctag("TRIMMED")] = "1" if r.trimmed else "0"
    if "tempo" in steps and r.bpm_exact is not None:
        t[STD_BPM] = str(round(r.bpm_exact))
        t[ctag("BPM_EXACT")] = f"{r.bpm_exact:.1f}"
    if "beatgrid" in steps:
        if r.first_downbeat is not None:
            t[ctag("FIRST_DOWNBEAT")] = _f3(max(0.0, r.first_downbeat))
        if r.tempo_changes:
            t[ctag("TEMPO_CHANGES")] = ",".join(f"{max(0.0, a):.3f}:{b:.1f}" for a, b in r.tempo_changes)
    if "key" in steps and r.key:
        t[STD_KEY] = r.key
    if "loudness" in steps and r.rg_gain is not None:
        t[STD_RG_GAIN] = f"{r.rg_gain:.2f} dB"
        t[STD_RG_PEAK] = f"{r.rg_peak:.6f}"
    if "loudness" in steps:
        for metric, value in (("INTEGRATED_LOUDNESS", r.integrated_loudness),
                              ("LOUDNESS_RANGE", r.loudness_range)):
            _raw_only(t, r, f"{metric}_RAW", value)
            rating = classify_threshold(metric, value) if ctag(f"{metric}_RAW") in t else None
            if rating is not None:
                t[ctag(metric)] = str(rating)
    if "features" in steps:
        _rated(t, r, "BRIGHTNESS", r.brightness)
        _rated(t, r, "ONSET_DENSITY", r.onset_density)
    if "vocals" in steps:
        _rated(t, r, "VOCAL_DENSITY", r.vocal_density)
    if "lowend" in steps:
        _raw_only(t, r, "LOW_END_ONSET_DENSITY_RAW", r.low_end_onset_density)
        _raw_only(t, r, "LOW_END_OCCUPANCY_RAW", r.low_end_occupancy)
        _raw_only(t, r, "LOW_END_ENERGY_RATIO_RAW", r.low_end_energy_ratio)
        _raw_only(t, r, "LOW_END_ACTIVITY_RAW", r.low_end_activity)
        rating = classify_threshold("LOW_END_ACTIVITY", r.low_end_activity) if ctag("LOW_END_ACTIVITY_RAW") in t else None
        if rating is not None:
            t[ctag("LOW_END_ACTIVITY")] = str(rating)
    if "bassline" in steps:
        _raw_only(t, r, "BASSLINE_ONSET_DENSITY_RAW", r.bassline_onset_density)
        _raw_only(t, r, "BASSLINE_OCCUPANCY_RAW", r.bassline_occupancy)
        _raw_only(t, r, "BASSLINE_ACTIVITY_RAW", r.bassline_activity)
        rating = classify_threshold("BASSLINE_ACTIVITY", r.bassline_activity) if ctag("BASSLINE_ACTIVITY_RAW") in t else None
        if rating is not None:
            t[ctag("BASSLINE_ACTIVITY")] = str(rating)
    if "structure" in steps:
        if r.intro_length is not None:
            t[ctag("INTRO_LENGTH")] = _f3(r.intro_length)
        if r.outro_length is not None:
            t[ctag("OUTRO_LENGTH")] = _f3(r.outro_length)
    if "energy" in steps:
        _rated(t, r, "ENERGY", r.energy)
    D(2, f"{len(t)} tag(s) built")
    return t


def _rated(t: dict[str, str], r: Result, metric: str, value) -> None:
    """Adds <metric>_RAW and <metric>. Nothing is written for a missing or invalid value."""
    if value is None:
        return
    rating = classify(metric, value)
    if rating is None:
        r.warnings.append(f"{metric}: invalid value {value!r}, not written")
        return
    t[ctag(f"{metric}_RAW")] = raw_str(value)
    t[ctag(metric)] = str(rating)
    D(3, f"{metric}: raw {t[ctag(metric + '_RAW')]} -> rating {rating}")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

NAME_RE = re.compile(r"^[A-Z0-9_]+$")
NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")
RATING_RE = re.compile(r"^[1-5]$")
RATED = {ctag(m) for m in CLASSES} | {ctag(m) for m, b in RATING_THRESHOLDS.items() if b}
LIST_RE = re.compile(r"^\d+\.\d{3}:\d+\.\d(,\d+\.\d{3}:\d+\.\d)*$")
VALUE_RULES = {
    STD_BPM: re.compile(r"^\d+$"),                      # ID3 TBPM: whole number
    STD_KEY: re.compile(r"^([A-G][b#]?m?|o)$"),         # musical notation, o = no key
    STD_RG_GAIN: re.compile(r"^-?\d+\.\d{2} dB$"),      # ReplayGain: 2 decimals + dB
    STD_RG_PEAK: re.compile(r"^\d+\.\d{6}$"),           # ReplayGain: linear peak, 6 decimals
}


def validate(t: dict[str, str]) -> None:
    known = {n for names in owned().values() for n in names}
    for name, value in t.items():
        if not NAME_RE.match(name):
            raise TrackError(f"invalid tag name (A-Z, 0-9 and _ only): {name}")
        if name not in known:
            raise TrackError(f"unknown tag name, not in tags.owned(): {name}")
        rule = VALUE_RULES.get(name)
        if rule and not rule.match(value):
            raise TrackError(f"invalid value for standard tag: {name}={value}")
        if name == STD_KEY and len(value) > 3:
            raise TrackError(f"INITIALKEY longer than 3 characters: {value}")
        if name in (ctag("SILENCE_FOUND"), ctag("TRIMMED")):
            if value not in ("0", "1"):
                raise TrackError(f"yes/no tag must be 1 or 0: {name}={value}")
        elif name in RATED:
            if not RATING_RE.match(value):
                raise TrackError(f"rating must be an integer 1-5: {name}={value}")
        elif name == ctag("TEMPO_CHANGES"):
            if not LIST_RE.match(value):
                raise TrackError(f"invalid tempo change list: {value}")
        elif name in RAW_LIMITS:
            lo, hi = RAW_LIMITS[name]
            if not NUM_RE.match(value) or (lo is not None and float(value) < lo) \
                    or (hi is not None and float(value) > hi):
                raise TrackError(f"raw value out of range: {name}={value}")
        elif name not in VALUE_RULES and not NUM_RE.match(value):
            raise TrackError(f"invalid number format: {name}={value}")
    D(3, f"{len(t)} tag(s) passed validation")


# ---------------------------------------------------------------------------
# Reading and writing (TagLib only)
# ---------------------------------------------------------------------------


def read(path: Path) -> dict[str, list[str]]:
    import taglib
    with taglib.File(str(path)) as f:
        result = {k.upper(): list(v) for k, v in f.tags.items()}
    D(4, f"read {len(result)} tag(s) from {path.name}")
    D(5, lambda: "\n".join(f"{k}={v}" for k, v in sorted(result.items())) or "none")
    return result


def read_complex(path: Path) -> tuple[dict[str, list], list[str]]:
    """Complex properties (e.g. pictures) and the names of unsupported data."""
    import taglib
    with taglib.File(str(path)) as f:
        cx = {k: list(f.complex_properties(k)) for k in f.complex_property_keys}
        unsupported = list(f.unsupported)
    D(4, f"complex: {', '.join(cx) or 'none'}; unsupported: {', '.join(unsupported) or 'none'}")
    return cx, unsupported


def number(tags: dict[str, list[str]], name: str) -> float | None:
    """First number in an existing tag value, or None."""
    vals = tags.get(name)
    if not vals:
        return None
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)", vals[0])
    return float(m.group(1)) if m else None


def write(path: Path, new: dict[str, str], steps: list[str],
          base_tags: dict[str, list[str]] | None = None,
          base_complex: dict[str, list] | None = None) -> None:
    """Writes tags through the PropertyMap interface.

    base_tags / base_complex: restored first (used after trimming).
    Stale custom tags of the steps that ran are removed. Standard tags are never removed.
    """
    import taglib
    validate(new)
    with taglib.File(str(path)) as f:
        if base_tags is not None:
            f.tags = {k: list(v) for k, v in base_tags.items()}
            D(3, f"restored {len(base_tags)} tag(s)")
        if base_complex:
            for k, values in base_complex.items():
                if not f.set_complex_properties(k, values):
                    raise TrackError(f"could not restore {k} after trimming")
                D(3, f"restored {k} ({len(values)})")
        own = owned()
        for step in steps:
            for name in own[step]:
                if name not in STANDARD and name not in new and name in f.tags:
                    del f.tags[name]
                    D(2, f"removed stale tag {name}")
        for name, value in new.items():
            f.tags[name] = [value]
            D(5, f"set {name}={value}")
        unsaved = f.save()
    if unsaved:
        raise TrackError(f"TagLib could not save: {', '.join(unsaved)}")
    D(1, f"wrote {len(new)} tag(s) to {path.name}")

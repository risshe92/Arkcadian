"""
Intro and outro length.

Intro: music start -> first vocals.
Outro: last vocals -> music end.
Instrumental fallback: first and last downbeat.
"""

from __future__ import annotations

from common import debugger

STEP = "structure"
D = debugger(STEP)


def intro_outro(intervals: list[tuple[float, float]], downbeats: list[float] | None,
                music_start: float, music_end: float) -> tuple[float | None, float | None, str | None]:
    """Returns (intro_length, outro_length, warning).

    intervals: vocal intervals relative to music_start.
    downbeats: on the file timeline.
    """
    region = music_end - music_start
    D(2, f"music {music_start:.3f}s -> {music_end:.3f}s, {len(intervals)} vocal interval(s)")

    if intervals:
        intro = intervals[0][0]
        outro = max(0.0, region - intervals[-1][1])
        D(2, f"first vocal {music_start + intervals[0][0]:.3f}s, last vocal end {music_start + intervals[-1][1]:.3f}s")
        D(1, f"intro {intro:.3f}s, outro {outro:.3f}s (from vocals)")
        return intro, outro, None

    if downbeats:
        intro = max(0.0, downbeats[0] - music_start)
        outro = max(0.0, music_end - downbeats[-1])
        D(1, f"intro {intro:.3f}s, outro {outro:.3f}s (fallback: downbeats)")
        return intro, outro, "no vocals detected, intro/outro use downbeats"

    D(1, "no vocals or downbeats, nothing written")
    return None, None, "no vocals or downbeats, intro/outro not written"

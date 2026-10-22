#!/usr/bin/env python3
"""
Report: export the tags of every track to one CSV, and print a summary.

Read-only. Uses TagLib to read tags and never writes to a track.

CSV layout
- One row per track. One column per tag field found in ANY track.
- File columns first: FILE, LENGTH_S, SAMPLE_RATE, CHANNELS, PICTURES.
- Then the identity tags (TITLE, ARTIST, ...), then this program's tags in
  step order, then every other tag A-Z.
- A tag with several values is joined with " | ".
- A tag missing from a track is an empty cell.

Summary (printed at the end)
- Tracks read, tracks that could not be read.
- Tracks with a full analysis (ENERGY tag present).
- This program's tags that are missing, and in how many tracks.
- How many tracks have each rating (1-5) for every display tag.

Examples
    python3 report.py --input ~/Tracks/Raw --output ~/Tracks/Reports/before.csv
    python3 report.py --input ~/Tracks/Processed --output ~/Tracks/Reports/after.csv --pipeline-only
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

import taglib

import tags

AUDIO_EXTENSIONS = {".flac", ".wav", ".aif", ".aiff"}
IDENTITY = ["TITLE", "ARTIST", "ALBUMARTIST", "ALBUM", "TRACKNUMBER", "DISCNUMBER",
            "DATE", "YEAR", "GENRE"]
FILE_COLUMNS = ["FILE", "LENGTH_S", "SAMPLE_RATE", "CHANNELS", "PICTURES"]
JOIN = " | "

# Tags that are only written in some cases, so a missing value is not a problem.
OPTIONAL = {tags.ctag("TEMPO_CHANGES")}


def pipeline_tags() -> list[str]:
    """This program's tag names, in step order."""
    return [name for names in tags.owned().values() for name in names]


def display_tags() -> list[str]:
    """Rating tags (1-5): a tag X that has a matching X_RAW."""
    names = pipeline_tags()
    return [n for n in names if f"{n}_RAW" in names]


def find_tracks(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        return [path]
    pattern = "**/*" if recursive else "*"
    return sorted(p for p in path.glob(pattern)
                  if p.is_file() and not p.name.startswith(".")
                  and p.suffix.lower() in AUDIO_EXTENSIONS)


def read_track(path: Path, base: Path) -> dict[str, str]:
    with taglib.File(str(path)) as f:
        row = {
            "FILE": str(path.relative_to(base)) if base != path else path.name,
            "LENGTH_S": f"{f.length}",
            "SAMPLE_RATE": f"{f.sampleRate}",
            "CHANNELS": f"{f.channels}",
            "PICTURES": f"{len(f.pictures)}",
        }
        for key, values in f.tags.items():
            row[key.upper()] = JOIN.join(values)
    return row


def order_columns(found: set[str], pipeline_only: bool) -> list[str]:
    pipeline = pipeline_tags()
    columns = [c for c in IDENTITY if c in found]
    columns += [c for c in pipeline if c not in columns and (c in found or pipeline_only)]
    if not pipeline_only:
        columns += sorted(found - set(columns))
    return FILE_COLUMNS + columns


def summary(rows: list[dict[str, str]], failed: list[tuple[Path, str]]) -> str:
    out = [f"Tracks read: {len(rows)} | Could not read: {len(failed)}"]
    for path, error in failed:
        out.append(f"  - {path.name}: {error}")
    if not rows:
        return "\n".join(out)

    energy = tags.ctag("ENERGY")
    analysed = sum(1 for r in rows if r.get(energy))
    out.append(f"Fully analysed (has {energy}): {analysed} of {len(rows)}")

    missing = [(n, sum(1 for r in rows if not r.get(n)))
               for n in pipeline_tags() if n not in OPTIONAL]
    missing = [(n, c) for n, c in missing if c]
    if analysed == 0:
        out.append("No tracks have this program's tags yet.")
    elif missing:
        out.append("")
        out.append("Missing tags (tag: tracks without it)")
        out += [f"  {n}: {c}" for n, c in missing]
    else:
        out.append("No program tags missing.")

    if analysed:
        out.append("")
        out.append("Ratings (tag: tracks with rating 1 / 2 / 3 / 4 / 5)")
        for n in display_tags():
            counts = Counter(r.get(n, "") for r in rows)
            line = " / ".join(str(counts.get(str(i), 0)) for i in range(1, 6))
            out.append(f"  {n}: {line}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Export the tags of every track to a CSV and print a summary. Read-only.")
    p.add_argument("--input", required=True, type=Path, help="A track, or a folder of tracks")
    p.add_argument("--output", required=True, type=Path, help="CSV file to write")
    p.add_argument("--recursive", action="store_true", help="Include tracks in subfolders")
    p.add_argument("--pipeline-only", action="store_true",
                   help="Only the file, identity and this program's tag columns")
    args = p.parse_args(argv)

    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not source.exists():
        p.error(f"--input not found: {source}")
    if output.suffix.lower() in AUDIO_EXTENSIONS:
        p.error("--output must be a .csv file, not a track")

    tracks = find_tracks(source, args.recursive)
    if not tracks:
        print(f"No tracks found in {source}")
        return 1

    base = source if source.is_dir() else source.parent
    rows, failed, found = [], [], set()
    for path in tracks:
        try:
            row = read_track(path, base)
        except OSError as e:
            failed.append((path, str(e)))
            continue
        rows.append(row)
        found.update(k for k in row if k not in FILE_COLUMNS)

    columns = order_columns(found, args.pipeline_only)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Written: {output}")
    print(f"Columns: {len(columns)}")
    print(summary(rows, failed))
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())

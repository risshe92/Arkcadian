#!/usr/bin/env python3
"""
Track analysis: command line, track selection and workflow.

Files:

  common.py               shared helpers
  tags.py                 tag names, formats, reading and writing (TagLib)
  report.py               tag export to CSV, with a summary
  modules/silence.py      silence detection / trim
  modules/tempo.py        Beat This! beats / BPM
  modules/beatgrid.py     downbeats / tempo changes
  modules/key.py          S-KEY key detection
  modules/features.py     brightness / onset density
  modules/bass.py         low-end and bassline activity
  modules/vocals.py       Demucs separation / vocal activity
  modules/structure.py    intro / outro length
  modules/loudness.py     ReplayGain / EBU R128 loudness
  modules/energy.py       energy formula

Run "python3 <this script> --help" for all options.
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import shutil
import sys
from pathlib import Path

# The modules sit next to this script. This works from any folder and with any script name.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Hide Hugging Face's "unauthenticated requests" notice (Demucs model download)
os.environ.setdefault("HF_HUB_VERBOSITY", "error")

import tags  # noqa: E402
from modules import (bass, beatgrid, energy, features, key, loudness, silence,  # noqa: E402
                     structure, tempo, vocals)
from common import (STEPS, Result, SkipTrack, Timer, TrackError, debugger,  # noqa: E402
                    log, set_debug_levels)

D = debugger("main")

# Settings
# Added to the names of copies. Empty = copies keep the original name, so
# --output-directory is then required.
COPY_SUFFIX = ""
SUPPORTED_EXTENSIONS = {".flac", ".wav", ".aif", ".aiff"}
LOSSY_EXTENSIONS = {".mp3", ".aac", ".m4a", ".ogg", ".opus", ".wma"}
# WAV: TagLib's PropertyMap interface also writes RIFF INFO as well as ID3, so WAV tags are not written
WRITE_BLOCKED_EXTENSIONS = {".wav"}

DEBUG_NAMES = STEPS + ["tags", "main"]


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def parse_debug(values: list[str], p: argparse.ArgumentParser) -> dict[str, int]:
    levels: dict[str, int] = {}
    for item in ",".join(values).split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            p.error(f"--debug needs STEP=LEVEL, got: {item}")
        name, _, lvl = item.partition("=")
        name = name.strip().lower()
        if name != "all" and name not in DEBUG_NAMES:
            p.error(f"--debug: unknown step {name}. Valid: all,{','.join(DEBUG_NAMES)}")
        if not lvl.strip().isdigit() or not 1 <= int(lvl) <= 5:
            p.error(f"--debug: level must be 1-5, got: {lvl}")
        if name == "all":
            for n in DEBUG_NAMES:
                levels[n] = max(levels.get(n, 0), int(lvl))
        else:
            levels[name] = int(lvl)
    return levels


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="V1 track analysis. Writes results as tags inside lossless audio files.",
        epilog="Debug levels: 1 results, 2 settings and values, 3 timings and commands, "
               "4 raw tool output, 5 full data.",
    )
    p.add_argument("--input", required=True, type=Path, help="A track, or a folder of tracks")
    p.add_argument("--overwrite", action="store_true",
                   help="Write directly to the original track. No copy.")
    p.add_argument("--output-directory", type=Path,
                   help="Where copies are saved. Default: same folder as the originals.")
    p.add_argument("--recursive", action="store_true", help="Include tracks in subfolders")
    p.add_argument("--trim-silence", action="store_true",
                   help="Trim silence instead of only reporting it")
    p.add_argument("--silence-threshold", type=float, default=silence.DEFAULT_THRESHOLD_DB, metavar="DB",
                   help=f"How quiet counts as silence. Default: {silence.DEFAULT_THRESHOLD_DB:g}")
    p.add_argument("--only", metavar="STEPS",
                   help=f"Run selected steps only, e.g. tempo,key. Steps: {','.join(STEPS)}")
    p.add_argument("--skip-analysed", action="store_true",
                   help=f"Skip tracks that already have the {tags.ctag('ENERGY')} tag")
    p.add_argument("--dry-run", action="store_true", help="Analyse and print results, but write nothing")
    p.add_argument("--limit", type=int, metavar="N", help="Only process the first N tracks")
    p.add_argument("--random", action="store_true",
                   help="Pick tracks in random order. With --limit: a random sample of N tracks")
    p.add_argument("--log-file", type=Path, help="Save the log and summary to a file")
    p.add_argument("--debug", action="append", default=[], metavar="STEP=LEVEL",
                   help=f"Debug output for a step, level 1-5. Repeat or comma-separate. "
                        f"Use all=N for every step. Steps: {','.join(DEBUG_NAMES)}")
    args = p.parse_args(argv)

    if args.overwrite and args.output_directory:
        p.error("--overwrite and --output-directory cannot be used together")
    if args.limit is not None and args.limit < 1:
        p.error("--limit must be 1 or more")
    if args.silence_threshold >= 0:
        p.error("--silence-threshold must be negative, e.g. -60")

    if args.only:
        chosen = [s.strip().lower() for s in args.only.split(",") if s.strip()]
        unknown = [s for s in chosen if s not in STEPS]
        if unknown:
            p.error(f"unknown step(s) in --only: {','.join(unknown)}. Valid: {','.join(STEPS)}")
        args.steps = [s for s in STEPS if s in chosen]
    else:
        args.steps = list(STEPS)
    if args.trim_silence and "silence" not in args.steps:
        p.error("--trim-silence needs the silence step")

    args.debug_levels = parse_debug(args.debug, p)

    args.input = args.input.expanduser().resolve()
    if not args.input.exists():
        p.error(f"--input not found: {args.input}")
    if args.output_directory:
        args.output_directory = args.output_directory.expanduser().resolve()

    # With no copy suffix, a copy in the source folder would replace the original
    if not args.overwrite and not args.dry_run and not COPY_SUFFIX:
        source_dir = args.input if args.input.is_dir() else args.input.parent
        if not args.output_directory:
            p.error("--output-directory is required (copies keep the original file name)")
        if args.output_directory == source_dir:
            p.error("--output-directory must not be the input folder (copies keep the original file name)")
    return args


def setup_logging(log_file: Path | None) -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")
    # Other libraries: warnings and errors only. Set up first, so a library's own
    # logging.basicConfig() call later does nothing.
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
                        datefmt="%H:%M:%S")
    for noisy in ("httpx", "httpx2", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(logging.ERROR)
    log.setLevel(logging.INFO)
    log.propagate = False   # stops every line being printed twice
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    log.addHandler(console)
    if log_file:
        log_file = log_file.expanduser().resolve()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        log.addHandler(fh)


# ---------------------------------------------------------------------------
# What each run needs
# ---------------------------------------------------------------------------


def needs(steps: list[str]) -> dict[str, bool]:
    beats = any(s in steps for s in ("tempo", "beatgrid", "structure"))
    # One Demucs pass serves vocals, structure and bassline
    sep = any(s in steps for s in ("vocals", "structure", "bassline"))
    return {
        "beats": beats,
        "vocals": sep,
        "audio": beats or sep or any(s in steps for s in ("key", "features", "lowend")),
    }


def check_tools(steps: list[str]) -> None:
    n = needs(steps)
    programs = []
    if "silence" in steps:
        programs.append("ffmpeg")
    if "loudness" in steps:
        programs.append("rsgain")
    missing = [t for t in programs if shutil.which(t) is None]
    if missing:
        raise SystemExit(f"Missing program(s) on PATH: {', '.join(missing)}")

    modules = ["numpy", "soundfile", "taglib"]
    if n["beats"]:
        modules += ["torch", "beat_this"]
    if "key" in steps:
        modules += ["torch", "skey", "soxr"]
    if "features" in steps:
        modules += ["librosa"]
    if n["vocals"]:
        modules += ["torch", "demucs", "librosa", "soxr"]
    if "lowend" in steps or "bassline" in steps:
        modules += ["scipy"]
    missing = []
    for m in dict.fromkeys(modules):
        try:
            __import__(m)
        except ImportError:
            missing.append(m)
    if missing:
        raise SystemExit(f"Missing Python module(s): {', '.join(missing)}")


# ---------------------------------------------------------------------------
# Track selection
# ---------------------------------------------------------------------------


def is_own_file(path: Path, args: argparse.Namespace) -> bool:
    """Copies and temporary files made by this script."""
    if ".partial" in path.name:
        return True
    if COPY_SUFFIX and path.stem.endswith(COPY_SUFFIX):
        return True
    out = args.output_directory
    return bool(out) and out != args.input and out in path.parents


def collect_tracks(args: argparse.Namespace) -> tuple[list[Path], list[tuple[Path, str]]]:
    tracks: list[Path] = []
    rejected: list[tuple[Path, str]] = []

    if args.input.is_file():
        if args.recursive:
            log.warning("--recursive ignored: --input is a single file")
        candidates = [args.input]
    else:
        pattern = "**/*" if args.recursive else "*"
        candidates = sorted(p for p in args.input.glob(pattern) if p.is_file())

    for path in candidates:
        if path.name.startswith("."):
            continue
        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            if args.input.is_file() or ext in LOSSY_EXTENSIONS:
                rejected.append((path, "not a supported lossless format"))
            continue
        if is_own_file(path, args):
            D(2, f"ignored (own copy): {path}")
            continue
        if ext in WRITE_BLOCKED_EXTENSIONS and not args.dry_run:
            rejected.append((path, "WAV tag writing is blocked in V1 (TagLib also writes RIFF INFO)"))
            continue
        tracks.append(path)

    if args.random:
        random.shuffle(tracks)
    if args.limit:
        tracks = tracks[:args.limit]
    D(1, f"{len(tracks)} track(s) selected, {len(rejected)} rejected")
    return tracks, rejected


def target_path(src: Path, args: argparse.Namespace) -> Path:
    """Where the result for this track lives."""
    if args.overwrite:
        return src
    name = f"{src.stem}{COPY_SUFFIX}{src.suffix}"
    if args.output_directory:
        if args.input.is_dir():
            return args.output_directory / src.parent.relative_to(args.input) / name
        return args.output_directory / name
    return src.parent / name


def partial_path(target: Path) -> Path:
    return target.with_name(f".{target.stem}.partial{os.getpid()}{target.suffix}")


# ---------------------------------------------------------------------------
# One track
# ---------------------------------------------------------------------------


def load_region(path: Path, start: float, end: float):
    """[start, end) as float32 (samples, channels), and the sample rate."""
    import soundfile as sf
    sr = sf.info(str(path)).samplerate
    s, e = int(round(start * sr)), int(round(end * sr))
    data, _ = sf.read(str(path), start=s, stop=e, dtype="float32", always_2d=True)
    return data, sr


def process_track(src: Path, args: argparse.Namespace) -> Result:
    import soundfile as sf

    steps = args.steps
    n = needs(steps)
    target = target_path(src, args)
    if not args.overwrite and target == src:
        raise TrackError("copy would replace the original. Use --output-directory.")
    in_place = args.overwrite or target.exists()
    base = target if in_place else src
    D(2, f"target {target}, analysed file {base}, in place: {in_place}")
    if in_place and not args.overwrite:
        log.info(f"  updating existing copy: {target.name}")

    base_tags = tags.read(base)
    if args.skip_analysed and base_tags.get(tags.ctag("ENERGY")):
        raise SkipTrack("already analysed")

    r = Result()
    info = sf.info(str(base))
    r.duration = info.frames / info.samplerate
    D(2, f"{info.format} {info.subtype}, {info.samplerate} Hz, {info.channels} ch, {r.duration:.3f}s")

    # Silence
    if "silence" in steps:
        r.silence_found, r.music_start, r.music_end = silence.detect(base, r.duration, args.silence_threshold)
        if r.silence_found:
            log.info(f"  silence found: start {r.music_start:.3f}s, end {r.duration - r.music_end:.3f}s")
    else:
        r.music_start = tags.number(base_tags, tags.ctag("MUSIC_START")) or 0.0
        r.music_end = tags.number(base_tags, tags.ctag("MUSIC_END")) or r.duration
    region = r.music_end - r.music_start

    audio = mono = sr = None
    if n["audio"]:
        with Timer(D, "load audio"):
            audio, sr = load_region(base, r.music_start, r.music_end)
        mono = audio.mean(axis=1)

    # Tempo and beat grid
    downbeats = None
    if n["beats"]:
        beats, downbeats = tempo.detect_beats(audio, sr, r.music_start)
        main_bpm = None
        try:
            main_bpm, confidence = tempo.bpm(beats)
            if "tempo" in steps:
                r.bpm_exact = main_bpm
                log.info(f"  BPM {main_bpm:.2f} (tags: BPM={round(main_bpm)}, "
                         f"{tags.ctag('BPM_EXACT')}={main_bpm:.1f}), {confidence:.0%} steady beats")
                if confidence < tempo.MIN_CONFIDENCE:
                    r.warnings.append(f"BPM low confidence ({confidence:.0%} steady beats): check by ear")
        except TrackError as e:
            if "tempo" in steps:
                r.warnings.append(str(e))
        if "beatgrid" in steps:
            try:
                r.first_downbeat, r.tempo_changes, warns = beatgrid.analyse(
                    beats, downbeats, main_bpm, r.music_start)
                r.warnings.extend(warns)
                if r.first_downbeat is None:
                    r.warnings.append("no downbeat detected")
                if r.tempo_changes:
                    log.info("  tempo changes: " + ", ".join(f"{t:.1f}s {v:.1f}" for t, v in r.tempo_changes))
            except TrackError as e:
                r.warnings.append(str(e))

    # Key
    if "key" in steps:
        notation, conf = key.detect(mono, sr)
        if conf < key.MIN_CONFIDENCE:
            r.warnings.append(f"key unreliable ({notation}, confidence {conf:.2f}), not written")
        else:
            r.key = notation

    # Features, low end, vocals, bassline, structure
    if "features" in steps:
        r.brightness, r.onset_density = features.analyse(mono, sr)
    if "lowend" in steps:
        r.low_end_onset_density, r.low_end_occupancy, r.low_end_energy_ratio = bass.low_end(mono, sr)
        r.low_end_activity = bass.low_end_activity(r.low_end_onset_density)
    if n["vocals"]:
        vocal, bass_stem, mix, vsr = vocals.separate(audio, sr)
        if "bassline" in steps:
            beats_rel = [b - r.music_start for b in beats] if n["beats"] else None
            r.bassline_onset_density, r.bassline_occupancy, warns = bass.bassline(bass_stem, mix, vsr, beats_rel)
            r.bassline_activity = bass.bassline_activity(r.bassline_onset_density, r.bassline_occupancy)
            r.warnings.extend(warns)
        del bass_stem
        intervals = vocals.activity(vocal, mix, vsr)
        if "vocals" in steps:
            r.vocal_density = vocals.density(intervals, region)
        if "structure" in steps:
            r.intro_length, r.outro_length, warn = structure.intro_outro(
                intervals, downbeats, r.music_start, r.music_end)
            if warn:
                r.warnings.append(warn)
    audio = mono = None

    # Output file
    trim_now = args.trim_silence and r.silence_found and not args.dry_run
    work = base
    tmp: Path | None = None
    restore_tags = restore_complex = None
    try:
        if not args.dry_run:
            if trim_now or not in_place:
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = partial_path(target)
                work = tmp
                D(2, f"working file {tmp.name}")
            if trim_now:
                restore_complex, unsupported = tags.read_complex(base)
                if unsupported:
                    r.warnings.append(f"trim drops tag data TagLib cannot copy: {', '.join(unsupported)}")
                silence.trim(base, tmp, r.music_start, r.music_end)
                restore_tags = base_tags
                shift = r.music_start
                r.music_start, r.music_end = 0.0, r.music_end - shift
                if r.first_downbeat is not None:
                    r.first_downbeat -= shift
                if r.tempo_changes:
                    r.tempo_changes = [(max(0.0, a - shift), b) for a, b in r.tempo_changes]
                r.trimmed = True
                D(2, f"timeline shifted by -{shift:.3f}s: music now 0.000s -> {r.music_end:.3f}s")
                if r.first_downbeat is not None:
                    D(2, f"first downbeat now {r.first_downbeat:.3f}s")
                if r.tempo_changes:
                    D(2, "tempo changes now: " + ", ".join(f"{t:.3f}s" for t, _ in r.tempo_changes))
            elif tmp is not None:
                shutil.copy2(base, tmp)

        # Loudness (on the final audio)
        if "loudness" in steps:
            r.rg_gain, r.rg_peak = loudness.replaygain(work)
            info_work = sf.info(str(work))
            r.integrated_loudness, r.loudness_range, warns = loudness.ebur128(
                work, info_work.frames / info_work.samplerate)
            r.warnings.extend(warns)

        # Energy (uses existing tags for inputs not measured in this run)
        if "energy" in steps:
            gain = r.rg_gain if r.rg_gain is not None else tags.number(base_tags, tags.STD_RG_GAIN)
            bright = r.brightness if r.brightness is not None \
                else tags.number(base_tags, tags.ctag("BRIGHTNESS_RAW"))
            onsets = r.onset_density if r.onset_density is not None \
                else tags.number(base_tags, tags.ctag("ONSET_DENSITY_RAW"))
            bpm = r.bpm_exact if r.bpm_exact is not None else tags.number(base_tags, tags.ctag("BPM_EXACT"))
            if None in (gain, bright, onsets, bpm):
                r.warnings.append("energy: missing inputs, not written")
            else:
                r.energy = energy.calc(loudness.lufs_from_gain(gain), bright, onsets, bpm)

        new = tags.build(r, steps)
        tags.validate(new)

        if args.dry_run:
            for k, v in new.items():
                log.info(f"  {k}={v}")
            if args.trim_silence and r.silence_found:
                log.info("  (dry run: would trim silence)")
            return r

        tags.write(work, new, steps, restore_tags, restore_complex)
        if tmp is not None:
            os.replace(tmp, target)
            tmp = None
        log.info(f"  saved: {target}")
        return r
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()
            D(2, "working file removed")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    setup_logging(args.log_file)
    set_debug_levels(args.debug_levels)
    check_tools(args.steps)

    mode = "dry run" if args.dry_run else ("overwrite" if args.overwrite else "copy")
    log.info(f"Input: {args.input}")
    log.info(f"Mode: {mode} | Steps: {','.join(args.steps)} | Tag prefix: {tags.TAG_PREFIX + '_' if tags.TAG_PREFIX else 'none'}")
    if args.debug_levels:
        log.info("Debug: " + ", ".join(f"{k}={v}" for k, v in args.debug_levels.items()))

    tracks, rejected = collect_tracks(args)
    for path, reason in rejected:
        log.warning(f"rejected: {path} ({reason})")
    if not tracks:
        log.error("No tracks to process")
        return 1

    done, skipped, failed, silent = [], [], [], []
    warned: list[tuple[Path, str]] = []
    for i, src in enumerate(tracks, 1):
        log.info(f"[{i}/{len(tracks)}] {src}")
        try:
            with Timer(D, "track"):
                r = process_track(src, args)
            done.append(src)
            if r.silence_found:
                silent.append((src, r))
            for w in r.warnings:
                log.warning(f"  {w}")
                warned.append((src, w))
        except SkipTrack as e:
            log.info(f"  skipped: {e}")
            skipped.append(src)
        except TrackError as e:
            log.error(f"  failed: {e}")
            failed.append((src, str(e)))
        except Exception as e:  # keep going with the next track
            log.exception(f"  failed (unexpected): {e}")
            failed.append((src, f"unexpected: {e}"))

    log.info("=" * 60)
    log.info("SUMMARY")
    log.info(f"Processed: {len(done)} | Skipped: {len(skipped)} | Failed: {len(failed)} | Rejected: {len(rejected)}")
    if silent:
        log.info("Tracks with silence:")
        for src, r in silent:
            log.info(f"  {src.name} ({'trimmed' if r.trimmed else 'not trimmed'})")
    if warned:
        log.info("Warnings:")
        for src, w in warned:
            log.info(f"  {src.name}: {w}")
    if failed:
        log.info("Failed:")
        for src, reason in failed:
            log.info(f"  {src.name}: {reason}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

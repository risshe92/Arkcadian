"""
Musical key (S-KEY). Essentia result is logged for comparison only.
"""

from __future__ import annotations

from common import TrackError, Timer, debugger, device, free_gpu, gpu_memory

STEP = "key"
D = debugger(STEP)

# Settings
MIN_CONFIDENCE = 0.30      # below this, no key is written

# S-KEY labels -> INITIALKEY musical notation
MAJOR = {"A": "A", "Bb": "Bb", "B": "B", "C": "C", "C#": "Db", "D": "D",
         "D#": "Eb", "E": "E", "F": "F", "F#": "F#", "G": "G", "G#": "Ab"}
MINOR = {"A": "Am", "Bb": "Bbm", "B": "Bm", "C": "Cm", "C#": "C#m", "D": "Dm",
         "D#": "Ebm", "E": "Em", "F": "Fm", "F#": "F#m", "G": "Gm", "G#": "G#m"}

_model = None


def _load():
    global _model
    if _model is None:
        import torch
        from skey.key_detection import load_checkpoint, load_model_components
        import contextlib
        import io
        captured = io.StringIO()
        # nnAudio prints setup messages; keep them out of the log unless debugging
        with Timer(D, "load S-KEY"), contextlib.redirect_stdout(captured):
            ckpt = load_checkpoint(None)
            dev = torch.device(device())
            hcqt, chromanet, crop = load_model_components(ckpt, dev)
        D(4, lambda: "nnAudio output:\n" + (captured.getvalue().strip() or "(none)"))
        _model = (ckpt["audio"]["sr"], hcqt, chromanet, crop, dev)
        D(2, f"S-KEY loaded (model sample rate {ckpt['audio']['sr']}, {gpu_memory()})")
    return _model


def detect(mono, sr: int) -> tuple[str, float]:
    """Returns (notation, confidence). Notation is INITIALKEY format, e.g. F#m."""
    import numpy as np
    import soxr
    import torch
    from skey.key_detection import key_map

    model_sr, hcqt, chromanet, crop, dev = _load()
    y = soxr.resample(mono, sr, model_sr) if sr != model_sr else mono
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if peak == 0:
        raise TrackError("key: audio is silent")
    y = (y / peak).astype("float32")
    D(2, f"input {y.size / model_sr:.2f}s at {model_sr} Hz")

    with Timer(D, "key inference"), torch.no_grad():
        x = torch.from_numpy(y)[None, None, :].to(dev)
        probs = torch.mean(chromanet(crop(hcqt(x), torch.zeros(1).to(dev))), dim=0)
    D(3, gpu_memory())
    probs = probs.cpu().numpy()
    free_gpu()

    idx = int(probs.argmax())
    tonic, mode = key_map[idx].split(" ")
    notation = MAJOR[tonic] if mode == "Major" else MINOR[tonic]
    conf = float(probs[idx])

    order = np.argsort(probs)[::-1]
    D(4, lambda: "top 3: " + ", ".join(f"{key_map[int(i)]} {probs[i]:.3f}" for i in order[:3]))
    D(5, lambda: "all: " + ", ".join(f"{key_map[i]} {probs[i]:.3f}" for i in range(len(probs))))
    D(1, f"{notation}, confidence {conf:.2f}")
    _essentia_compare(mono, sr, notation)
    return notation, conf


def _essentia_compare(mono, sr: int, notation: str) -> None:
    """Optional. Logs Essentia's key. Never written to tags."""
    try:
        import essentia.standard as es
        import soxr
    except ImportError:
        D(2, "Essentia not installed, no comparison")
        return
    y = soxr.resample(mono, sr, 44100) if sr != 44100 else mono
    with Timer(D, "Essentia key"):
        k, scale, strength = es.KeyExtractor(profileType="edma")(y.astype("float32"))
    D(1, f"Essentia: {k} {scale} (strength {strength:.2f}), S-KEY: {notation}")

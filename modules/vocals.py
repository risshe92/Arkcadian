"""
Vocal activity and vocal density (Demucs htdemucs vocal stem).

The same Demucs pass also returns the bass stem for modules/bass.py.
"""

from __future__ import annotations

from common import Timer, debugger, device, free_gpu, gpu_memory

STEP = "vocals"
D = debugger(STEP)

# Settings
MODEL_NAME = "htdemucs"
FRAME = 2048
HOP = 1024
ABS_DB = -45.0          # vocal stem must be louder than this (dBFS)
REL_DB = -12.0          # and no more than this far below the mix
MIN_RUN_S = 0.5         # ignore vocal blips shorter than this

_model = None


def _load():
    global _model
    if _model is None:
        from demucs.pretrained import get_model
        with Timer(D, "load Demucs"):
            _model = get_model(MODEL_NAME)
            _model.to(device()).eval()
        D(2, f"Demucs {MODEL_NAME} loaded ({gpu_memory()})")
    return _model


def separate(audio, sr: int):
    """Returns (vocal stem, bass stem, mix, sample rate). Stems and mix are mono float32.

    One Demucs pass gives all stems. The bass stem is taken from the same
    output, so vocal results are unchanged and the model runs only once.
    """
    import numpy as np
    import soxr
    import torch
    from demucs.apply import apply_model

    model = _load()
    wav = soxr.resample(audio, sr, model.samplerate) if sr != model.samplerate else audio
    if wav.shape[1] == 1:
        wav = np.repeat(wav, 2, axis=1)
    elif wav.shape[1] > 2:
        wav = wav[:, :2]
    D(2, f"input {wav.shape[0] / model.samplerate:.2f}s at {model.samplerate} Hz")

    t = torch.from_numpy(np.ascontiguousarray(wav.T)).float()
    ref = t.mean(0)
    t = (t - ref.mean()) / (ref.std() + 1e-8)
    with Timer(D, "separation"), torch.no_grad():
        # shifts=0: no random time shift, so the same track always gives the same result
        out = apply_model(model, t[None], shifts=0, device=device(), split=True, overlap=0.25,
                          progress=False)[0]
    D(3, gpu_memory())
    out = out * (ref.std() + 1e-8) + ref.mean()
    vocal = out[model.sources.index("vocals")].mean(0).cpu().numpy().astype("float32")
    bass = out[model.sources.index("bass")].mean(0).cpu().numpy().astype("float32")
    mix = wav.mean(axis=1).astype("float32")
    del out, t
    free_gpu()
    return vocal, bass, mix, model.samplerate


def activity(vocal, mix, sr: int) -> list[tuple[float, float]]:
    """Vocal-active intervals in seconds, relative to the start of the audio."""
    import librosa
    import numpy as np
    D(2, f"thresholds: vocal > {ABS_DB} dBFS and > mix {REL_DB} dB, min run {MIN_RUN_S}s")

    v = librosa.feature.rms(y=vocal, frame_length=FRAME, hop_length=HOP)[0]
    m = librosa.feature.rms(y=mix, frame_length=FRAME, hop_length=HOP)[0]
    n = min(v.size, m.size)
    v_db = 20 * np.log10(np.maximum(v[:n], 1e-10))
    m_db = 20 * np.log10(np.maximum(m[:n], 1e-10))
    active = (v_db > ABS_DB) & (v_db - m_db > REL_DB)
    D(4, lambda: f"{n} frames, {int(active.sum())} active before smoothing")
    D(5, lambda: "vocal dB per frame: " + ", ".join(f"{x:.1f}" for x in v_db))

    frame_s = HOP / sr
    min_frames = max(1, int(round(MIN_RUN_S / frame_s)))
    intervals = []
    i = 0
    while i < n:
        if active[i]:
            j = i
            while j < n and active[j]:
                j += 1
            if j - i >= min_frames:
                intervals.append((i * frame_s, j * frame_s))
            i = j
        else:
            i += 1
    D(3, f"{len(intervals)} vocal interval(s)")
    D(5, lambda: "\n".join(f"vocal {a:.3f}s -> {b:.3f}s" for a, b in intervals) or "none")
    return intervals


def density(intervals: list[tuple[float, float]], region_s: float) -> float:
    sung = sum(b - a for a, b in intervals)
    value = min(1.0, sung / region_s) if region_s > 0 else 0.0
    D(1, f"vocal density {value:.3f} ({sung:.1f}s of {region_s:.1f}s)")
    return value

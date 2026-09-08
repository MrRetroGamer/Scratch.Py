"""Music extension: synthesized instruments and drums (numpy -> pygame buffers)."""

from __future__ import annotations

import numpy as np

SAMPLE_RATE = 44100

_INSTRUMENTS = {
    1: ("saw", 0.02, 1.4, 0.35, 0.25),
    2: ("sine2", 0.01, 0.9, 0.3, 0.2),
    3: ("organ", 0.02, 0.05, 0.9, 0.15),
    4: ("saw", 0.005, 0.8, 0.25, 0.2),
    5: ("saw", 0.08, 0.08, 0.85, 0.3),
    6: ("square", 0.03, 0.5, 0.5, 0.2),
    7: ("square", 0.008, 0.6, 0.6, 0.12),
    8: ("tri", 0.01, 0.7, 0.4, 0.18),
    9: ("sine2", 0.015, 0.6, 0.45, 0.22),
    10: ("tri", 0.02, 1.0, 0.4, 0.25),
    11: ("saw", 0.06, 0.06, 0.8, 0.28),
    12: ("brass", 0.05, 0.1, 0.8, 0.25),
    13: ("brass", 0.04, 0.09, 0.82, 0.24),
    14: ("sine2", 0.01, 1.2, 0.3, 0.3),
    15: ("sine3", 0.01, 1.0, 0.35, 0.3),
    16: ("organ", 0.03, 0.04, 0.95, 0.12),
    17: ("saw", 0.02, 0.9, 0.4, 0.2),
    18: ("sine2", 0.02, 0.7, 0.5, 0.25),
    19: ("sine3", 0.015, 0.9, 0.4, 0.28),
    20: ("tri", 0.012, 0.8, 0.42, 0.22),
    21: ("sine2", 0.02, 1.1, 0.36, 0.26),
}

_DRUM_KINDS = [
    "snare", "kick", "sidestick", "crash", "openhat", "closedhat",
    "tambourine", "clap", "claves", "woodblock", "cowbell", "triangle",
    "bongo", "conga", "cabasa", "guiro", "vibraslap", "cuica",
]


def _wave(kind: str, phase: np.ndarray) -> np.ndarray:
    if kind == "sine":
        return np.sin(phase)
    if kind == "sine2":
        return 0.7 * np.sin(phase) + 0.3 * np.sin(2 * phase)
    if kind == "sine3":
        return 0.6 * np.sin(phase) + 0.25 * np.sin(2 * phase) + 0.15 * np.sin(3 * phase)
    if kind == "square":
        return np.sign(np.sin(phase)) * 0.6
    if kind == "saw":
        return 2.0 * ((phase / (2 * np.pi)) % 1.0) - 1.0
    if kind == "tri":
        return 2.0 * np.abs(2.0 * ((phase / (2 * np.pi)) % 1.0) - 1.0) - 1.0
    if kind == "organ":
        return (
            0.4 * np.sin(phase)
            + 0.3 * np.sin(2 * phase)
            + 0.2 * np.sin(3 * phase)
            + 0.1 * np.sin(4 * phase)
        )
    if kind == "brass":
        return 0.6 * np.sin(phase) + 0.4 * np.sin(2 * phase + 0.4)
    return np.sin(phase)


def _adsr(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    env = np.full(n, float(s), dtype=np.float64)
    ai = max(1, min(int(a * SAMPLE_RATE), n))
    env[:ai] = np.linspace(0.0, 1.0, ai)
    di = int(d * SAMPLE_RATE)
    if di > 0 and ai < n:
        d_end = min(ai + di, n)
        env[ai:d_end] = np.linspace(1.0, float(s), d_end - ai)
    ri = int(r * SAMPLE_RATE)
    if ri > 0:
        ri = min(ri, n)
        env[n - ri:] *= np.linspace(1.0, 0.0, ri)
    return env


def render_note(instrument: int, midi_note: int, seconds: float) -> np.ndarray:
    kind, a, d, s, r = _INSTRUMENTS.get(int(instrument), _INSTRUMENTS[1])
    seconds = max(0.03, min(seconds, 8.0))
    n = int(SAMPLE_RATE * seconds)
    t = np.arange(n) / SAMPLE_RATE
    freq = 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
    phase = 2 * np.pi * freq * t
    wave = _wave(kind, phase)
    if kind == "saw" and instrument in (5, 11):
        vibrato = 1.0 + 0.006 * np.sin(2 * np.pi * 5.5 * t)
        wave = _wave(kind, phase * vibrato)
    env = _adsr(n, a, d, s, r)
    samples = wave * env * 0.5

    if instrument == 1:
        decay = np.exp(-t * 2.2)
        samples *= decay
    elif instrument == 4:
        samples *= np.exp(-t * 2.8)
    return np.clip(samples, -1.0, 1.0)


def _noise(n: int) -> np.ndarray:
    rng = np.random.default_rng()
    return rng.uniform(-1, 1, n)


def _tone_sweep(n: int, f_start: float, f_end: float) -> np.ndarray:
    freqs = np.linspace(f_start, f_end, n)
    phases = 2 * np.pi * np.cumsum(freqs) / SAMPLE_RATE
    return np.sin(phases)


def render_drum(drum: int, seconds: float) -> np.ndarray:
    drum = ((int(drum) - 1) % len(_DRUM_KINDS))
    kind = _DRUM_KINDS[drum]
    seconds = max(0.05, min(max(seconds, 0.2), 2.0))
    n = int(SAMPLE_RATE * seconds)
    t = np.arange(n) / SAMPLE_RATE
    noise = _noise(n)

    if kind == "snare":
        body = _tone_sweep(n, 190, 120) * np.exp(-t * 22)
        snap = noise * np.exp(-t * 26) * 0.9
        samples = body * 0.7 + snap
    elif kind == "kick":
        sweep = _tone_sweep(n, 150, 45)
        samples = sweep * np.exp(-t * 13)
    elif kind == "sidestick":
        click = noise * np.exp(-t * 90)
        tone = np.sin(2 * np.pi * 1700 * t) * np.exp(-t * 60)
        samples = click * 0.6 + tone * 0.5
    elif kind == "crash":
        hp = noise - np.convolve(noise, np.ones(24) / 24, mode="same")
        samples = hp * np.exp(-t * 3.2)
    elif kind == "openhat":
        hp = noise - np.convolve(noise, np.ones(20) / 20, mode="same")
        samples = hp * np.exp(-t * 9)
    elif kind == "closedhat":
        hp = noise - np.convolve(noise, np.ones(16) / 16, mode="same")
        samples = hp * np.exp(-t * 38)
    elif kind == "tambourine":
        jingles = (noise * 0.5 + np.sin(2 * np.pi * 6000 * t) * 0.5) * np.exp(-t * 20)
        samples = jingles
    elif kind == "clap":
        bursts = np.zeros(n)
        for offset in (0, 0.012, 0.024, 0.04):
            i0 = int(offset * SAMPLE_RATE)
            length = n - i0
            if length <= 0:
                continue
            bursts[i0:] += noise[:length] * np.exp(-np.arange(length) / SAMPLE_RATE * 30) * 0.6
        samples = bursts
    elif kind == "claves":
        samples = np.sin(2 * np.pi * 2500 * t) * np.exp(-t * 40)
    elif kind == "woodblock":
        samples = np.sin(2 * np.pi * 1000 * t) * np.exp(-t * 45)
    elif kind == "cowbell":
        a = np.sin(2 * np.pi * 560 * t)
        b = np.sin(2 * np.pi * 845 * t)
        samples = (a + b) * 0.5 * np.exp(-t * 14)
    elif kind == "triangle":
        samples = np.sin(2 * np.pi * 4500 * t) * np.exp(-t * 8)
    elif kind == "bongo":
        samples = _tone_sweep(n, 420, 300) * np.exp(-t * 24)
    elif kind == "conga":
        samples = _tone_sweep(n, 320, 220) * np.exp(-t * 18)
    elif kind == "cabasa":
        samples = (noise * 0.4 + np.sin(2 * np.pi * 3000 * t) * 0.2) * np.exp(-t * 16)
    elif kind == "guiro":
        modulator = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 28 * t))
        samples = noise * modulator * np.exp(-t * 6)
    elif kind == "vibraslap":
        rattle = noise * (0.5 + 0.5 * np.sin(2 * np.pi * 60 * t)) * np.exp(-t * 10)
        tone = np.sin(2 * np.pi * 700 * t) * np.exp(-t * 10)
        samples = rattle * 0.7 + tone * 0.3
    else:
        samples = _tone_sweep(n, 400, 500) * np.exp(-t * 20)

    peak = float(np.max(np.abs(samples))) or 1.0
    samples = samples / peak
    fade_n = min(int(0.01 * SAMPLE_RATE), n)
    if fade_n > 0:
        samples[-fade_n:] *= np.linspace(1, 0, fade_n)
    return np.clip(samples, -1.0, 1.0)


def to_sound_array(mono: np.ndarray) -> np.ndarray:

    pcm = (mono * 32767).astype(np.int16)
    stereo = np.ascontiguousarray(np.column_stack((pcm, pcm)))
    return stereo

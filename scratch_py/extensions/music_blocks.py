"""Music extension blocks."""

from __future__ import annotations

from ..blocks import api, command, reporter
from ..util import jscompat as cast
from . import music as synth

_NOTE_NAMES = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}


def _note_to_midi(value) -> int:
    text = cast.to_string(value).strip()
    if text and (text[0].isalpha()):
        name = _NOTE_NAMES.get(text[0].lower())
        if name is not None:
            rest = text[1:]
            sharp = False
            flat = False
            while rest and rest[0] in "#b":
                if rest[0] == "#":
                    sharp = True
                else:
                    flat = True
                rest = rest[1:]
            octave = cast.to_number(rest) if rest else 4
            midi = 12 * (int(octave) + 1) + name + (1 if sharp else 0) - (1 if flat else 0)
            return max(21, min(108, midi))
    num = int(cast.js_round(cast.to_number(text)))
    return max(21, min(108, num))


@command("music_playDrum")
def play_drum(rt, tgt, block):
    drum = int(cast.js_round(cast.to_number(api.val(rt, tgt, block, "DRUM", 1))))
    beats = max(0.0, cast.to_number(api.val(rt, tgt, block, "BEATS", 1)))
    seconds = beats * 60.0 / rt.tempo
    handle = None
    if rt.audio:
        samples = synth.render_drum(drum, seconds)
        handle = rt.audio.play_buffer(samples, tgt.volume / 100.0)
    if handle is not None:
        while rt.audio.is_playing(handle):
            yield


@command("music_playNote")
def play_note(rt, tgt, block):
    midi = _note_to_midi(api.val(rt, tgt, block, "NOTE", 60))
    beats = max(0.0, cast.to_number(api.val(rt, tgt, block, "BEATS", 0.25)))
    seconds = beats * 60.0 / rt.tempo
    instrument = getattr(rt, "instrument", 1)
    handle = None
    if rt.audio:
        samples = synth.render_note(instrument, midi, max(seconds, 0.05))
        handle = rt.audio.play_buffer(samples, tgt.volume / 100.0)
        if handle is not None:
            while rt.audio.is_playing(handle):
                yield
            return
    yield from _sleep(rt, seconds)


def _sleep(rt, seconds: float):

    start = rt.now()
    while rt.now() - start < seconds:
        yield


@command("music_setInstrument")
def set_instrument(rt, tgt, block):
    value = int(cast.js_round(cast.to_number(api.val(rt, tgt, block, "INSTRUMENT", 1))))
    rt.instrument = max(1, min(21, value))


@command("music_setTempo")
def set_tempo(rt, tgt, block):
    rt.tempo = max(20.0, cast.to_number(api.val(rt, tgt, block, "TEMPO", 60)))


@command("music_changeTempoBy")
def change_tempo_by(rt, tgt, block):
    rt.tempo = max(20.0, rt.tempo + cast.to_number(api.val(rt, tgt, block, "TEMPO", 0)))


@reporter("music_getTempo")
def get_tempo(rt, tgt, block):
    return rt.tempo

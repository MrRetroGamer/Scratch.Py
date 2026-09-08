from __future__ import annotations

import math

from ..util import jscompat as cast
from . import api, command, reporter


def _sound_index(rt, tgt, value) -> int | None:
    name = cast.to_string(value)
    for i, sound in enumerate(tgt.data.sounds):
        if sound.name == name:
            return i
    n = cast.to_number(value)
    if not math.isnan(n):
        idx = int(n)
        if 0 <= idx < len(tgt.data.sounds):
            return idx
    return None


@command("sound_play")
def sound_play(rt, tgt, block):
    value = api.val(rt, tgt, block, "SOUND_MENU")
    idx = _sound_index(rt, tgt, value)
    if idx is not None and rt.audio:
        rt.audio.play(tgt, idx)


@command("sound_playuntildone")
def sound_playuntildone(rt, tgt, block):
    value = api.val(rt, tgt, block, "SOUND_MENU")
    idx = _sound_index(rt, tgt, value)
    if idx is not None and rt.audio:
        channel = rt.audio.play(tgt, idx)
        if channel is not None:
            while rt.audio.is_playing(channel):
                yield


@command("sound_stopallsounds")
def stopallsounds(rt, tgt, block):
    if rt.audio:
        rt.audio.stop_all()


@command("sound_setvolumeto")
def setvolumeto(rt, tgt, block):
    tgt.volume = max(0.0, min(100.0, cast.to_number(api.val(rt, tgt, block, "VOLUME", 100))))


@command("sound_changevolumeby")
def changevolumeby(rt, tgt, block):
    tgt.volume = max(0.0, min(100.0, tgt.volume + cast.to_number(api.val(rt, tgt, block, "VOLUME", 0))))


@reporter("sound_volume")
def volume_reporter(rt, tgt, block):
    return tgt.volume

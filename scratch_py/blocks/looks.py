from __future__ import annotations

import math
import random

from ..util import jscompat as cast
from . import api, command, reporter

EFFECT_MAP = {
    "COLOR": "color",
    "COLOUR": "color",
    "FISHEYE": "fisheye",
    "WHIRL": "whirl",
    "MOSAIC": "mosaic",
    "PIXELATE": "pixelate",
    "BRIGHTNESS": "brightness",
    "GHOST": "ghost",
    "SATURATION": "saturation",
}


def _costume_index(rt, tgt, value) -> int:
    costumes = tgt.data.costumes
    if not costumes:
        return 0
    text = cast.to_string(value)
    for i, c in enumerate(costumes):
        if c.name == text:
            return i
    num = cast.to_number(value)
    if not math.isnan(num):
        idx = int(cast.js_round(num))
        count = len(costumes)
        return (idx - 1) % count
    return tgt.current_costume % len(costumes)


@command("looks_say")
def say(rt, tgt, block):
    tgt.say_text = api.text(rt, tgt, block, "MESSAGE")
    tgt.say_style = "say"


@command("looks_think")
def think(rt, tgt, block):
    tgt.say_text = api.text(rt, tgt, block, "MESSAGE")
    tgt.say_style = "think"


@command("looks_sayforsecs")
def sayforsecs(rt, tgt, block):
    message = api.text(rt, tgt, block, "MESSAGE")
    duration = max(0.0, cast.to_number(api.val(rt, tgt, block, "SECS", 0)))
    tgt.say_text = message
    tgt.say_style = "say"
    start = rt.now()
    yield
    while rt.now() - start < duration:
        yield
    if tgt.say_text == message:
        tgt.say_text = None


@command("looks_thinkforsecs")
def thinkforsecs(rt, tgt, block):
    message = api.text(rt, tgt, block, "MESSAGE")
    duration = max(0.0, cast.to_number(api.val(rt, tgt, block, "SECS", 0)))
    tgt.say_text = message
    tgt.say_style = "think"
    start = rt.now()
    yield
    while rt.now() - start < duration:
        yield
    if tgt.say_text == message:
        tgt.say_text = None


@command("looks_switchcostumeto")
def switchcostumeto(rt, tgt, block):
    value = api.val(rt, tgt, block, "COSTUME")
    if value is None:
        entry = block.fields.get("COSTUME")
        value = entry[0] if entry else ""
    tgt.current_costume = _special_costume_index(tgt, value)


def _special_costume_index(tgt, value) -> int:
    costumes = tgt.data.costumes
    if not costumes:
        return 0
    text = cast.to_string(value).lower()
    if text == "next costume":
        return (tgt.current_costume + 1) % len(costumes)
    if text == "previous costume":
        return (tgt.current_costume - 1) % len(costumes)
    if text == "random costume":
        return random.randrange(len(costumes))
    return _costume_index(tgt.rt, tgt, value)


@command("looks_nextcostume")
def nextcostume(rt, tgt, block):
    if tgt.data.costumes:
        tgt.current_costume = (tgt.current_costume + 1) % len(tgt.data.costumes)


@command("looks_switchbackdropto")
def switchbackdropto(rt, tgt, block):
    stage = rt.stage
    value = api.val(rt, tgt, block, "BACKDROP")
    if value is None:
        entry = block.fields.get("BACKDROP")
        value = entry[0] if entry else ""
    count = len(stage.data.costumes)
    if not count:
        return
    text = cast.to_string(value).lower()
    if text == "next backdrop":
        stage.current_costume = (stage.current_costume + 1) % count
    elif text == "previous backdrop":
        stage.current_costume = (stage.current_costume - 1) % count
    elif text == "random backdrop":
        stage.current_costume = random.randrange(count)
    else:
        stage.current_costume = _costume_index(rt, stage, value) % count
    name = stage.data.costumes[stage.current_costume].name
    rt.fire_backdrop_switch(name)


@command("looks_nextbackdrop")
def nextbackdrop(rt, tgt, block):
    stage = rt.stage
    count = len(stage.data.costumes)
    if not count:
        return
    stage.current_costume = (stage.current_costume + 1) % count
    name = stage.data.costumes[stage.current_costume].name
    rt.fire_backdrop_switch(name)


@command("looks_changesizeby")
def changesizeby(rt, tgt, block):
    tgt.size = _clamp_size(tgt.size + cast.to_number(api.val(rt, tgt, block, "CHANGE", 0)))


@command("looks_setsizeto")
def setsizeto(rt, tgt, block):
    tgt.size = _clamp_size(cast.to_number(api.val(rt, tgt, block, "SIZE", 100)))


def _clamp_size(value: float) -> float:
    return max(5.0, min(535.0, float(value)))


@command("looks_changeeffectby")
def changeeffectby(rt, tgt, block):
    key = EFFECT_MAP.get(api.fld(block, "EFFECT").upper())
    if key:
        tgt.change_effect(key, cast.to_number(api.val(rt, tgt, block, "CHANGE", 0)))


@command("looks_seteffectto")
def seteffectto(rt, tgt, block):
    key = EFFECT_MAP.get(api.fld(block, "EFFECT").upper())
    if key:
        tgt.set_effect(key, cast.to_number(api.val(rt, tgt, block, "VALUE", 0)))


@command("looks_cleargraphiceffects")
def cleargraphiceffects(rt, tgt, block):
    for key in tgt.effects:
        tgt.effects[key] = 0.0


@command("looks_show")
def show(rt, tgt, block):
    tgt.visible = True


@command("looks_hide")
def hide(rt, tgt, block):
    tgt.visible = False


@command("looks_gotofrontback")
def gotofrontback(rt, tgt, block):
    layer = api.fld(block, "LAYER")
    if tgt in rt.draw_order:
        rt.draw_order.remove(tgt)
    if layer == "back":
        rt.draw_order.insert(0, tgt)
    else:
        rt.draw_order.append(tgt)


@command("looks_goforwardbackwardlayers")
def goforwardbackwardlayers(rt, tgt, block):
    raw = api.val(rt, tgt, block, "NUM", 0)
    amount = int(cast.js_round(cast.to_number(raw)))
    direction = api.fld(block, "FORWARD_BACKWARD")
    if tgt not in rt.draw_order:
        return
    idx = rt.draw_order.index(tgt)
    rt.draw_order.remove(tgt)
    if direction == "forward":
        idx += amount
    else:
        idx -= amount
    idx = max(0, min(len(rt.draw_order), idx))
    rt.draw_order.insert(idx, tgt)


@reporter("looks_size")
def size_reporter(rt, tgt, block):
    return tgt.size


@reporter("looks_costumenumbername")
def costumenumbername(rt, tgt, block):
    which = api.text(rt, tgt, block, "NUMBER_NAME", "number").lower()
    if which == "name":
        costume = tgt.costume()
        return costume.name if costume else ""
    return tgt.current_costume + 1


@reporter("looks_backdropnumbername")
def backdropnumbername(rt, tgt, block):
    stage = rt.stage
    which = api.text(rt, tgt, block, "NUMBER_NAME", "number").lower()
    if which == "name":
        costume = stage.costume()
        return costume.name if costume else ""
    return stage.current_costume + 1

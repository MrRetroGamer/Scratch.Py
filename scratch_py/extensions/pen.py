"""Pen extension: HSV-tracked pen state + drawing through the renderer."""

from __future__ import annotations

import colorsys

from ..blocks import api, command
from ..util import jscompat as cast

DEFAULT_RGB = (136.0, 51.0, 255.0)


def hsv_to_rgb(h_deg: float, s_pct: float, v_pct: float):
    r, g, b = colorsys.hsv_to_rgb((h_deg % 360.0) / 360.0, max(0.0, min(1.0, s_pct / 100.0)), max(0.0, min(1.0, v_pct / 100.0)))
    return (r * 255.0, g * 255.0, b * 255.0)


def rgb_to_hsv(rgb):

    r, g, b = [c / 255.0 for c in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return (h * 360.0, s * 100.0, v * 100.0)


def _sync_from_rgb(pen):
    h, s, v = rgb_to_hsv(pen["rgb"])
    pen["hue"] = h / 3.6
    pen["saturation"] = s
    pen["brightness"] = v


def _sync_from_hsv(pen):
    pen["rgb"] = hsv_to_rgb(pen["hue"] * 3.6, pen["saturation"], pen["brightness"])


@command("pen_clear")
def pen_clear(rt, tgt, block):
    if rt.renderer:
        rt.renderer.pen_clear()


@command("pen_penDown")
def pen_down(rt, tgt, block):
    tgt.pen["down"] = True
    rt._pen_prev[id(tgt)] = (tgt.x, tgt.y)


@command("pen_penUp")
def pen_up(rt, tgt, block):
    tgt.pen["down"] = False


@command("pen_setPenColorToColor")
def set_color_to_color(rt, tgt, block):
    raw = api.val(rt, tgt, block, "COLOR")
    rgb = _parse_color_arg(raw)
    if rgb is None:
        return
    tgt.pen["rgb"] = rgb
    tgt.pen["transparency"] = 0.0
    _sync_from_rgb(tgt.pen)


def _parse_color_arg(value):
    if value is None:
        return None
    text = cast.to_string(value).strip()
    if text.startswith("#"):
        hexpart = text[1:]
        if len(hexpart) >= 6:
            try:
                return (
                    float(int(hexpart[0:2], 16)),
                    float(int(hexpart[2:4], 16)),
                    float(int(hexpart[4:6], 16)),
                )
            except ValueError:
                return None
        return None
    num = int(cast.to_number(value))
    if num > 0xFFFFFF:
        num &= 0xFFFFFF
    return (float((num >> 16) & 255), float((num >> 8) & 255), float(num & 255))


@command("pen_setPenColorParamTo")
def set_param(rt, tgt, block):
    _change_param(rt, tgt, block, api.fld(block, "COLOR_PARAM"), api.val(rt, tgt, block, "VALUE", 0), absolute=True)


@command("pen_changePenColorParamBy")
def change_param(rt, tgt, block):
    _change_param(rt, tgt, block, api.fld(block, "COLOR_PARAM"), api.val(rt, tgt, block, "VALUE", 0), absolute=False)


def _change_param(rt, tgt, block, param, value, absolute: bool):
    pen = tgt.pen
    amount = cast.to_number(value)
    key = param.lower()
    current = {
        "color": lambda: pen["hue"],
        "saturation": lambda: pen["saturation"],
        "brightness": lambda: pen["brightness"],
        "transparency": lambda: pen["transparency"],
    }.get(key)
    if current is None:
        return
    new_value = amount if absolute else current() + amount
    if key == "color":
        pen["hue"] = new_value % 100.0
    elif key == "transparency":
        pen["transparency"] = max(0.0, min(100.0, new_value))
    else:
        setattr_like(pen, key, max(0.0, min(100.0, new_value)))
    _sync_from_hsv(pen)


def setattr_like(pen, key, value):
    pen[key] = value


@command("pen_setPenSizeTo")
def set_size(rt, tgt, block):
    tgt.pen["size"] = max(1.0, min(1200.0, cast.to_number(api.val(rt, tgt, block, "SIZE", 1))))


@command("pen_changePenSizeBy")
def change_size(rt, tgt, block):
    delta = cast.to_number(api.val(rt, tgt, block, "SIZE", 0))
    tgt.pen["size"] = max(1.0, min(1200.0, tgt.pen["size"] + delta))


@command("pen_stamp")
def stamp(rt, tgt, block):
    if rt.renderer:
        rt.renderer.stamp_sprite(tgt)

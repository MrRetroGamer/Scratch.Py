from __future__ import annotations

from datetime import datetime

from ..util import jscompat as cast
from . import api, boolean, command, reporter


@boolean("sensing_touchingobject")
def touchingobject(rt, tgt, block):
    what = api.text(rt, tgt, block, "TOUCHINGOBJECTMENU")
    if rt.renderer is None:
        return False
    if what == "_mouse_":
        return rt.renderer.touching_point(tgt, rt.renderer.mouse_x(), rt.renderer.mouse_y())
    if what == "_edge_":
        bounds = rt.sprite_bounds(tgt)
        if bounds is None:
            return False
        left, right, top, bottom = bounds
        return left <= -240 or right >= 240 or top >= 180 or bottom <= -180
    other = rt.find_target_by_name(what)
    if other is None:
        return False
    for o in rt.targets_with_name(what):
        if o is tgt:
            continue
        if rt.renderer.sprites_touching(tgt, o):
            return True
    return False


@boolean("sensing_touchingcolor")
def touchingcolor(rt, tgt, block):
    if rt.renderer is None:
        return False
    color = _parse_color(api.val(rt, tgt, block, "COLOR"))
    if color is None:
        return False
    return rt.renderer.touching_color(tgt, color)


@boolean("sensing_coloristouchingcolor")
def coloristouchingcolor(rt, tgt, block):
    if rt.renderer is None:
        return False
    c1 = _parse_color(api.val(rt, tgt, block, "COLOR1"))
    c2 = _parse_color(api.val(rt, tgt, block, "COLOR2"))
    if c1 is None or c2 is None:
        return False
    return rt.renderer.color_touching_color(tgt, c1, c2)


def _parse_color(value):
    if value is None:
        return None
    text = cast.to_string(value).strip()
    if text.startswith("#"):
        text = text[1:]
        try:
            return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
        except ValueError:
            return None
    num = cast.to_number(value)
    num = int(num) & 0xFFFFFF
    return ((num >> 16) & 255, (num >> 8) & 255, num & 255)


@reporter("sensing_distanceto")
def distanceto(rt, tgt, block):
    what = api.text(rt, tgt, block, "DISTANCETOMENU")
    if what == "_mouse_":
        if rt.renderer:
            mx, my = rt.renderer.mouse_x(), rt.renderer.mouse_y()
        else:
            mx, my = 0.0, 0.0
    else:
        best = None
        best_d = None
        for o in rt.targets_with_name(what):
            dx = tgt.x - o.x
            dy = tgt.y - o.y
            d = dx * dx + dy * dy
            if best_d is None or d < best_d:
                best_d = d
                best = o
        if best is None:
            return 10000.0
        mx, my = best.x, best.y
    dx = tgt.x - mx
    dy = tgt.y - my
    return (dx * dx + dy * dy) ** 0.5


@command("sensing_askandwait")
def askandwait(rt, tgt, block):
    question = api.text(rt, tgt, block, "QUESTION")
    tgt.say_text = "..."
    tgt.say_style = "say"
    token = rt.ask(question)
    try:
        while not token["done"]:
            yield
    finally:
        if tgt.say_text == "...":
            tgt.say_text = None
            tgt.say_style = None


@reporter("sensing_answer")
def answer(rt, tgt, block):
    return rt.answer


@boolean("sensing_keypressed")
def keypressed(rt, tgt, block):
    key = api.text(rt, tgt, block, "KEY_OPTION").lower()
    if key == "any":
        return bool(rt.keys_held)
    return key in rt.keys_held


@boolean("sensing_mousedown")
def mousedown(rt, tgt, block):
    return rt.mouse_down


@reporter("sensing_mousex")
def mousex(rt, tgt, block):
    return rt.renderer.mouse_x() if rt.renderer else 0


@reporter("sensing_mousey")
def mousey(rt, tgt, block):
    return rt.renderer.mouse_y() if rt.renderer else 0


@reporter("sensing_loudness")
def loudness(rt, tgt, block):
    return rt.loudness


@reporter("sensing_timer")
def timer(rt, tgt, block):
    return round(rt.timer_value(), 4)


@command("sensing_resettimer")
def resettimer(rt, tgt, block):
    rt.reset_timer()


@reporter("sensing_of")
def of_block(rt, tgt, block):
    attribute = api.fld(block, "PROPERTY").lower()
    obj_name = api.fld(block, "OBJECT")
    target = rt.stage if obj_name in ("_stage_", "Stage") else rt.find_target_by_name(obj_name)
    if target is None:
        return ""
    table = {
        "x position": lambda t: t.x,
        "y position": lambda t: t.y,
        "direction": lambda t: t.direction,
        "costume #": lambda t: t.current_costume + 1,
        "costume name": lambda t: t.costume().name if t.costume() else "",
        "size": lambda t: t.size,
        "volume": lambda t: t.volume,
        "backdrop #": lambda t: t.current_costume + 1,
        "backdrop name": lambda t: t.costume().name if t.costume() else "",
    }
    fn = table.get(attribute)
    if fn is None:
        for entry in target.variables.values():
            if entry[0].lower() == attribute:
                return entry[1]
        return ""
    if attribute in ("x position", "y position", "direction", "costume #", "size") and target.is_stage:
        return ""
    return fn(target)


@reporter("sensing_current")
def current_block(rt, tgt, block):
    menu = api.fld(block, "CURRENTMENU").upper()
    now = datetime.now()
    table = {
        "YEAR": now.year,
        "MONTH": now.month,
        "DATE": now.day,
        "DAYOFWEEK": (now.isoweekday() % 7) + 1,
        "HOUR": now.hour,
        "MINUTE": now.minute,
        "SECOND": now.second,
    }
    return table.get(menu, 0)


@reporter("sensing_dayssince2000")
def dayssince2000(rt, tgt, block):
    epoch = datetime(2000, 1, 1)
    delta = datetime.now() - epoch
    return delta.total_seconds() / 86400.0


@reporter("sensing_username")
def username(rt, tgt, block):
    return rt.username

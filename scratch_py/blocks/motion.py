from __future__ import annotations

from ..util import jscompat as cast
from . import api, command, reporter


def _resolve_target_xy(rt, tgt, menu_value):
    if menu_value == "_mouse_":
        if rt.renderer:
            return rt.renderer.mouse_x(), rt.renderer.mouse_y()
        return 0.0, 0.0
    other = rt.find_target_by_name(menu_value)
    if other is not None:
        return other.x, other.y
    return tgt.x, tgt.y


@command("motion_movesteps")
def movesteps(rt, tgt, block):
    old_x, old_y = tgt.x, tgt.y
    tgt.move_steps(cast.to_number(api.val(rt, tgt, block, "STEPS", 0)))
    rt.pen_move(tgt, old_x, old_y)


@command("motion_turnright")
def turnright(rt, tgt, block):
    tgt.point_in_direction(tgt.direction + cast.to_number(api.val(rt, tgt, block, "DEGREES", 0)))


@command("motion_turnleft")
def turnleft(rt, tgt, block):
    tgt.point_in_direction(tgt.direction - cast.to_number(api.val(rt, tgt, block, "DEGREES", 0)))


@command("motion_pointindirection")
def pointindirection(rt, tgt, block):
    tgt.point_in_direction(cast.to_number(api.val(rt, tgt, block, "DIRECTION", 90)))


@command("motion_pointtowards")
def pointtowards(rt, tgt, block):
    x, y = _resolve_nearest_xy(rt, tgt, api.text(rt, tgt, block, "TOWARDS"))
    tgt.point_towards_xy(x, y)


def _resolve_nearest_xy(rt, tgt, menu_value):
    if menu_value == "_mouse_":
        if rt.renderer:
            return rt.renderer.mouse_x(), rt.renderer.mouse_y()
        return 0.0, 0.0
    best = None
    best_d = None
    for other in rt.targets_with_name(menu_value):
        if other is tgt:
            continue
        dx = other.x - tgt.x
        dy = other.y - tgt.y
        d = dx * dx + dy * dy
        if best_d is None or d < best_d:
            best_d = d
            best = other
    if best is not None:
        return best.x, best.y
    return tgt.x, tgt.y


@command("motion_gotoxy")
def gotoxy(rt, tgt, block):
    old_x, old_y = tgt.x, tgt.y
    tgt.x = cast.to_number(api.val(rt, tgt, block, "X", 0))
    tgt.y = cast.to_number(api.val(rt, tgt, block, "Y", 0))
    rt.pen_move(tgt, old_x, old_y)


@command("motion_goto")
def goto(rt, tgt, block):
    what = api.text(rt, tgt, block, "TO")
    if what == "_random_":
        import random

        old_x, old_y = tgt.x, tgt.y
        tgt.x = random.uniform(-240, 240)
        tgt.y = random.uniform(-180, 180)
        rt.pen_move(tgt, old_x, old_y)
    elif what == "_mouse_" and rt.renderer:
        old_x, old_y = tgt.x, tgt.y
        tgt.x = rt.renderer.mouse_x()
        tgt.y = rt.renderer.mouse_y()
        rt.pen_move(tgt, old_x, old_y)
    elif what != "_myself_":
        other = rt.find_target_by_name(what)
        if other is not None:
            old_x, old_y = tgt.x, tgt.y
            tgt.x, tgt.y = other.x, other.y
            rt.pen_move(tgt, old_x, old_y)


@command("motion_glidesecstoxy")
def glidesecstoxy(rt, tgt, block):
    yield from _glide_to(rt, tgt, block,
                         cast.to_number(api.val(rt, tgt, block, "X", 0)),
                         cast.to_number(api.val(rt, tgt, block, "Y", 0)))


@command("motion_glidesecsgeneric")
def glidesecsgeneric(rt, tgt, block):
    what = api.text(rt, tgt, block, "TO", "_random_")
    if what == "_random_":
        import random

        x, y = random.uniform(-240, 240), random.uniform(-180, 180)
    else:
        x, y = _resolve_target_xy(rt, tgt, what)
    yield from _glide_to(rt, tgt, block, x, y)


def _glide_to(rt, tgt, block, dest_x, dest_y):
    duration = max(0.0, cast.to_number(api.val(rt, tgt, block, "SECS", 0)))
    sx, sy = tgt.x, tgt.y
    prev_x, prev_y = sx, sy
    start = rt.now()
    if duration <= 0:
        tgt.x, tgt.y = dest_x, dest_y
        rt.pen_move(tgt, prev_x, prev_y)
        return
    while True:
        elapsed = rt.now() - start
        frac = min(1.0, elapsed / duration)
        tgt.x = sx + (dest_x - sx) * frac
        tgt.y = sy + (dest_y - sy) * frac
        rt.pen_move(tgt, prev_x, prev_y)
        prev_x, prev_y = tgt.x, tgt.y
        if frac >= 1.0:
            return
        yield


@command("motion_changexby")
def changexby(rt, tgt, block):
    old_x = tgt.x
    tgt.x += cast.to_number(api.val(rt, tgt, block, "DX", 0))
    rt.pen_move(tgt, old_x, tgt.y)


@command("motion_setx")
def setx(rt, tgt, block):
    old_x = tgt.x
    tgt.x = cast.to_number(api.val(rt, tgt, block, "X", 0))
    rt.pen_move(tgt, old_x, tgt.y)


@command("motion_changeyby")
def changeyby(rt, tgt, block):
    old_y = tgt.y
    tgt.y += cast.to_number(api.val(rt, tgt, block, "DY", 0))
    rt.pen_move(tgt, tgt.x, old_y)


@command("motion_sety")
def sety(rt, tgt, block):
    old_y = tgt.y
    tgt.y = cast.to_number(api.val(rt, tgt, block, "Y", 0))
    rt.pen_move(tgt, tgt.x, old_y)


@command("motion_ifonedgebounce")
def ifonedgebounce(rt, tgt, block):
    tgt.if_on_edge_bounce()


@command("motion_setrotationstyle")
def setrotationstyle(rt, tgt, block):
    tgt.rotation_style = api.fld(block, "STYLE")


@reporter("motion_xposition")
def xposition(rt, tgt, block):
    return tgt.x


@reporter("motion_yposition")
def yposition(rt, tgt, block):
    return tgt.y


@reporter("motion_direction")
def direction(rt, tgt, block):
    return tgt.direction

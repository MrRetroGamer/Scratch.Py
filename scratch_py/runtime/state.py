"""Mutable runtime state for a sprite/stage target."""

from __future__ import annotations

import math

from ..parser.model import Costume, TargetData

EFFECT_KEYS = ("color", "fisheye", "whirl", "mosaic", "pixelate", "brightness", "ghost", "saturation")

STAGE_WIDTH = 480
STAGE_HEIGHT = 360


class TargetState:
    def __init__(self, data: TargetData, rt):
        self.data = data
        self.rt = rt
        self.is_stage = data.is_stage
        self.name = data.name
        self.variables = {vid: [entry[0], entry[1]] for vid, entry in data.variables.items()}
        self.lists = {lid: [entry[0], list(entry[1])] for lid, entry in data.lists.items()}
        self.x = data.x
        self.y = data.y
        self.size = data.size
        self.direction = data.direction
        self.visible = data.visible
        self.rotation_style = data.rotation_style
        self.current_costume = data.current_costume
        self.volume = data.volume
        self.effects = {key: 0.0 for key in EFFECT_KEYS}
        self.say_text: str | None = None
        self.say_style: str | None = None
        self.is_clone = False
        self.original: TargetState | None = None
        self.pen = {
            "down": False,
            "size": 1.0,
            "hue": 80.0,
            "saturation": 100.0,
            "brightness": 100.0,
            "transparency": 0.0,
            "rgb": (85.0, 0.0, 255.0),
        }

    @property
    def costumes(self) -> list[Costume]:
        return self.data.costumes

    def costume(self) -> Costume | None:
        if not self.data.costumes:
            return None
        index = int(self.current_costume) % len(self.data.costumes)
        return self.data.costumes[index]

    def move_steps(self, steps: float):
        radians = math.radians(90.0 - self.direction)
        self.x += steps * math.cos(radians)
        self.y += steps * math.sin(radians)

    def point_in_direction(self, direction: float):
        d = ((float(direction) % 360.0) + 540.0) % 360.0 - 180.0
        self.direction = d

    def point_towards_xy(self, tx: float, ty: float):
        dx = tx - self.x
        dy = ty - self.y
        if dx == 0 and dy == 0:
            return
        self.point_in_direction(math.degrees(math.atan2(dx, dy)))

    def if_on_edge_bounce(self):
        bounds = self.rt.sprite_bounds(self)
        if bounds is None:
            return
        left, right, top, bottom = bounds
        half_w = (right - left) / 2.0
        half_h = (top - bottom) / 2.0
        cx, cy = (left + right) / 2.0, (top + bottom) / 2.0
        radians = math.radians(self.direction)
        dx = math.sin(radians)
        dy = math.cos(radians)
        bounced = False
        if cx > STAGE_WIDTH / 2 - half_w and dx > 0:
            dx = -dx
            bounced = True
        elif cx < -STAGE_WIDTH / 2 + half_w and dx < 0:
            dx = -dx
            bounced = True
        if cy > STAGE_HEIGHT / 2 - half_h and dy > 0:
            dy = -dy
            bounced = True
        elif cy < -STAGE_HEIGHT / 2 + half_h and dy < 0:
            dy = -dy
            bounced = True
        if bounced:
            if dx == 0:
                dx = 1e-9
            self.point_in_direction(math.degrees(math.atan2(dx, dy)))

    def keep_on_stage(self):
        limit = 10000
        self.x = max(-limit, min(limit, self.x))
        self.y = max(-limit, min(limit, self.y))

    def set_effect(self, key: str, value: float):
        if key in ("ghost", "brightness"):
            value = max(-100.0, min(100.0, value))
        elif key == "saturation":
            value = max(-100.0, min(100.0, value))
        self.effects[key] = value

    def change_effect(self, key: str, delta: float):
        self.set_effect(key, self.effects.get(key, 0.0) + delta)

    def clone_state_from(self, original: TargetState):
        self.x = original.x
        self.y = original.y
        self.size = original.size
        self.direction = original.direction
        self.visible = original.visible
        self.rotation_style = original.rotation_style
        self.current_costume = original.current_costume
        self.volume = original.volume
        self.effects = dict(original.effects)
        self.variables = {vid: [e[0], e[1]] for vid, e in original.variables.items()}
        self.lists = {lid: [e[0], list(e[1])] for lid, e in original.lists.items()}
        self.pen = dict(original.pen)
        self.is_clone = True
        self.original = original

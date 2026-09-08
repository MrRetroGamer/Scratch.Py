"""Typed model of an SB3 project."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Costume:
    name: str
    md5ext: str
    data_format: str
    rotation_center_x: float = 0.0
    rotation_center_y: float = 0.0
    bitmap_resolution: float = 1.0


@dataclass
class Sound:
    name: str
    md5ext: str
    data_format: str
    rate: int = 0
    sample_count: int = 0


@dataclass
class Input:
    """A decoded block input slot.

    kind is 1 (shadow only), 2 (block, no shadow) or 3 (block obscuring shadow).
    Exactly one of block_id / shadow_block_id / primitive is meaningful per kind.
    primitive is a raw tuple (tag, value, ...) using SB3 primitive tags:
      4-9 math/color literals, 10 string, 11 broadcast, 12 variable, 13 list.
    """

    kind: int
    block_id: str | None = None
    shadow_block_id: str | None = None
    primitive: tuple | None = None

    def value_or(self, default):
        if self.primitive is not None:
            return self.primitive[1]
        return default


@dataclass
class Block:
    id: str
    opcode: str
    parent: str | None = None
    next: str | None = None
    inputs: dict[str, Input] = field(default_factory=dict)
    fields: dict[str, list] = field(default_factory=dict)
    mutation: dict | None = None
    shadow: bool = False
    top_level: bool = False
    x: float | None = None
    y: float | None = None


@dataclass
class TargetData:
    name: str
    is_stage: bool
    blocks: dict[str, Block] = field(default_factory=dict)
    variables: dict[str, list] = field(default_factory=dict)
    lists: dict[str, list] = field(default_factory=dict)
    broadcasts: dict[str, str] = field(default_factory=dict)
    costumes: list[Costume] = field(default_factory=list)
    current_costume: int = 0
    sounds: list[Sound] = field(default_factory=list)
    volume: float = 100.0
    layer_order: int = 0
    x: float = 0.0
    y: float = 0.0
    size: float = 100.0
    direction: float = 90.0
    visible: bool = True
    draggable: bool = False
    rotation_style: str = "all around"


@dataclass
class MonitorData:
    id: str
    mode: str
    opcode: str
    params: dict
    sprite_name: str | None
    width: float = 0
    height: float = 0
    x: float = 5
    y: float = 5
    visible: bool = True
    slider_min: float = 0
    slider_max: float = 100
    is_discrete: bool = True
    value: object = None


@dataclass
class ProjectData:
    targets: list[TargetData]
    monitors: list[MonitorData]
    extensions: list[str]
    meta: dict

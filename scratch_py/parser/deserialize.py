"""Deserialize project.json into the typed model, handling both dict-form and
compressed array-form block serialization emitted by sb3.js."""

from __future__ import annotations

import json

from .model import Block, Costume, Input, MonitorData, ProjectData, Sound, TargetData


def parse_project(raw: str | bytes) -> ProjectData:
    data = json.loads(raw)
    if not isinstance(data, dict) or "targets" not in data:
        raise ValueError("not a valid project.json")
    targets = [_load_target(t) for t in data["targets"]]
    monitors = [_load_monitor(m) for m in data.get("monitors", [])]
    return ProjectData(
        targets=targets,
        monitors=monitors,
        extensions=list(data.get("extensions", [])),
        meta=dict(data.get("meta", {})),
    )


def _load_target(data: dict) -> TargetData:
    t = TargetData(name=data["name"], is_stage=bool(data.get("isStage", False)))
    t.blocks = {bid: _load_block(bid, bdata) for bid, bdata in data.get("blocks", {}).items()}
    t.variables = {vid: list(v) for vid, v in data.get("variables", {}).items()}
    t.lists = {lid: [name, list(items)] for lid, (name, items) in data.get("lists", {}).items()}
    t.broadcasts = dict(data.get("broadcasts", {}))
    t.costumes = [_load_costume(c) for c in data.get("costumes", [])]
    t.sounds = [
        Sound(
            name=s["name"],
            md5ext=s.get("md5ext") or f"{s['assetId']}.{s['dataFormat']}",
            data_format=s["dataFormat"],
            rate=int(s.get("rate", 0)),
            sample_count=int(s.get("sampleCount", 0)),
        )
        for s in data.get("sounds", [])
    ]
    t.current_costume = int(data.get("currentCostume", 0))
    t.volume = float(data.get("volume", 100))
    t.layer_order = int(data.get("layerOrder", 0))
    t.x = float(data.get("x", 0))
    t.y = float(data.get("y", 0))
    t.size = float(data.get("size", 100))
    t.direction = float(data.get("direction", 90))
    t.visible = bool(data.get("visible", True))
    t.draggable = bool(data.get("draggable", False))
    t.rotation_style = data.get("rotationStyle", "all around")
    return t


def _load_costume(c: dict) -> Costume:
    return Costume(
        name=c["name"],
        md5ext=c.get("md5ext") or f"{c['assetId']}.{c['dataFormat']}",
        data_format=c["dataFormat"],
        rotation_center_x=float(c.get("rotationCenterX", 0)),
        rotation_center_y=float(c.get("rotationCenterY", 0)),
        bitmap_resolution=float(c.get("bitmapResolution", 1)),
    )


def _load_block(bid: str, data) -> Block:
    if isinstance(data, list):
        b = Block(id=bid, opcode=data[0])
        inputs = data[1] if len(data) > 1 else {}
        fields = data[2] if len(data) > 2 else {}
        mutation = data[3] if len(data) > 3 and data[3] else None
        b.shadow = bool(data[4]) if len(data) > 4 else False
        b.top_level = bool(data[5]) if len(data) > 5 else False
    else:
        b = Block(
            id=bid,
            opcode=data["opcode"],
            parent=data.get("parent"),
            next=data.get("next"),
            shadow=bool(data.get("shadow", False)),
            top_level=bool(data.get("topLevel", False)),
            x=data.get("x"),
            y=data.get("y"),
        )
        inputs = data.get("inputs", {})
        fields = data.get("fields", {})
        mutation = data.get("mutation")
    b.inputs = {k: _load_input(v) for k, v in inputs.items()}
    b.fields = fields
    if mutation is not None:
        b.mutation = dict(mutation)
    return b


def _load_input(arr: list) -> Input:
    kind = int(arr[0])
    inp = Input(kind=kind)
    main = arr[1]
    if isinstance(main, list):
        inp.primitive = tuple(main)
    elif isinstance(main, str):
        inp.block_id = main
    if len(arr) > 2:
        obscured = arr[2]
        if isinstance(obscured, list):
            if inp.primitive is None:
                inp.primitive = tuple(obscured)
        elif isinstance(obscured, str):
            inp.shadow_block_id = obscured
    return inp


def _load_monitor(m: dict) -> MonitorData:
    return MonitorData(
        id=m["id"],
        mode=m["mode"],
        opcode=m["opcode"],
        params=dict(m.get("params", {})),
        sprite_name=m.get("spriteName"),
        width=float(m.get("width", 0)),
        height=float(m.get("height", 0)),
        x=float(m.get("x", 5)),
        y=float(m.get("y", 5)),
        visible=bool(m.get("visible", True)),
        slider_min=float(m.get("sliderMin", 0)),
        slider_max=float(m.get("sliderMax", 100)),
        is_discrete=bool(m.get("isDiscrete", True)),
        value=m.get("value"),
    )


class ScriptDumper:
    """Renders parsed scripts back into readable Scratch pseudo-code."""

    def dump_project(self, project: ProjectData) -> str:
        out = []
        for target in project.targets:
            out.append(f"=== {target.name}{' (stage)' if target.is_stage else ''} ===")
            for bid, block in target.blocks.items():
                if block.top_level and not block.shadow:
                    out.append(self.dump_stack(target, bid))
                    out.append("")
        return "\n".join(out)

    def dump_stack(self, target: TargetData, first_id: str | None, indent: int = 0) -> str:
        lines = []
        bid = first_id
        while bid:
            block = target.blocks.get(bid)
            if block is None:
                break
            lines.append(self._dump_block(target, block, indent))
            sub = self._dump_substacks(target, block, indent + 1)
            lines.extend(sub)
            bid = block.next
        return "\n".join(lines)

    def _dump_substacks(self, target: TargetData, block: Block, indent: int) -> list[str]:
        out = []
        for name in ("SUBSTACK", "SUBSTACK2"):
            inp = block.inputs.get(name)
            if inp and inp.block_id:
                out.append(self.dump_stack(target, inp.block_id, indent))
        return out

    def _dump_block(self, target: TargetData, block: Block, indent: int) -> str:
        pad = "    " * indent
        parts = []
        for key in sorted(block.inputs):
            inp = block.inputs[key]
            if inp.primitive is not None:
                parts.append(f"{key}={inp.primitive[1]!r}")
            elif inp.block_id and inp.block_id in target.blocks:
                inner = target.blocks[inp.block_id]
                parts.append(f"{key}=[{self._describe(target, inner)}]")
        mut = ""
        if block.mutation and "proccode" in block.mutation:
            mut = f" <{block.mutation['proccode']}>"
        head = block.opcode + mut
        if parts:
            head += " (" + ", ".join(parts) + ")"
        for fname, fval in block.fields.items():
            head += f" {{{fname}: {fval[0]}}}"
        return f"{pad}{head}"

    def _describe(self, target: TargetData, block: Block) -> str:
        if block.opcode == "operator_join":
            a = self._inline_value(target, block.inputs.get("STRING1"))
            b = self._inline_value(target, block.inputs.get("STRING2"))
            return f"join {a} {b}"
        if block.fields:
            return next(iter(block.fields.values()))[0]
        return block.opcode

    def _inline_value(self, target: TargetData, inp: Input | None) -> str:
        if inp is None:
            return "?"
        if inp.primitive is not None:
            return repr(inp.primitive[1])
        if inp.block_id and inp.block_id in target.blocks:
            return "[" + self._describe(target, target.blocks[inp.block_id]) + "]"
        return "?"

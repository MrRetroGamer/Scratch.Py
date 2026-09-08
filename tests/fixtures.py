"""Programmatic .sb3 builders used by the test suites."""

from __future__ import annotations

import json
import struct
import zipfile
import zlib


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))


def make_png(width: int = 8, height: int = 8, rgba=(255, 0, 0, 255)) -> bytes:
    raw = b"".join(b"\x00" + bytes(rgba) * width for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )


def prim_num(v) -> list:
    return [1, [4, str(v)]]


def prim_string(v) -> list:
    return [1, [10, str(v)]]


def prim_var(name: str, vid: str) -> list:
    return [1, [12, str(name), str(vid)]]


def prim_list(name: str, lid: str) -> list:
    return [1, [13, str(name), str(lid)]]


def prim_bool_true() -> list:
    return [1, [4, "true"]]


def block_ref(block_id: str) -> list:
    return [2, block_id]


def b(bid, opcode, *, inputs=None, fields=None, nxt=None, parent=None,
      top_level=False, shadow=False, mutation=None) -> dict:
    data = {
        "opcode": opcode,
        "next": nxt,
        "parent": parent,
        "inputs": inputs or {},
        "fields": fields or {},
        "shadow": shadow,
        "topLevel": top_level,
    }
    if mutation is not None:
        data["mutation"] = mutation
    if top_level:
        data["x"], data["y"] = 0, 0
    return data


def simple_project(sprites: dict[str, dict]) -> dict:
    stage = {
        "isStage": True,
        "name": "Stage",
        "variables": {},
        "lists": {},
        "broadcasts": {},
        "blocks": {},
        "comments": {},
        "currentCostume": 0,
        "costumes": [
            {
                "name": "backdrop1",
                "dataFormat": "svg",
                "assetId": "cd21514d0531fdffb22204e0ec5ed84a",
                "md5ext": "cd21514d0531fdffb22204e0ec5ed84a.svg",
                "rotationCenterX": 240,
                "rotationCenterY": 180,
            }
        ],
        "sounds": [],
        "volume": 100,
        "layerOrder": 0,
        "tempo": 60,
        "videoTransparency": 50,
        "videoState": "on",
        "textToSpeechLanguage": None,
    }
    targets = [stage]
    for i, (name, extra) in enumerate(sprites.items()):
        sprite = {
            "isStage": False,
            "name": name,
            "variables": {},
            "lists": {},
            "broadcasts": {},
            "blocks": {},
            "currentCostume": 0,
            "costumes": [
                {
                    "name": "costume1",
                    "dataFormat": "png",
                    "assetId": "f9a1c175dbe2e5dee472858dd9d67101",
                    "md5ext": "f9a1c175dbe2e5dee472858dd9d67101.png",
                    "rotationCenterX": 48,
                    "rotationCenterY": 50,
                }
            ],
            "sounds": [],
            "volume": 100,
            "layerOrder": i + 1,
            "visible": True,
            "x": 0,
            "y": 0,
            "size": 100,
            "direction": 90,
            "draggable": False,
            "rotationStyle": "all around",
        }
        sprite.update(extra)
        targets.append(sprite)
    return {
        "targets": targets,
        "monitors": [],
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": "tests"},
    }


FAKE_PNG = make_png()

FAKE_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360">'
    b"<rect width='480' height='360' fill='#88f'/></svg>"
)


def write_sb3(path, project_dict: dict, assets: dict[str, bytes] | None = None):
    all_assets = {
        "cd21514d0531fdffb22204e0ec5ed84a.svg": FAKE_SVG,
        "f9a1c175dbe2e5dee472858dd9d67101.png": FAKE_PNG,
    }
    all_assets.update(assets or {})
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("project.json", json.dumps(project_dict))
        for name, payload in all_assets.items():
            zf.writestr(name, payload)

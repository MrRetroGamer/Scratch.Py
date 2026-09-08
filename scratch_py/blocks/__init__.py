"""Opcode handler registry. Handlers are plain functions or generator functions;
generator functions may yield to give control back to the scheduler."""

from __future__ import annotations

import importlib
import inspect

MODULES = [
    "scratch_py.blocks.motion",
    "scratch_py.blocks.looks",
    "scratch_py.blocks.sound",
    "scratch_py.blocks.events",
    "scratch_py.blocks.control",
    "scratch_py.blocks.sensing",
    "scratch_py.blocks.operators",
    "scratch_py.blocks.data",
    "scratch_py.blocks.procedures",
    "scratch_py.extensions.pen",
    "scratch_py.extensions.music_blocks",
]

HANDLERS: dict[str, Handler] = {}


class Handler:
    __slots__ = ("opcode", "kind", "fn", "is_gen")

    def __init__(self, opcode: str, kind: str, fn):
        self.opcode = opcode
        self.kind = kind
        self.fn = fn
        self.is_gen = inspect.isgeneratorfunction(fn)


def _register(opcode: str, kind: str):
    def deco(fn):
        HANDLERS[opcode] = Handler(opcode, kind, fn)
        return fn

    return deco


def command(opcode: str):
    return _register(opcode, "command")


def hat(opcode: str):
    return _register(opcode, "hat")


def reporter(opcode: str):
    return _register(opcode, "reporter")


def boolean(opcode: str):
    return _register(opcode, "boolean")


_registered = False


def register_all():
    global _registered
    if _registered:
        return
    for mod in MODULES:
        importlib.import_module(mod)
    _registered = True


def _menu_field_reporter(rt, tgt, block):
    if block.fields:
        return next(iter(block.fields.values()))[0]
    return ""


MENU_OPCODES = {
    "looks_costume",
    "looks_backdrop",
    "looks_backdrops",
    "sensing_keyoptions",
    "control_stop_menu",
    "control_create_clone_of_menu",
    "motion_glideto",
    "pen_menu_colorParam",
    "music_menu_drums",
    "music_menu_instruments",
    "event_broadcast_menu",
    "sound_sounds_menu",
}
MENU_HANDLER = Handler("<menu>", "reporter", _menu_field_reporter)


def get_handler(opcode: str) -> Handler | None:
    h = HANDLERS.get(opcode)
    if h is not None:
        return h
    if opcode.startswith("motion_glidesecs"):
        return HANDLERS.get("motion_glidesecsgeneric")
    if opcode.endswith("menu") or opcode in MENU_OPCODES:
        return MENU_HANDLER
    return None

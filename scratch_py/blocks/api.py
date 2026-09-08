"""Evaluation helpers used by block handlers. `rt` is the Runtime instance,
`tgt` the executing TargetState, `block` the parser Block."""

from __future__ import annotations

from ..util import jscompat as cast


def val(rt, tgt, block, name: str, default=None):
    inp = block.inputs.get(name)
    if inp is None:
        return default
    return rt.eval_input(tgt, inp)


def num(rt, tgt, block, name: str, default=0):
    v = val(rt, tgt, block, name)
    if v is None:
        return default
    return cast.to_number(v)


def text(rt, tgt, block, name: str, default=""):
    v = val(rt, tgt, block, name)
    if v is None:
        return default
    return cast.to_string(v)


def flag(rt, tgt, block, name: str) -> bool:
    return cast.to_bool(val(rt, tgt, block, name, False))


def fld(block, name: str):
    entry = block.fields.get(name)
    if not entry:
        return ""
    return entry[0]


def substack(block, name: str = "SUBSTACK") -> str | None:
    inp = block.inputs.get(name)
    if inp is None:
        return None
    return inp.block_id

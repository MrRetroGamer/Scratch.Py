from __future__ import annotations

from ..util import jscompat as cast
from . import api, boolean, reporter


@reporter("operator_add")
def add(rt, tgt, block):
    return cast.to_number(api.val(rt, tgt, block, "NUM1", 0)) + cast.to_number(
        api.val(rt, tgt, block, "NUM2", 0)
    )


@reporter("operator_subtract")
def subtract(rt, tgt, block):
    return cast.to_number(api.val(rt, tgt, block, "NUM1", 0)) - cast.to_number(
        api.val(rt, tgt, block, "NUM2", 0)
    )


@reporter("operator_multiply")
def multiply(rt, tgt, block):
    return cast.to_number(api.val(rt, tgt, block, "NUM1", 0)) * cast.to_number(
        api.val(rt, tgt, block, "NUM2", 0)
    )


@reporter("operator_divide")
def divide(rt, tgt, block):
    return cast.js_divide(
        cast.to_number(api.val(rt, tgt, block, "NUM1", 0)),
        cast.to_number(api.val(rt, tgt, block, "NUM2", 0)),
    )


@reporter("operator_random")
def random_block(rt, tgt, block):
    return cast.pick_random(api.val(rt, tgt, block, "FROM"), api.val(rt, tgt, block, "TO"))


@boolean("operator_gt")
def gt(rt, tgt, block):
    return cast.compare(api.val(rt, tgt, block, "OPERAND1"), api.val(rt, tgt, block, "OPERAND2")) > 0


@boolean("operator_lt")
def lt(rt, tgt, block):
    return cast.compare(api.val(rt, tgt, block, "OPERAND1"), api.val(rt, tgt, block, "OPERAND2")) < 0


@boolean("operator_equals")
def equals_block(rt, tgt, block):
    return cast.equals(api.val(rt, tgt, block, "OPERAND1"), api.val(rt, tgt, block, "OPERAND2"))


@boolean("operator_and")
def and_block(rt, tgt, block):
    return cast.to_bool(api.val(rt, tgt, block, "OPERAND1", False)) and cast.to_bool(
        api.val(rt, tgt, block, "OPERAND2", False)
    )


@boolean("operator_or")
def or_block(rt, tgt, block):
    return cast.to_bool(api.val(rt, tgt, block, "OPERAND1", False)) or cast.to_bool(
        api.val(rt, tgt, block, "OPERAND2", False)
    )


@boolean("operator_not")
def not_block(rt, tgt, block):
    return not cast.to_bool(api.val(rt, tgt, block, "OPERAND", False))


@reporter("operator_join")
def join(rt, tgt, block):
    return cast.to_string(api.val(rt, tgt, block, "STRING1")) + cast.to_string(
        api.val(rt, tgt, block, "STRING2")
    )


@reporter("operator_letter_of")
def letter_of(rt, tgt, block):
    return cast.letter_of(api.val(rt, tgt, block, "LETTER"), api.val(rt, tgt, block, "STRING"))


@reporter("operator_length")
def length(rt, tgt, block):
    return len(cast.to_string(api.val(rt, tgt, block, "STRING")))


@boolean("operator_contains")
def contains_block(rt, tgt, block):
    return cast.contains(
        cast.to_string(api.val(rt, tgt, block, "STRING1")),
        cast.to_string(api.val(rt, tgt, block, "STRING2")),
    )


@reporter("operator_mod")
def mod(rt, tgt, block):
    return cast.js_mod(
        cast.to_number(api.val(rt, tgt, block, "NUM1", 0)),
        cast.to_number(api.val(rt, tgt, block, "NUM2", 0)),
    )


@reporter("operator_round")
def round_block(rt, tgt, block):
    return cast.js_round(cast.to_number(api.val(rt, tgt, block, "NUM", 0)))


@reporter("operator_mathop")
def mathop(rt, tgt, block):
    op = api.fld(block, "OPERATOR")
    return cast.math_op(op, api.val(rt, tgt, block, "NUM", 0))

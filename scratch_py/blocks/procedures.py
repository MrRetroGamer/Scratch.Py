from __future__ import annotations

import json

from . import api, command, hat, reporter


@hat("procedures_definition")
def procedures_definition(rt, tgt, block):
    return None


@command("procedures_call")
def procedures_call(rt, tgt, block):
    mutation = block.mutation or {}
    proccode = mutation.get("proccode", "")
    defn = rt.find_procdef(tgt, proccode)
    if defn is None:
        rt._warn_once(f"proc:{proccode}", f"missing custom block definition: {proccode}")
        return
    try:
        arg_ids = json.loads(mutation.get("argumentids", "[]"))
    except (ValueError, TypeError):
        arg_ids = []
    proto = None
    inp = defn.inputs.get("custom_block")
    if inp is not None:
        ref = inp.block_id or inp.shadow_block_id
        if ref and ref in tgt.data.blocks:
            candidate = tgt.data.blocks[ref]
            if candidate.opcode == "procedures_prototype":
                proto = candidate
    proto_mutation = proto.mutation if proto is not None else None
    try:
        arg_names = json.loads((proto_mutation or {}).get("argumentnames", "[]"))
    except (ValueError, TypeError):
        arg_names = []
    args = {}
    for i, aid in enumerate(arg_ids):
        value = rt.eval_input(tgt, block.inputs[aid]) if aid in block.inputs else ""
        name = arg_names[i] if i < len(arg_names) else f"arg{i}"
        args[name] = value
    body_id = defn.next
    warp = bool(proto_mutation.get("warp") in (True, "true")) if proto_mutation else False
    thread = rt.current_thread
    thread.arg_stack.append(args)
    saved_warp = thread.warp
    if warp:
        thread.warp = True
    try:
        yield from rt.run_substack(tgt, body_id)
    finally:
        thread.warp = saved_warp
        if thread.arg_stack:
            thread.arg_stack.pop()


def _lookup_arg(rt, block):
    name = api.fld(block, "VALUE")
    thread = rt.current_thread
    if thread is None or not thread.arg_stack:
        return ""
    frame = thread.arg_stack[-1]
    return frame.get(name, "")


@reporter("argument_reporter_string_number")
def argument_reporter_string_number(rt, tgt, block):
    return _lookup_arg(rt, block)


@reporter("argument_reporter_boolean")
def argument_reporter_boolean(rt, tgt, block):
    from ..util import jscompat as cast

    return cast.to_bool(_lookup_arg(rt, block))

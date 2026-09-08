from __future__ import annotations

from ..runtime.thread import DONE, StopAll, StopScript
from ..util import jscompat as cast
from . import api, command, hat


@command("control_wait")
def wait(rt, tgt, block):
    duration = max(0.0, cast.to_number(api.val(rt, tgt, block, "DURATION", 0)))
    start = rt.now()
    while rt.now() - start < duration:
        yield


@command("control_repeat")
def repeat(rt, tgt, block):
    times = max(0, int(cast.js_round(cast.to_number(api.val(rt, tgt, block, "TIMES", 0)))))
    thread = rt.current_thread
    substack = api.substack(block)
    warp = thread.warp if thread else False
    for _ in range(times):
        if substack:
            yield from rt.run_substack(tgt, substack)
        if not warp:
            yield
        elif rt.warp_deadline_exceeded():
            yield


@command("control_forever")
def forever(rt, tgt, block):
    substack = api.substack(block)
    while True:
        if substack:
            yield from rt.run_substack(tgt, substack)
        yield


@command("control_if")
def if_block(rt, tgt, block):
    if cast.to_bool(api.val(rt, tgt, block, "CONDITION", False)):
        substack = api.substack(block)
        if substack:
            yield from rt.run_substack(tgt, substack)


@command("control_if_else")
def if_else(rt, tgt, block):
    if cast.to_bool(api.val(rt, tgt, block, "CONDITION", False)):
        substack = api.substack(block, "SUBSTACK")
        if substack:
            yield from rt.run_substack(tgt, substack)
    else:
        substack = api.substack(block, "SUBSTACK2")
        if substack:
            yield from rt.run_substack(tgt, substack)


@command("control_wait_until")
def wait_until(rt, tgt, block):
    while not cast.to_bool(api.val(rt, tgt, block, "CONDITION", False)):
        yield


@command("control_repeat_until")
def repeat_until(rt, tgt, block):
    thread = rt.current_thread
    warp = thread.warp if thread else False
    substack = api.substack(block)
    while not cast.to_bool(api.val(rt, tgt, block, "CONDITION", False)):
        if substack:
            yield from rt.run_substack(tgt, substack)
        if not warp:
            yield
        elif rt.warp_deadline_exceeded():
            yield


@command("control_stop")
def stop(rt, tgt, block):
    option = api.fld(block, "STOP_OPTION")
    if option == "all":
        raise StopAll()
    if option == "this script":
        raise StopScript()
    if option == "other scripts in sprite":
        current = rt.current_thread
        for th in list(rt.threads):
            if th.target is tgt and (current is None or th is not current):
                th.status = DONE


@command("control_create_clone_of")
def create_clone_of(rt, tgt, block):
    what = api.text(rt, tgt, block, "CLONE_OPTION", "_myself_")
    source = tgt if what == "_myself_" else rt.find_target_by_name(what)
    if source is not None:
        rt.create_clone(source)


@hat("control_start_as_clone")
def start_as_clone(rt, tgt, block):
    return None


@command("control_delete_this_clone")
def delete_this_clone(rt, tgt, block):
    if tgt.is_clone:
        rt.delete_clone(tgt)
        raise StopScript()

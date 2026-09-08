from __future__ import annotations

from . import command, hat


@hat("event_whenflagclicked")
def whenflagclicked(rt, tgt, block):
    return None


@hat("event_whenkeypressed")
def whenkeypressed(rt, tgt, block):
    return None


@hat("event_whenthisspriteclicked")
def whenthisspriteclicked(rt, tgt, block):
    return None


@hat("event_whenstageclicked")
def whenstageclicked(rt, tgt, block):
    return None


@hat("event_whenbroadcastreceived")
def whenbroadcastreceived(rt, tgt, block):
    return None


@hat("event_whenbackdropswitchesto")
def whenbackdropswitchesto(rt, tgt, block):
    return None


@hat("event_whengreaterthan")
def whengreaterthan(rt, tgt, block):
    return None


@command("event_broadcast")
def broadcast(rt, tgt, block):
    name = _broadcast_name(rt, tgt, block)
    rt.restart_broadcast_threads(name)


@command("event_broadcastandwait")
def broadcast_and_wait(rt, tgt, block):
    name = _broadcast_name(rt, tgt, block)
    rt.restart_broadcast_threads(name)
    while not rt.broadcast_wait_finished(name):
        yield


def _broadcast_name(rt, tgt, block) -> str:
    inp = block.inputs.get("BROADCAST_INPUT")
    if inp is None:
        entry = block.fields.get("BROADCAST_OPTION")
        return entry[0] if entry else ""
    value = rt.eval_input(tgt, inp)
    return str(value)

"""Thread objects and control-flow exceptions for the scheduler."""

from __future__ import annotations

RUNNING = 0
DONE = 1


class StopScript(Exception):
    """Raised by `stop this script`; terminates only the current thread."""


class StopAll(Exception):
    """Raised by `stop all`; terminates every thread."""


class Thread:
    __slots__ = ("rt", "target", "top_block_id", "gen", "status", "warp", "arg_stack")

    def __init__(self, rt, target, top_block_id: str, gen):
        self.rt = rt
        self.target = target
        self.top_block_id = top_block_id
        self.gen = gen
        self.status = RUNNING
        self.warp = False
        self.arg_stack: list[dict] = []

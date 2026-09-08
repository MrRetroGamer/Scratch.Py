"""Entry point: python scratch_py/cli.py project.sb3 (or python -m scratch_py.cli)"""

from __future__ import annotations

if __name__ == "__main__" and __package__ in (None, ""):
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    import scratch_py.cli as _self

    raise SystemExit(_self.main())

import argparse
import sys

from . import __version__


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="scratch.py",
        description="Run Scratch 3 (.sb3) projects natively in Python.",
    )
    parser.add_argument("project", nargs="?", help="path to a .sb3 file")
    parser.add_argument("--version", action="version", version=f"scratch.py {__version__}")
    parser.add_argument("--scale", type=int, default=2, help="window scale factor (default 2)")
    parser.add_argument("--turbo", action="store_true", help="run without frame throttle")
    parser.add_argument("--dump", action="store_true", help="print parsed scripts and exit")
    parser.add_argument("--headless", type=int, metavar="FRAMES", default=None,
                        help="simulate N frames without a window, print final state")
    args = parser.parse_args(argv)
    if args.project is None:
        parser.error("the following arguments are required: project")

    from .parser.sb3 import SB3Error, load_sb3

    try:
        project, assets = load_sb3(args.project)
    except SB3Error as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.dump:
        from .parser.deserialize import ScriptDumper

        print(ScriptDumper().dump_project(project))
        return 0

    from .runtime.engine import Runtime

    rt = Runtime(project, assets)

    if args.headless is not None:
        rt.green_flag()
        for _ in range(args.headless):
            rt.tick()
            rt.advance_time(1 / 30)
        _print_state(rt)
        return 0

    from .audio.player import AudioPlayer
    from .render.renderer import Renderer

    rt.audio = AudioPlayer(assets)
    renderer = Renderer(rt, assets, scale=args.scale)
    rt.turbo = args.turbo or rt.turbo
    rt.green_flag()
    renderer.run()
    return 0


def _print_state(rt) -> None:
    for tgt in rt.targets:
        kind = "stage" if tgt.is_stage else "sprite"
        print(f"== {tgt.name} ({kind}) ==")
        if not tgt.is_stage:
            print(f"  x={tgt.x} y={tgt.y} dir={tgt.direction} size={tgt.size} visible={tgt.visible}")
        for entry in tgt.variables.values():
            value = entry[1]
            if isinstance(value, list):
                value = f"[{', '.join(str(v) for v in value[:10])}]"
            print(f"  var {entry[0]} = {value}")
        for entry in tgt.lists.values():
            preview = ", ".join(str(v) for v in entry[1][:10])
            print(f"  list {entry[0]} ({len(entry[1])}) = [{preview}]")


if __name__ == "__main__":
    raise SystemExit(main())

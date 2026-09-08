# scratch.py

A custom parser + runtime that plays **Scratch 3 (`.sb3`) projects natively in Python**.

`.sb3` files are ZIP archives containing `project.json` (the whole program: sprites,
blocks, variables) plus content-addressed assets (`<md5>.png|svg|wav`). scratch.py
parses that format and executes it with a faithful reimplementation of the
scratch-vm scheduler, rendered with pygame-ce.

```bash
pip install -e .[dev]
python -m scratch_py path/to/project.sb3
# or equivalently:
scratch-py path/to/project.sb3

# print the version and exit
python -m scratch_py --version
# inspect a project without running it
python -m scratch_py project.sb3 --dump
# simulate 120 frames with no window, print final variable/list state
python -m scratch_py project.sb3 --headless 120
```

## Controls

The window opens **maximized** with a Scratch-style toolbar: a **green flag** and
**stop** button above the stage — safe to use while typing in an ask box.

| Key | Action |
| --- | --- |
| `T` | Toggle turbo mode (inactive while typing) |
| `F` | Fullscreen (inactive while typing) |

Monitors, the ask box and speech bubbles are drawn at native window resolution
with Segoe UI, matching the Scratch editor's look: orange-bordered variable
chips, striped list cards with item counts, and a blue-ringed ask bar.

SVG costumes render through **resvg** (bundled, no system libraries), falling
back to cairosvg and svglib when present.

## Architecture

```
scratch_py/
├── parser/      sb3 zip loader -> typed model (blocks, targets, assets)
├── runtime/     generator-stack thread scheduler at 30 FPS, clones, broadcasts
├── blocks/      opcode handlers for every core category + procedures
├── extensions/  pen layer, music synth
├── render/      pygame-ce stage, costumes (PNG/SVG), speech bubbles, monitors
├── audio/       sound playback via pygame mixer
└── util/        JS-compatible number/string casting (the hard 10%)
```

Scripts compile to Python generators that `yield` exactly where scratch-vm's
sequencer yields (once per loop iteration, on waits/glides/sound-play-until-done),
so timing and animation feel match the real VM. Warp-mode procedures run without
yielding until a 500 ms safety budget is exceeded.

## Fidelity notes

TurboWarp-grade semantics: case-insensitive string equality, JavaScript modulo and
rounding behavior, JS number formatting (`1e+21`, `NaN`, `Infinity`), clone cap of
300, broadcast restart rules, timer/greater-than hat edge triggering.

Graphic effects `ghost`, `brightness`, `saturation`, `color`, `fisheye`, `whirl`,
`mosaic` and `pixelate` are implemented, applied in `pixelate -> whirl ->
fisheye -> mosaic -> ghost` order per costume render. Clicking empty stage space
fires `when stage clicked` hats; clicking a sprite fires its `when this sprite
clicked` hats. Sound blocks look names up by name, then by numeric index. Costume
names `next/previous/random costume` and backdrop rewrites
`next/previous/random backdrop` are supported. Loudness always reports `-1` (no
microphone).

## Status

Core blocks, pen and music extensions are implemented. See `tests/` for the
compatibility suite covering casting quirks, parsing and headless execution.

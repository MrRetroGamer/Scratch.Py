# scratch.py

Run **Scratch 3 (`.sb3`) projects natively in Python** — no web player, no
Electron, no browser.

`.sb3` files are just ZIP archives containing `project.json` (the whole program:
sprites, blocks, variables) plus content-addressed assets (`<md5>.png|svg|wav`).
scratch.py parses that format and executes it with a faithful reimplementation
of the scratch-vm scheduler, rendered with pygame-ce.

## Features

- Full core block set (motion, looks, sound, events, control, sensing,
  operators, data) plus custom procedures
- Extensions: pen layer and music synthesis
- Complete graphic effects: `ghost`, `brightness`, `saturation`, `color`,
  `fisheye`, `whirl`, `mosaic`, `pixelate`
- Clones, broadcasts, speech bubbles, variable/list monitors, ask box, and a
  Scratch-style "when stage clicked" event
- PNG and SVG costumes (SVG handled by **resvg**, no system libraries)
- TurboWarp-grade number/string semantics: JS modulo, rounding, `NaN`,
  `Infinity`, `1e+21` formatting, case-insensitive equality
- Headless mode for testing and CI

## Requirements

- Python **3.11+**
- `pygame-ce`, `numpy`, `resvg-py` (installed automatically)

## Installation

```bash
pip install scratch.py
# or, to run from a source checkout:
pip install -e .
```

To develop (adds `pytest` and `ruff`):

```bash
pip install -e ".[dev]"
```

Optional SVG dependencies, if you don't want to use resvg:

```bash
pip install -e ".[svg]"        # cairosvg
pip install -e ".[svg-pure]"   # svglib + reportlab
```

## Quick start

Grab any `.sb3` project file (in Scratch, choose **File → Save to your
computer**, or download one from [Scratch](https://scratch.mit.edu/explore/projects/all)).

```bash
python -m scratch_py path/to/your/project.sb3
# equivalently, after pip install:
scratch-py path/to/your/project.sb3
```

The project starts running immediately. Click the on-screen green flag to start
`when green flag clicked` scripts, or the stop button to halt everything.

## Command line

| Flag | Meaning |
| --- | --- |
| `--scale N` | Window scale factor, 1 = stage fits 480x360 (default `2`) |
| `--turbo` | Run without the 30 FPS frame throttle |
| `--dump` | Print the parsed blocks/scripts and exit (great for debugging) |
| `--headless N` | Simulate N frames with no window, then print final variable/list state |
| `--version` | Print the version and exit |

```bash
python -m scratch_py project.sb3 --dump          # inspect a project
python -m scratch_py project.sb3 --headless 120  # run 120 frames in CI
```

## Window controls

The window opens maximized with a Scratch-style toolbar (green flag / stop)
above the stage.

| Key | Action |
| --- | --- |
| `T` | Toggle turbo mode (inactive while typing) |
| `F` | Toggle fullscreen (inactive while typing) |

Monitors, the ask box and speech bubbles are drawn at native window resolution
with Segoe UI, matching the Scratch editor's look.

## How it works

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

### Fidelity notes

TurboWarp-grade semantics: case-insensitive string equality, JavaScript modulo
and rounding behavior, JS number formatting (`1e+21`, `NaN`, `Infinity`), clone
cap of 300, broadcast restart rules, timer/greater-than hat edge triggering.

Graphic effects are applied in `pixelate -> whirl -> fisheye -> mosaic -> ghost`
order per costume render. Clicking empty stage space fires `when stage clicked`
hats; clicking a sprite fires its `when this sprite clicked` hats. Sound blocks
look names up by name, then by numeric index. Costume names
`next/previous/random costume` and backdrop rewrites
`next/previous/random backdrop` are supported. Loudness always reports `-1` (no
microphone).

## Contributing

Contributions are welcome! Here's how to get set up and start.

### 1. Clone and install

```bash
git clone https://github.com/MrRetroGamer/Scratch.Py.git
cd Scratch.Py
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -e ".[dev]"
```

### 2. Run the tests and linter

```bash
python -m pytest              # full compatibility suite
python -m pytest -x test_end_to_end.py  # a single file
python -m ruff check .        # lint
```

The test suite builds `.sb3` projects in memory, so it needs no network or
fixture files — new tests can be added right next to the existing ones.

### 3. Find a good first issue

- Missing or incorrect opcode? They live in `scratch_py/blocks/` — one file per
  category. Add a `@command("opcode_name")` handler and a test.
- Rendering or fidelity bug? Start in `scratch_py/render/` or
  `scratch_py/runtime/`.

### 4. Guidelines

- Keep the fidelity bar: match scratch-vm semantics, don't guess.
- Add a test for every behavior change (`tests/`).
- Run `ruff check .` and keep the suite green before opening a PR.
- Describe the project change and how to reproduce it in the PR.

### Reporting bugs

Open an issue at
https://github.com/MrRetroGamer/Scratch.Py/issues with:

- The exact command you ran
- A minimal repro: the smallest `.sb3` that triggers it, or a short script that
  builds one (see `tests/fixtures.py`)
- The expected vs. actual behavior
- Your `python -m scratch_py --version` output

## Status

Core blocks, pen and music extensions are implemented, with an automated
compatibility suite covering casting quirks, parsing and headless execution.
See the [pre-release notes](https://github.com/MrRetroGamer/Scratch.Py/releases)
for the current release and what changed.

## License

MIT — see [LICENSE](LICENSE).
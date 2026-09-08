import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

from scratch_py.parser.sb3 import load_sb3
from scratch_py.runtime.engine import Runtime
from tests.fixtures import b, make_png, prim_num, prim_string, simple_project, write_sb3


def _rich_project() -> dict:
    project = simple_project({"Actor": {"variables": {}}})
    project["extensions"] = ["pen", "music"]
    project["monitors"] = [
        {
            "id": "/score",
            "mode": "default",
            "opcode": "data_variable",
            "params": {"VARIABLE": "score", "ID": "v_score"},
            "spriteName": None,
            "value": 0,
            "width": 0,
            "height": 0,
            "x": 5,
            "y": 5,
            "visible": True,
            "sliderMin": 0,
            "sliderMax": 100,
            "isDiscrete": True,
        }
    ]
    stage = project["targets"][0]
    stage["variables"]["v_score"] = ["score", 0]
    actor = project["targets"][1]
    actor["costumes"][0]["md5ext"] = "actor.png"
    actor["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="say"),
        "say": b("say", "looks_sayforsecs",
                 inputs={"MESSAGE": prim_string("hello"), "SECS": prim_num("0.2")},
                 parent="gf", nxt="pen"),
        "pen": b("pen", "pen_penDown", parent="say", nxt="mv"),
        "mv": b("mv", "motion_movesteps", inputs={"STEPS": prim_num(50)},
                parent="pen", nxt="stamp"),
        "stamp": b("stamp", "pen_stamp", parent="mv", nxt="ghost"),
        "ghost": b("ghost", "looks_changeeffectby",
                   fields={"EFFECT": ["GHOST", None]},
                   inputs={"CHANGE": prim_num(50)}, parent="stamp", nxt="clone"),
        "clone": b("clone", "control_create_clone_of",
                   inputs={"CLONE_OPTION": [1, [10, "_myself_"]]}, parent="ghost"),
        "onclone": b("onclone", "control_start_as_clone", top_level=True, nxt="inc"),
        "inc": b("inc", "data_changevariableby",
                 fields={"VARIABLE": ["score", "v_score"]},
                 inputs={"VALUE": prim_num(7)}, parent="onclone"),
    }
    return project


def test_full_stack_headless(tmp_path):
    assets = {"actor.png": make_png(96, 100)}
    path = tmp_path / "rich.sb3"
    write_sb3(path, _rich_project(), assets)
    loaded, loaded_assets = load_sb3(str(path))
    rt = Runtime(loaded, loaded_assets)

    from scratch_py.audio.player import AudioPlayer

    rt.audio = AudioPlayer(loaded_assets)
    rt.green_flag()

    from scratch_py.render.renderer import Renderer

    try:
        renderer = Renderer(rt, loaded_assets, scale=2)
    except Exception as exc:
        pytest.skip(f"display unavailable: {exc}")

    renderer.draw_frame()
    for _ in range(60):
        rt.tick()
        rt.advance_time(1 / 30)
        renderer.draw_frame()
    renderer.draw_frame()

    actor = next(t for t in rt.targets if t.name == "Actor" and not t.is_clone)
    expected_dx = 50 * math.cos(math.radians(0))
    assert actor.x == pytest.approx(expected_dx, abs=0.5)
    assert actor.effects["ghost"] == 50
    assert rt.stage.variables["v_score"][1] == 7

    trail = renderer.pen_layer.get_at(
        (int((240 + 25) * renderer._rs), int(180 * renderer._rs)))
    assert trail[3] > 0, "pen trail should have been drawn"

    assert actor.say_text is None, "bubble should clear after say-for-secs"

    monitor = rt.monitors[0]
    assert rt.monitor_value(monitor) == 7

    import pygame

    pygame.quit()


def test_music_synth_renders(tmp_path):
    from scratch_py.extensions import music as synth

    samples = synth.render_note(1, 60, 0.2)
    assert samples.shape[0] == int(44100 * 0.2)
    peak = float(abs(samples).max())
    assert 0 < peak <= 1.0

    drum = synth.render_drum(1, 0.25)
    assert drum.shape[0] > 1000
    assert float(abs(drum).max()) <= 1.0


def _gradient_surface(size=24):
    import pygame

    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    for x in range(size):
        for y in range(size):
            surf.set_at((x, y), (
                x * 255 // (size - 1),
                y * 255 // (size - 1),
                128,
                255,
            ))
    return surf


def test_graphic_effects_transform_costume(tmp_path):
    import pygame

    from scratch_py.render.renderer import Renderer

    pygame.init()
    try:
        pygame.display.set_mode((64, 64))
        base = _gradient_surface()
        before = pygame.image.tobytes(base, "RGBA")
        pixelated = Renderer._pixelate(base, 100)
        whirled = Renderer._whirl(base, 100)
        fisheye = Renderer._fisheye(base, 100)
        mosaic = Renderer._mosaic(base, 40)
        for label, out in (("pixelate", pixelated), ("whirl", whirled),
                           ("fisheye", fisheye), ("mosaic", mosaic)):
            assert out.get_size() == base.get_size(), label
            assert pygame.image.tobytes(out, "RGBA") != before, f"{label} must change pixels"
        # Cover color/saturation paths (make_surface -> pixels_alpha regression).
        hue = Renderer._hue_shift(base, 80)
        sat = Renderer._adjust_saturation(base, 80)
        assert pygame.image.tobytes(hue, "RGBA") != before
        assert pygame.image.tobytes(sat, "RGBA") != before
    finally:
        pygame.quit()


def test_pixelate_reduces_detail():
    import pygame

    from scratch_py.render.renderer import Renderer

    pygame.init()
    try:
        pygame.display.set_mode((64, 64))
        base = _gradient_surface()

        def total_variation(surf):
            total = 0
            for x in range(24 - 1):
                for y in range(24):
                    a, b = surf.get_at((x, y)), surf.get_at((x + 1, y))
                    total += abs(a.r - b.r) + abs(a.g - b.g) + abs(a.b - b.b)
            return total

        flat = Renderer._pixelate(base, 100)
        assert total_variation(flat) < total_variation(base) / 2, (
            "pixelate must flatten local detail"
        )
    finally:
        pygame.quit()


def test_renderer_drag_keep_on_stage(tmp_path):
    from scratch_py.parser.sb3 import load_sb3
    from scratch_py.runtime.engine import Runtime

    project = simple_project({"M": {"blocks": {}}})
    actor = project["targets"][1]
    st = actor["costumes"][0]
    st["md5ext"] = "fence.png"
    actor["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="sx"),
        "sx": b("sx", "motion_setx", inputs={"X": prim_num(5000)}, parent="gf"),
    }
    path = tmp_path / "fence.sb3"
    write_sb3(path, project, {"fence.png": make_png(10, 10)})
    loaded, assets = load_sb3(str(path))
    rt = Runtime(loaded, assets)
    rt.green_flag()
    rt.tick()
    assert rt.targets[1].x == pytest.approx(5000.0), (
        "set x to may move sprites off-stage; only editor dragging is fenced"
    )


def test_cli_version():
    import contextlib
    import io

    from scratch_py.cli import main

    captured = io.StringIO()
    with pytest.raises(SystemExit) as exc:
        with contextlib.redirect_stdout(captured):
            main(["--version"])
    assert exc.value.code == 0
    assert captured.getvalue().strip().startswith("scratch.py")


def _counter_project():
    project = simple_project({"Btn": {"variables": {}}})
    stage = project["targets"][0]
    stage["variables"]["v_runs"] = ["runs", 0]
    actor = project["targets"][1]
    actor["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="wt"),
        "wt": b("wt", "control_wait", inputs={"DURATION": prim_num("10")},
                parent="gf", nxt="inc"),
        "inc": b("inc", "data_changevariableby",
                 fields={"VARIABLE": ["runs", "v_runs"]},
                 inputs={"VALUE": prim_num(1)}, parent="wt"),
    }
    return project


def _make_renderer(tmp_path):
    path = tmp_path / "btn.sb3"
    write_sb3(path, _counter_project())
    loaded, loaded_assets = load_sb3(str(path))
    rt = Runtime(loaded, loaded_assets)
    from scratch_py.render.renderer import Renderer

    try:
        renderer = Renderer(rt, loaded_assets, scale=2)
    except Exception as exc:
        pytest.skip(f"display unavailable: {exc}")
    return rt, renderer


def test_toolbar_buttons(tmp_path):
    import pygame

    rt, renderer = _make_renderer(tmp_path)
    try:
        flag_center = renderer._flag_button_rect().center
        stop_center = renderer._stop_button_rect().center

        renderer._handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"pos": flag_center, "button": 1}))
        assert len(rt.threads) == 1, "flag button should start green-flag scripts"

        renderer._handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"pos": stop_center, "button": 1}))
        assert rt.threads == [], "stop button should kill all threads"
    finally:
        pygame.quit()


def test_typing_not_hijacked_by_hotkeys(tmp_path):
    import pygame

    rt, renderer = _make_renderer(tmp_path)
    token = rt.ask("type here")
    try:
        renderer._handle_event(pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_g, "unicode": "g"}))
        assert renderer._typed == "g", "'g' must be typed, not trigger green flag"
        assert rt.threads == [], "typing must not start scripts"

        renderer._handle_event(pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_t, "unicode": "t"}))
        assert renderer._typed == "gt", "'t' must be typed, not toggle turbo"

        renderer._handle_event(pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_RETURN, "unicode": "\r"}))
        assert token["done"], "Enter submits answer"
        assert rt.answer == "gt"
    finally:
        pygame.quit()


def test_turbo_hotkey_still_works_outside_typing(tmp_path):
    import pygame

    rt, renderer = _make_renderer(tmp_path)
    try:
        was = rt.turbo
        renderer._handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_t}))
        assert rt.turbo != was
    finally:
        pygame.quit()


TRICKY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="40">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#ff0080"/><stop offset="1" stop-color="#00c8ff"/>
</linearGradient></defs>
<path d="M0 0h60v40H0z" fill="url(#g)"/>
<path d="M10 30 Q 30 5 50 30" stroke="#fff" stroke-width="3" fill="none"/>
</svg>"""


def test_svg_backend_renders_gradient_paths():
    from scratch_py.parser.model import Costume
    from scratch_py.render.costumes import CostumeCache

    cache = CostumeCache({"test.svg": TRICKY_SVG.encode()})
    costume = Costume(name="t", md5ext="test.svg", data_format="svg",
                      rotation_center_x=30, rotation_center_y=20)
    loaded = cache.get(costume, rs=2.0)
    if loaded is None:
        pytest.skip("no SVG backend available")
    assert loaded.surface.get_width() == 120
    assert loaded.surface.get_height() == 80
    assert loaded.px_per_unit == 2.0
    center = loaded.surface.get_at((60, 40))
    assert center[3] > 0, "gradient body should have opaque pixels"


def test_svg_rasterizes_higher_at_higher_rs():
    from scratch_py.parser.model import Costume
    from scratch_py.render.costumes import CostumeCache

    cache = CostumeCache({"test.svg": TRICKY_SVG.encode()})
    costume = Costume(name="t", md5ext="test.svg", data_format="svg",
                      rotation_center_x=30, rotation_center_y=20)
    low = cache.get(costume, rs=1.0)
    high = cache.get(costume, rs=3.0)
    if low is None or high is None:
        pytest.skip("no SVG backend available")
    assert low.surface.get_width() == 60
    assert high.surface.get_width() == 180
    assert high.px_per_unit == 3.0


def _menu_project():
    project = simple_project({"M": {"blocks": {}}})
    actor = project["targets"][1]
    actor["costumes"].append({
        "name": "costume2",
        "dataFormat": "png",
        "assetId": "f9a1c175dbe2e5dee472858dd9d67101",
        "md5ext": "f9a1c175dbe2e5dee472858dd9d67101.png",
        "rotationCenterX": 48,
        "rotationCenterY": 50,
    })
    actor["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="sw"),
        "sw": b("sw", "looks_switchcostumeto",
                inputs={"COSTUME": [1, "menu1"]}, parent="gf"),
        "menu1": b("menu1", "looks_costume",
                   fields={"COSTUME": ["costume2", None]}, parent="sw", shadow=True),
    }
    return project


def test_menu_shadow_opcode_no_warning(tmp_path, capsys):
    path = tmp_path / "menu.sb3"
    write_sb3(path, _menu_project())
    loaded, assets = load_sb3(str(path))
    rt = Runtime(loaded, assets)
    rt.green_flag()
    for _ in range(5):
        rt.tick()
    assert rt.targets[1].current_costume == 1, "menu shadow should select costume2"
    captured = capsys.readouterr()
    assert "looks_costume" not in captured.out, "menu shadows must not warn"


def test_overlay_ui_draws_window_space(tmp_path):
    import pygame

    rt, renderer = _make_renderer(tmp_path)
    try:
        rt.stage.variables[next(iter(rt.stage.variables))] = ["runs", 123]
        rt.targets[1].say_text = "hi there"
        rt.targets[1].say_style = "say"
        rt.ask("what?")
        rt.green_flag()
        renderer.draw_frame()

        bar = renderer._ask_bar_rect()
        px = renderer.window.get_at((bar.centerx, bar.centery))
        assert px[0] > 200 and px[1] > 200 and px[2] > 200, "ask bar should be light"

        flag_center = renderer._flag_button_rect().center
        px2 = renderer.window.get_at(flag_center)
        assert px2 != (252, 252, 252), "flag icon should paint over toolbar"
    finally:
        pygame.quit()


def _slider_project():
    project = simple_project({"Btn": {"variables": {}}})
    stage = project["targets"][0]
    stage["variables"]["v_power"] = ["power", 50]
    project["monitors"] = [
        {
            "id": "slider1",
            "mode": "slider",
            "opcode": "data_variable",
            "params": {"VARIABLE": "power", "ID": "v_power"},
            "spriteName": None,
            "value": 50,
            "width": 0,
            "height": 0,
            "x": 5,
            "y": 5,
            "visible": True,
            "sliderMin": 10,
            "sliderMax": 90,
            "isDiscrete": True,
        }
    ]
    return project


def _make_slider_renderer(tmp_path):
    path = tmp_path / "slider.sb3"
    write_sb3(path, _slider_project())
    loaded, loaded_assets = load_sb3(str(path))
    rt = Runtime(loaded, loaded_assets)
    from scratch_py.render.renderer import Renderer

    try:
        renderer = Renderer(rt, loaded_assets, scale=2)
    except Exception as exc:
        pytest.skip(f"display unavailable: {exc}")
    return rt, renderer


def test_set_monitor_value_respects_slider_ranges(tmp_path):
    import pygame

    rt, renderer = _make_slider_renderer(tmp_path)
    try:
        monitor = rt.monitors[0]
        rt.set_monitor_value(monitor, 200)
        assert rt.monitor_value(monitor) == 90, "clamped to sliderMax"
        rt.set_monitor_value(monitor, -5)
        assert rt.monitor_value(monitor) == 10, "clamped to sliderMin"
        rt.set_monitor_value(monitor, 49.6)
        assert rt.monitor_value(monitor) == 50, "discrete sliders round"
    finally:
        pygame.quit()


def test_slider_drag_updates_variable(tmp_path):
    import pygame

    rt, renderer = _make_slider_renderer(tmp_path)
    try:
        renderer.draw_frame()
        assert renderer._slider_rects, "slider monitor should register a drag target"
        entry = next(iter(renderer._slider_rects.values()))
        monitor, track, lo, hi, hit = entry
        assert (lo, hi) == (10, 90), "slider range comes from the project"

        left = (track.x, track.centery)
        renderer._handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"pos": left, "button": 1}))
        assert rt.monitor_value(monitor) == 10, "drag to far left hits sliderMin"

        right = (track.right + 40, track.centery)
        renderer._handle_event(pygame.event.Event(pygame.MOUSEMOTION, {"pos": right}))
        assert rt.monitor_value(monitor) == 90, "dragging past the edge clamps to sliderMax"

        mid = (track.centerx, track.centery)
        renderer._handle_event(pygame.event.Event(pygame.MOUSEMOTION, {"pos": mid}))
        assert rt.monitor_value(monitor) == 50, "track midpoint maps to range midpoint"

        renderer._handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONUP, {"pos": mid, "button": 1}))
        assert renderer._drag_slider is None
    finally:
        pygame.quit()


def test_slider_visible_in_frame(tmp_path):
    import pygame

    rt, renderer = _make_slider_renderer(tmp_path)
    try:
        renderer.draw_frame()
        entry = next(iter(renderer._slider_rects.values()))
        monitor, track, lo, hi, hit = entry
        end_px = renderer.window.get_at((track.x + 1, track.centery))
        assert end_px == (206, 212, 224), "slider track should be drawn"
        thumb_px = renderer.window.get_at(track.center)
        assert thumb_px == (255, 255, 255, 255), "thumb (value=50) sits at track center"
    finally:
        pygame.quit()


def test_render_scale_matches_window(tmp_path):
    import pygame

    rt, renderer = _make_renderer(tmp_path)
    try:
        renderer.draw_frame()
        rect = renderer._stage_rect()
        assert renderer.stage.get_size() == rect.size, "internal surface must be 1:1 with the stage rect"
        assert renderer._rs == min(4.0, max(1.0, round(rect.w / 480 * 4) / 4))
        assert renderer.pen_layer.get_size() == renderer.stage.get_size()
    finally:
        pygame.quit()


def _stamp_project():
    project = simple_project({"Actor": {"variables": {}}})
    project["extensions"] = ["pen"]
    actor = project["targets"][1]
    actor["costumes"] = [
        {
            "name": "Tile", "dataFormat": "png", "assetId": "taaa",
            "md5ext": "tile.png", "bitmapResolution": 1,
            "rotationCenterX": 5, "rotationCenterY": 5,
        },
        {
            "name": "Gem", "dataFormat": "png", "assetId": "tbbb",
            "md5ext": "gem.png", "bitmapResolution": 1,
            "rotationCenterX": 5, "rotationCenterY": 5,
        },
    ]
    actor["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="k"),
        "k": b("k", "control_wait", inputs={"DURATION": prim_num("0.05")},
               parent="gf", nxt="hide"),
        "hide": b("hide", "looks_hide", parent="k", nxt="sw"),
        "sw": b("sw", "looks_switchcostumeto", inputs={"COSTUME": [1, "m1"]},
                parent="hide", nxt="st"),
        "m1": b("m1", "looks_costume", fields={"COSTUME": ["Gem", None]},
                parent="sw", shadow=True),
        "st": b("st", "pen_stamp", parent="sw"),
    }
    return project


def test_stamp_uses_current_costume_after_switch(tmp_path):
    import pygame

    from scratch_py.render.renderer import STAGE_H, STAGE_W, Renderer

    path = tmp_path / "stamp.sb3"
    write_sb3(path, _stamp_project(),
              {"tile.png": make_png(10, 10, (200, 200, 200, 255)),
               "gem.png": make_png(10, 10, (0, 255, 0, 255))})
    loaded, assets = load_sb3(str(path))
    rt = Runtime(loaded, assets)
    try:
        renderer = Renderer(rt, assets, scale=2)
    except Exception as exc:
        pytest.skip(f"display unavailable: {exc}")
    rt.green_flag()
    try:
        # first frame renders the sprite as Tile, seeding a (stale) info cache
        rt.tick()
        rt.advance_time(1 / 30)
        renderer.draw_frame()
        for _ in range(6):
            rt.tick()
            rt.advance_time(1 / 30)
            renderer.draw_frame()
        rs = renderer._rs
        center = (int((0 + STAGE_W / 2) * rs), int((STAGE_H / 2 - 0) * rs))
        px = renderer.pen_layer.get_at(center)
        assert px[0] == 0 and px[1] == 255 and px[2] == 0, (
            "pen_stamp after switch costume must stamp the NEW costume (Gem), "
            "not the stale Tile rendered last frame"
        )
    finally:
        pygame.quit()


def _clone_touch_project():
    project = simple_project({"Bullet": {"variables": {}}, "Enemy": {"variables": {}}})
    stage = project["targets"][0]
    stage["variables"]["v_hit"] = ["hit", 0]
    bullets, enemy = project["targets"][1], project["targets"][2]

    def mc(p):
        return {"name": "c", "dataFormat": "png", "assetId": p, "md5ext": p + ".png",
                "bitmapResolution": 1, "rotationCenterX": 5, "rotationCenterY": 5}

    bullets["costumes"] = [mc("b")]
    enemy["costumes"] = [mc("e")]
    enemy["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="cl"),
        "cl": b("cl", "control_create_clone_of",
                inputs={"CLONE_OPTION": [1, [10, "_myself_"]]}, parent="gf"),
        "oc": b("oc", "control_start_as_clone", top_level=True, nxt="pos"),
        "pos": b("pos", "motion_gotoxy",
                 inputs={"X": prim_num(0), "Y": prim_num(3)}, parent="oc"),
    }
    # Bullet clone: if touching the (clone of) Enemy, set hit=1.
    bullets["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="cl"),
        "cl": b("cl", "control_create_clone_of",
                inputs={"CLONE_OPTION": [1, [10, "_myself_"]]}, parent="gf"),
        "oc": b("oc", "control_start_as_clone", top_level=True, nxt="to"),
        "to": b("to", "motion_gotoxy",
                inputs={"X": prim_num(0), "Y": prim_num(0)}, parent="oc", nxt="if1"),
        "if1": b("if1", "control_if",
                 inputs={
                     "CONDITION": [2, "cond1"],
                     "SUBSTACK": [2, "then1"],
                 }, parent="to"),
        "cond1": b("cond1", "sensing_touchingobject",
                   inputs={"TOUCHINGOBJECTMENU": [1, "tm1"]}, parent="if1"),
        "tm1": b("tm1", "sensing_touchingobjectmenu",
                 fields={"TOUCHINGOBJECTMENU": ["Enemy", "x"]}, parent="cond1", shadow=True),
        "then1": b("then1", "data_setvariableto",
                   fields={"VARIABLE": ["hit", "v_hit"]},
                   inputs={"VALUE": prim_num(1)}, parent="if1"),
    }
    return project, {"b.png": make_png(10, 10, (255, 0, 0, 255)),
                     "e.png": make_png(10, 10, (0, 0, 255, 255))}


def test_clone_aware_touching_and_fresh_position(tmp_path):
    import pygame

    from scratch_py.render.renderer import Renderer

    project, assets = _clone_touch_project()
    path = tmp_path / "ctouch.sb3"
    write_sb3(path, project, assets)
    loaded, loaded_assets = load_sb3(str(path))
    rt = Runtime(loaded, loaded_assets)
    try:
        renderer = Renderer(rt, loaded_assets, scale=2)
    except Exception as exc:
        pytest.skip(f"display unavailable: {exc}")
    rt.green_flag()
    # The Bullet clone overlaps the Enemy clone (bullet at 0,0; enemy clone 0,3):
    # the touching check must see the neonate clone, not only the hidden original.
    for _ in range(5):
        rt.tick()
        rt.advance_time(1 / 30)
        renderer.draw_frame()
    hit = rt.stage.variables["v_hit"][1]
    assert int(hit) == 1, f"touching (sprite v) must consider clones; v_hit={hit}"

    # Fresh-position sensing: teleport the bullet far away and probe with NO draw in
    # between. The info cache must detect the moved position and re-render.
    bullet = next(t for t in rt.targets if t.name == "Bullet" and t.is_clone)
    enemy_clone = next(t for t in rt.targets if t.name == "Enemy" and t.is_clone)
    bullet.x, bullet.y = 300.0, 0.0
    assert renderer.sprites_touching(bullet, enemy_clone) is False, (
        "collision sensing must use the sprite's current position, not last frame's"
    )
    pygame.quit()

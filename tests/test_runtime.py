
import pytest

from scratch_py.parser.sb3 import load_sb3
from scratch_py.runtime.engine import Runtime
from tests.fixtures import (
    b,
    block_ref,
    prim_num,
    prim_string,
    prim_var,
    simple_project,
    write_sb3,
)


def _run(tmp_path, project_dict, frames=120, step=0.0):
    path = tmp_path / "proj.sb3"
    write_sb3(path, project_dict)
    loaded, assets = load_sb3(str(path))
    rt = Runtime(loaded, assets)
    rt.green_flag()
    for _ in range(frames):
        rt.tick()
        if step:
            rt.advance_time(step)
    return rt


def var_value(rt, target_index: int, var_name: str):
    tgt = rt.targets[target_index]
    for entry in tgt.variables.values():
        if entry[0] == var_name:
            return entry[1]
    return None


def test_broadcast_and_wait_flow(tmp_path):
    project = simple_project({"Sprite1": {"variables": {"v_fin": ["finished", 0]}}})
    stage = project["targets"][0]
    stage["broadcasts"]["bid1"] = "msg1"
    stage["variables"]["v_score"] = ["score", 0]
    sprite = project["targets"][1]
    sprite["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="set1"),
        "set1": b("set1", "data_setvariableto",
                  fields={"VARIABLE": ["score", "v_score"]},
                  inputs={"VALUE": prim_num(0)}, parent="gf", nxt="rep1"),
        "rep1": b("rep1", "control_repeat",
                  inputs={"TIMES": prim_num(3), "SUBSTACK": block_ref("ch1")},
                  parent="set1", nxt="waitb"),
        "ch1": b("ch1", "data_changevariableby",
                 fields={"VARIABLE": ["score", "v_score"]},
                 inputs={"VALUE": prim_num(2)}, parent="rep1"),
        "waitb": b("waitb", "event_broadcastandwait",
                   inputs={"BROADCAST_INPUT": [1, [11, "msg1"]]},
                   parent="rep1", nxt="check"),
        "check": b("check", "control_if",
                   inputs={"CONDITION": block_ref("eq"), "SUBSTACK": block_ref("done")},
                   parent="waitb"),
        "eq": b("eq", "operator_equals",
                inputs={"OPERAND1": block_ref("varscore"), "OPERAND2": prim_num(16)},
                parent="check"),
        "varscore": b("varscore", "data_variable",
                      fields={"VARIABLE": ["score", "v_score"]}, parent="eq", shadow=True),
        "done": b("done", "data_setvariableto",
                  fields={"VARIABLE": ["finished", "v_fin"]},
                  inputs={"VALUE": prim_string("ok")}, parent="check"),
        "recv": b("recv", "event_whenbroadcastreceived",
                  fields={"BROADCAST_OPTION": ["msg1", "bid1"]}, top_level=True, nxt="add10"),
        "add10": b("add10", "data_changevariableby",
                   fields={"VARIABLE": ["score", "v_score"]},
                   inputs={"VALUE": prim_num(10)}, parent="recv"),
    }
    rt = _run(tmp_path, project)
    assert var_value(rt, 0, "score") == 16
    assert var_value(rt, 1, "finished") == "ok"


def test_procedure_call_with_argument(tmp_path):
    project = simple_project({"Sprite1": {"variables": {"v_steps": ["steps", 0]}}})
    sprite = project["targets"][1]
    sprite["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="call1"),
        "call1": b(
            "call1", "procedures_call", top_level=False,
            mutation={
                "tagName": "mutation",
                "proccode": "jump %s",
                "argumentids": '["arg1"]',
                "children": [],
            },
            inputs={"arg1": prim_num(5)},
            parent="gf",
        ),
        "defn": b("defn", "procedures_definition", top_level=True,
                  inputs={"custom_block": [1, "proto"]}, nxt="body1"),
        "proto": b("proto", "procedures_prototype", parent="defn", shadow=True,
                   mutation={
                       "tagName": "mutation",
                       "proccode": "jump %s",
                       "argumentnames": '["n"]',
                       "argumentdefaults": '["50"]',
                       "argumentids": '["arg1"]',
                       "warp": "false",
                       "children": [],
                   }),
        "body1": b("body1", "data_changevariableby",
                   fields={"VARIABLE": ["steps", "v_steps"]},
                   inputs={"VALUE": [2, "argrep"]}, parent="defn"),
        "argrep": b("argrep", "argument_reporter_string_number",
                    fields={"VALUE": ["n"]}, parent="body1", shadow=True),
    }
    rt = _run(tmp_path, project)
    assert var_value(rt, 1, "steps") == 5


def test_clone_lifecycle(tmp_path):
    project = simple_project({"Sprite1": {"variables": {}}})
    stage = project["targets"][0]
    stage["variables"]["v_count"] = ["clone_count", 0]
    sprite = project["targets"][1]
    sprite["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="mk"),
        "mk": b("mk", "control_create_clone_of",
                inputs={"CLONE_OPTION": [1, [10, "_myself_"]]}, parent="gf"),
        "onclone": b("onclone", "control_start_as_clone", top_level=True, nxt="inc"),
        "inc": b("inc", "data_changevariableby",
                 fields={"VARIABLE": ["clone_count", "v_count"]},
                 inputs={"VALUE": prim_num(1)}, parent="onclone", nxt="delme"),
        "delme": b("delme", "control_delete_this_clone", parent="inc"),
    }
    rt = _run(tmp_path, project, frames=60)
    assert var_value(rt, 0, "clone_count") == 1
    clone_count = sum(1 for t in rt.targets if t.is_clone)
    assert clone_count == 0


def test_motion_and_glide_timing(tmp_path):
    project = simple_project({"Mover": {"blocks": {}}})
    mover = project["targets"][1]
    mover["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="g"),
        "g": b("g", "motion_glidesecstoxy",
               inputs={"SECS": prim_num("0.2"), "X": prim_num(100), "Y": prim_num(-50)},
               parent="gf", nxt="mv"),
        "mv": b("mv", "motion_movesteps", inputs={"STEPS": prim_num(10)}, parent="g"),
    }
    rt = _run(tmp_path, project, frames=40, step=1 / 30)
    mover_state = rt.targets[1]
    import math

    expected_x = 100 + 10 * math.cos(math.radians(0))
    assert mover_state.x == pytest.approx(expected_x)
    assert mover_state.y == pytest.approx(-50 + 10 * math.sin(math.radians(0)))


def test_glide_interpolates(tmp_path):
    import math as m

    project = simple_project({"M": {"blocks": {}}})
    mvt = project["targets"][1]
    mvt["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="g"),
        "g": b("g", "motion_glidesecstoxy",
               inputs={"SECS": prim_num("1"), "X": prim_num(100), "Y": prim_num(0)},
               parent="gf"),
    }
    path = tmp_path / "g.sb3"
    write_sb3(path, project)
    loaded, assets = load_sb3(str(path))
    rt = Runtime(loaded, assets)
    rt.green_flag()
    rt.tick()
    positions = []
    for _ in range(5):
        rt.advance_time(0.25)
        rt.tick()
        positions.append(rt.targets[1].x)
    assert positions[0] == pytest.approx(100 * (0.25 / 1.0), abs=2.0)
    assert all(a <= b for a, b in zip(positions, positions[1:], strict=False))
    assert m.cos(0) == 1


def test_wait_block_uses_virtual_time(tmp_path):
    project = simple_project({"W": {"variables": {}}})
    stage = project["targets"][0]
    stage["variables"]["v_after"] = ["after", 0]
    w = project["targets"][1]
    w["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="wt"),
        "wt": b("wt", "control_wait", inputs={"DURATION": prim_num("0.5")},
                parent="gf", nxt="set"),
        "set": b("set", "data_setvariableto",
                 fields={"VARIABLE": ["after", "v_after"]},
                 inputs={"VALUE": prim_string("yes")}, parent="wt"),
    }
    rt = _run(tmp_path, project, frames=10)
    assert var_value(rt, 0, "after") == 0
    for _ in range(20):
        rt.advance_time(1 / 30)
        rt.tick()
    assert var_value(rt, 0, "after") == "yes"


def test_key_hat_fires(tmp_path):
    project = simple_project({"K": {"variables": {}}})
    stage = project["targets"][0]
    stage["variables"]["v_hits"] = ["hits", 0]
    k = project["targets"][1]
    k["blocks"] = {
        "kh": b("kh", "event_whenkeypressed",
                fields={"KEY_OPTION": ["space", None]}, top_level=True, nxt="add"),
        "add": b("add", "data_changevariableby",
                 fields={"VARIABLE": ["hits", "v_hits"]},
                 inputs={"VALUE": prim_num(1)}, parent="kh"),
    }
    path = tmp_path / "k.sb3"
    write_sb3(path, project)
    loaded, assets = load_sb3(str(path))
    rt = Runtime(loaded, assets)
    rt.green_flag()
    rt.post_event("keydown", "space")
    for _ in range(5):
        rt.tick()
    assert var_value(rt, 0, "hits") == 1


def test_stop_this_script(tmp_path):
    project = simple_project({"S": {"variables": {}}})
    stage = project["targets"][0]
    stage["variables"]["v_n"] = ["n", 0]
    s = project["targets"][1]
    s["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="c1"),
        "c1": b("c1", "data_changevariableby",
                fields={"VARIABLE": ["n", "v_n"]},
                inputs={"VALUE": prim_num(1)}, parent="gf", nxt="st"),
        "st": b("st", "control_stop", fields={"STOP_OPTION": ["this script", None],
                                              "STOP_MENU": ["stop", None]},
                parent="c1", nxt="never"),
        "never": b("never", "data_changevariableby",
                   fields={"VARIABLE": ["n", "v_n"]},
                   inputs={"VALUE": prim_num(100)}, parent="st"),
    }
    rt = _run(tmp_path, project)
    assert var_value(rt, 0, "n") == 1


def test_list_operations(tmp_path):
    project = simple_project({"L": {"variables": {}}})
    stage = project["targets"][0]
    stage["lists"]["v_items"] = ["items", []]
    s = project["targets"][1]
    s["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="a1"),
        "a1": b("a1", "data_addtolist", fields={"LIST": ["items", "v_items"]},
                inputs={"ITEM": prim_string("x")}, parent="gf", nxt="a2"),
        "a2": b("a2", "data_addtolist", fields={"LIST": ["items", "v_items"]},
                inputs={"ITEM": prim_string("y")}, parent="a1", nxt="i1"),
        "i1": b("i1", "data_insertatlist", fields={"LIST": ["items", "v_items"]},
                inputs={"INDEX": prim_num(1), "ITEM": prim_string("start")},
                parent="a2", nxt="r1"),
        "r1": b("r1", "data_replaceitemoflist", fields={"LIST": ["items", "v_items"]},
                inputs={"INDEX": prim_num(3), "ITEM": prim_string("end")},
                parent="i1"),
    }
    rt = _run(tmp_path, project)
    assert list(rt.stage.lists.values())[0][1] == ["start", "x", "end"]


def test_inline_variable_primitive_order(tmp_path):
    """Regression: sb3 variable primitives are [12, NAME, ID]. This mirrors the
    'Life Simulator' clock pattern: set total to (hours * 60) + minutes."""
    project = simple_project({"Calc": {"variables": {}}})
    stage = project["targets"][0]
    stage["variables"]["v_h"] = ["Local Hour", 7]
    stage["variables"]["v_m"] = ["Local Minute", 28]
    stage["variables"]["v_t"] = ["Total Minutes", 0]
    s = project["targets"][1]
    s["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="set"),
        "set": b("set", "data_setvariableto",
                 fields={"VARIABLE": ["Total Minutes", "v_t"]},
                 inputs={"VALUE": [2, "add"]}, parent="gf"),
        "add": b("add", "operator_add",
                 inputs={"NUM1": [2, "mul"], "NUM2": prim_var("Local Minute", "v_m")},
                 parent="set"),
        "mul": b("mul", "operator_multiply",
                 inputs={"NUM1": prim_var("Local Hour", "v_h"), "NUM2": prim_num(60)},
                 parent="add"),
    }
    rt = _run(tmp_path, project)
    assert var_value(rt, 0, "Total Minutes") == 7 * 60 + 28


def test_no_junk_variables_created(tmp_path):
    project = simple_project({"Calc": {"variables": {}}})
    stage = project["targets"][0]
    stage["variables"]["v_a"] = ["alpha", 3]
    s = project["targets"][1]
    s["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="set"),
        "set": b("set", "data_setvariableto",
                 fields={"VARIABLE": ["alpha", "v_a"]},
                 inputs={"VALUE": prim_var("alpha", "v_a")}, parent="gf"),
    }
    rt = _run(tmp_path, project)
    assert len(rt.stage.variables) == 1, "no auto-created junk variables"
    assert var_value(rt, 0, "alpha") == 3


def test_stage_click_hat(tmp_path):
    """Clicking empty stage fires `when stage clicked`; clicking a sprite must not."""
    project = simple_project({"S": {"variables": {}}})
    stage = project["targets"][0]
    stage["variables"]["v_clicks"] = ["clicks", 0]
    stage["blocks"] = {
        "sc": b("sc", "event_whenstageclicked", top_level=True, nxt="inc"),
        "inc": b("inc", "data_changevariableby",
                 fields={"VARIABLE": ["clicks", "v_clicks"]},
                 inputs={"VALUE": prim_num(1)}, parent="sc"),
    }
    path = tmp_path / "stage.sb3"
    write_sb3(path, project)
    loaded, assets = load_sb3(str(path))
    rt = Runtime(loaded, assets)
    rt.green_flag()

    def _click(x, y):
        rt.post_event("click", (x, y))
        rt.tick()

    _click(200.0, 200.0)
    assert var_value(rt, 0, "clicks") == 1, "empty-stage click must fire the stage hat"
    _click(-200.0, 150.0)
    assert var_value(rt, 0, "clicks") == 2


def test_sprite_click_does_not_fire_stage(tmp_path):
    project = simple_project({"S": {"variables": {}}})
    stage = project["targets"][0]
    stage["variables"]["v_clicks"] = ["clicks", 0]
    stage["blocks"] = {
        "sc": b("sc", "event_whenstageclicked", top_level=True, nxt="inc"),
        "inc": b("inc", "data_changevariableby",
                 fields={"VARIABLE": ["clicks", "v_clicks"]},
                 inputs={"VALUE": prim_num(1)}, parent="sc"),
    }
    path = tmp_path / "sprite.sb3"
    write_sb3(path, project)
    loaded, assets = load_sb3(str(path))
    rt = Runtime(loaded, assets)

    from scratch_py.render.renderer import Renderer

    try:
        renderer = Renderer(rt, assets, scale=2)
    except Exception as exc:
        pytest.skip(f"display unavailable: {exc}")
    try:
        import pygame

        sprite = rt.targets[1]
        sprite.visible = True
        sprite.x = 0.0
        sprite.y = 0.0
        rt.green_flag()
        # A click centered on the visible sprite hits the sprite, not the stage.
        renderer.draw_frame()
        local = renderer._to_stage(renderer._stage_rect().center)
        rt._handle_click(local[0], local[1])
        assert var_value(rt, 0, "clicks") == 0, "sprite click must not fire stage hat"
    finally:
        import pygame

        pygame.quit()


def test_sound_numeric_index_fallback():
    from scratch_py.blocks.sound import _sound_index
    from scratch_py.parser.model import Sound

    class FakeData:
        sounds = [
            Sound(name="pop", md5ext="a.wav", data_format="wav"),
            Sound(name="click", md5ext="b.wav", data_format="wav"),
        ]

    class FakeTgt:
        data = FakeData()

    assert _sound_index(None, FakeTgt(), "pop") == 0
    assert _sound_index(None, FakeTgt(), "click") == 1
    assert _sound_index(None, FakeTgt(), "1") == 1, "numeric names fall back to index"
    assert _sound_index(None, FakeTgt(), "9") is None, "out-of-range index is rejected"
    assert _sound_index(None, FakeTgt(), "nope") is None


def test_special_costume_names(tmp_path):
    project = simple_project({"C": {"blocks": {}}})
    actor = project["targets"][1]
    actor["costumes"] = [
        {"name": "a", "dataFormat": "png", "assetId": "a", "md5ext": "a.png",
         "rotationCenterX": 5, "rotationCenterY": 5},
        {"name": "b", "dataFormat": "png", "assetId": "b", "md5ext": "b.png",
         "rotationCenterX": 5, "rotationCenterY": 5},
    ]
    actor["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="sw"),
        "sw": b("sw", "looks_switchcostumeto",
                inputs={"COSTUME": prim_string("next costume")}, parent="gf", nxt="sw2"),
        "sw2": b("sw2", "looks_switchcostumeto",
                 inputs={"COSTUME": prim_string("previous costume")}, parent="sw", nxt="sw3"),
        "sw3": b("sw3", "looks_switchcostumeto",
                 inputs={"COSTUME": prim_string("random costume")}, parent="sw2"),
    }
    rt = _run(tmp_path, project)
    assert rt.targets[1].current_costume in (0, 1), "random costume picks a valid index"


def test_menu_opcodes_registered():
    from scratch_py.blocks import get_handler

    for opcode in ("sensing_touchingobjectmenu", "sensing_distancetomenu",
                   "control_create_clone_of_menu", "motion_glideto",
                   "event_broadcast_menu", "sound_sounds_menu"):
        assert get_handler(opcode) is not None, f"{opcode} must resolve to the menu handler"


def test_warp_procedure_with_repeat(tmp_path):
    """Regression for Mines: a 'run without screen refresh' procedure whose body
    contains a repeat loop must execute fully without touching the warp budget."""
    project = simple_project({"Calc": {"variables": {}}})
    stage = project["targets"][0]
    stage["variables"]["v_n"] = ["count", 0]
    s = project["targets"][1]
    s["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="call1"),
        "call1": b("call1", "procedures_call",
                   mutation={"proccode": "run %s", "argumentids": "[]"},
                   parent="gf"),
        "defn": b("defn", "procedures_definition", top_level=True,
                  inputs={"custom_block": [1, "proto"]}, nxt="rep"),
        "proto": b("proto", "procedures_prototype", parent="defn", shadow=True,
                   mutation={"proccode": "run %s", "argumentnames": "[]",
                             "argumentids": "[]", "warp": "true"}),
        "rep": b("rep", "control_repeat",
                 inputs={"TIMES": prim_num(5), "SUBSTACK": block_ref("inc")},
                 parent="defn"),
        "inc": b("inc", "data_changevariableby",
                 fields={"VARIABLE": ["count", "v_n"]},
                 inputs={"VALUE": prim_num(1)}, parent="rep"),
    }
    path = tmp_path / "warp.sb3"
    write_sb3(path, project)
    loaded, assets = load_sb3(str(path))
    rt = Runtime(loaded, assets)
    rt.green_flag()
    rt.tick()
    assert var_value(rt, 0, "count") == 5, "warp procedure finishes within one tick"


def test_huge_warp_loop_yields_and_resumes(tmp_path):
    """A warp loop too big for one frame must yield at the deadline and keep
    making progress on subsequent ticks instead of freezing the player."""
    project = simple_project({"Calc": {"variables": {}}})
    stage = project["targets"][0]
    stage["variables"]["v_n"] = ["count", 0]
    s = project["targets"][1]
    s["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="rep"),
        "rep": b("rep", "control_repeat",
                 inputs={"TIMES": prim_num(500000), "SUBSTACK": block_ref("inc")},
                 parent="gf"),
        "inc": b("inc", "data_changevariableby",
                 fields={"VARIABLE": ["count", "v_n"]},
                 inputs={"VALUE": prim_num(1)}, parent="rep"),
    }
    path = tmp_path / "huge.sb3"
    write_sb3(path, project)
    loaded, assets = load_sb3(str(path))
    rt = Runtime(loaded, assets)
    rt.green_flag()
    rt.tick()
    first = var_value(rt, 0, "count")
    assert 0 < first < 500000, "deadline must stop the loop within one tick"
    rt.tick()
    rt.tick()
    second = var_value(rt, 0, "count")
    assert second > first, "warp loop resumes on the next tick"


def test_nested_warp_procs_no_budget_multiplication(tmp_path):
    project = simple_project({"Calc": {"variables": {}}})
    stage = project["targets"][0]
    stage["variables"]["v_n"] = ["count", 0]
    s = project["targets"][1]
    s["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="outer"),
        "outer": b("outer", "procedures_call",
                   mutation={"proccode": "outer %s", "argumentids": "[]"},
                   parent="gf"),
        "odef": b("odef", "procedures_definition", top_level=True,
                  inputs={"custom_block": [1, "oproto"]}, nxt="inner"),
        "oproto": b("oproto", "procedures_prototype", parent="odef", shadow=True,
                    mutation={"proccode": "outer %s", "argumentnames": "[]",
                              "argumentids": "[]", "warp": "true"}),
        "inner": b("inner", "procedures_call",
                   mutation={"proccode": "inner %s", "argumentids": "[]"},
                   parent="odef"),
        "idef": b("idef", "procedures_definition", top_level=True,
                  inputs={"custom_block": [1, "iproto"]}, nxt="irep"),
        "iproto": b("iproto", "procedures_prototype", parent="idef", shadow=True,
                    mutation={"proccode": "inner %s", "argumentnames": "[]",
                              "argumentids": "[]", "warp": "true"}),
        "irep": b("irep", "control_repeat",
                  inputs={"TIMES": prim_num(300000), "SUBSTACK": block_ref("inc")},
                  parent="idef"),
        "inc": b("inc", "data_changevariableby",
                 fields={"VARIABLE": ["count", "v_n"]},
                 inputs={"VALUE": prim_num(1)}, parent="irep"),
    }
    path = tmp_path / "nested.sb3"
    write_sb3(path, project)
    loaded, assets = load_sb3(str(path))
    rt = Runtime(loaded, assets)
    rt.green_flag()
    import time as time_mod

    t1 = time_mod.perf_counter()
    rt.tick()
    elapsed = time_mod.perf_counter() - t1
    assert elapsed < 0.4, f"nested warp must respect the shared deadline, took {elapsed:.3f}s"
    assert var_value(rt, 0, "count") > 0, "inner loop made progress"


def test_pen_segments_captured_under_warp(tmp_path):
    """Pen must draw every movement inside a warp loop, not just one segment
    per tick (regression for FAST EARTH artwork)."""
    project = simple_project({"Draw": {"variables": {}}})
    s = project["targets"][1]
    s["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="down"),
        "down": b("down", "pen_penDown", parent="gf", nxt="rep"),
        "rep": b("rep", "control_repeat",
                 inputs={"TIMES": prim_num(2), "SUBSTACK": block_ref("mv")},
                 parent="down"),
        "mv": b("mv", "motion_movesteps", inputs={"STEPS": prim_num(5)},
                parent="rep", nxt="turn"),
        "turn": b("turn", "motion_turnright",
                  inputs={"DEGREES": prim_num(90)}, parent="mv"),
    }
    path = tmp_path / "pen.sb3"
    write_sb3(path, project)
    loaded, assets = load_sb3(str(path))
    rt = Runtime(loaded, assets)

    from scratch_py.render.renderer import Renderer

    try:
        renderer = Renderer(rt, assets, scale=2)
    except Exception as exc:
        pytest.skip(f"display unavailable: {exc}")
    try:
        rt.green_flag()
        rt.tick()
        rt.advance_time(1 / 30)
        rt.tick()
        rt.advance_time(1 / 30)
        renderer.draw_frame()
        rs = renderer._rs
        corner = renderer.pen_layer.get_at((int((240 + 5) * rs), int((180 + 2.5) * rs)))
        assert corner[3] > 0, "the corner of the L-path must be drawn (mid-move segment)"
    finally:
        import pygame

        pygame.quit()


def test_script_error_isolation(tmp_path, capsys):
    """A broken script must not crash the player: it stops alone, the traceback
    is reported, and other scripts keep running."""
    project = simple_project({"Broken": {}, "Healthy": {"variables": {}}})
    stage = project["targets"][0]
    stage["variables"]["v_ok"] = ["ok", 0]
    broken = project["targets"][1]
    broken["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="boom"),
        "boom": b("boom", "data_setvariableto",
                  fields={"VARIABLE": ["x", None]},
                  inputs={"VALUE": prim_string("never")}, parent="gf"),
    }
    healthy = project["targets"][2]
    healthy["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="inc"),
        "inc": b("inc", "data_changevariableby",
                 fields={"VARIABLE": ["ok", "v_ok"]},
                 inputs={"VALUE": prim_num(1)}, parent="gf"),
    }
    path = tmp_path / "iso.sb3"
    write_sb3(path, project)
    loaded, assets = load_sb3(str(path))
    rt = Runtime(loaded, assets)

    from scratch_py import blocks as blocks_mod
    from scratch_py.blocks import Handler

    original = blocks_mod.HANDLERS["data_setvariableto"]

    def explode(rt, tgt, block):
        raise RuntimeError("boom")

    blocks_mod.HANDLERS["data_setvariableto"] = Handler("data_setvariableto", "command", explode)
    try:
        rt.green_flag()
        for _ in range(10):
            rt.tick()
            rt.advance_time(1 / 30)
    finally:
        blocks_mod.HANDLERS["data_setvariableto"] = original

    assert var_value(rt, 0, "ok") == 1, "healthy script must keep running"
    captured = capsys.readouterr()
    assert "error in script 'event_whenflagclicked' on target 'Broken'" in captured.out
    assert "RuntimeError: boom" in captured.err


def test_every_exception_is_printed(tmp_path, capsys):
    """No dedup: a script that fails on multiple ticks reports every failure."""
    project = simple_project({"Broken": {"variables": {}}})
    broken = project["targets"][1]
    broken["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="w"),
        "w": b("w", "control_wait", inputs={"DURATION": prim_num("0.01")},
               parent="gf", nxt="boom"),
        "boom": b("boom", "data_setvariableto",
                  fields={"VARIABLE": ["x", None]},
                  inputs={"VALUE": prim_string("never")}, parent="w"),
    }
    path = tmp_path / "spam.sb3"
    write_sb3(path, project)
    loaded, assets = load_sb3(str(path))
    rt = Runtime(loaded, assets)

    from scratch_py import blocks as blocks_mod
    from scratch_py.blocks import Handler

    original = blocks_mod.HANDLERS["data_setvariableto"]

    def explode(rt, tgt, block):
        raise RuntimeError("kapow")

    blocks_mod.HANDLERS["data_setvariableto"] = Handler("data_setvariableto", "command", explode)

    blocks_mod.HANDLERS["data_setvariableto"] = Handler("data_setvariableto", "command", explode)
    try:
        for _ in range(3):
            rt.green_flag()
            rt.tick()
            rt.advance_time(0.02)
            rt.tick()
        reports = capsys.readouterr().out.count("error in script")
    finally:
        blocks_mod.HANDLERS["data_setvariableto"] = original
    assert reports >= 3, f"expected repeated reports, got {reports}"


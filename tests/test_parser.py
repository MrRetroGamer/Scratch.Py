from scratch_py.parser.deserialize import ScriptDumper
from scratch_py.parser.sb3 import SB3Error, load_sb3
from tests.fixtures import b, block_ref, prim_num, prim_string, simple_project, write_sb3


def _broadcast_demo_project() -> dict:
    project = simple_project({"Sprite1": {"variables": {"v_fin": ["finished", 0]}}})
    stage = project["targets"][0]
    stage["broadcasts"]["bid1"] = "msg1"
    stage["variables"]["v_score"] = ["score", 0]

    sprite = project["targets"][1]
    sprite["blocks"] = {
        "gf": b("gf", "event_whenflagclicked", top_level=True, nxt="set1"),
        "set1": b(
            "set1", "data_setvariableto",
            fields={"VARIABLE": ["score", "v_score"]},
            inputs={"VALUE": prim_num(0)},
            parent="gf", nxt="rep1",
        ),
        "rep1": b(
            "rep1", "control_repeat",
            inputs={"TIMES": prim_num(3), "SUBSTACK": block_ref("ch1")},
            parent="set1", nxt="waitb",
        ),
        "ch1": b(
            "ch1", "data_changevariableby",
            fields={"VARIABLE": ["score", "v_score"]},
            inputs={"VALUE": prim_num(2)},
            parent="rep1",
        ),
        "waitb": b("waitb", "event_broadcastandwait",
                   inputs={"BROADCAST_INPUT": [1, [11, "msg1"]]},
                   parent="rep1", nxt="check"),
        "check": b(
            "check", "control_if",
            inputs={"CONDITION": block_ref("eq"), "SUBSTACK": block_ref("done")},
            parent="waitb",
        ),
        "eq": b("eq", "operator_equals",
                inputs={"OPERAND1": block_ref("varscore"), "OPERAND2": prim_num(16)},
                parent="check"),
        "varscore": b("varscore", "data_variable",
                      fields={"VARIABLE": ["score", "v_score"]}, parent="eq", shadow=True),
        "done": b(
            "done", "data_setvariableto",
            fields={"VARIABLE": ["finished", "v_fin"]},
            inputs={"VALUE": prim_string("ok")}, parent="check",
        ),
        "recv": b("recv", "event_whenbroadcastreceived",
                  fields={"BROADCAST_OPTION": ["msg1", "bid1"]}, top_level=True, nxt="add10"),
        "add10": b(
            "add10", "data_changevariableby",
            fields={"VARIABLE": ["score", "v_score"]},
            inputs={"VALUE": prim_num(10)}, parent="recv",
        ),
    }
    return project


def _build(tmp_path):
    path = tmp_path / "demo.sb3"
    write_sb3(path, _broadcast_demo_project())
    return load_sb3(str(path))


def test_parse_roundtrip(tmp_path):
    loaded, assets = _build(tmp_path)
    assert len(loaded.targets) == 2
    assert loaded.targets[0].is_stage
    assert loaded.targets[0].broadcasts == {"bid1": "msg1"}
    assert "cd21514d0531fdffb22204e0ec5ed84a.svg" in assets

    sprite = loaded.targets[1]
    assert sprite.name == "Sprite1"
    assert sprite.blocks["gf"].opcode == "event_whenflagclicked"
    assert sprite.blocks["gf"].next == "set1"

    rep = sprite.blocks["rep1"]
    sub = rep.inputs["SUBSTACK"]
    assert sub.kind == 2 and sub.block_id == "ch1"

    times_input = rep.inputs["TIMES"]
    assert times_input.primitive[0] == 4 and times_input.primitive[1] == "3"

    stage = loaded.targets[0]
    assert stage.variables["v_score"] == ["score", 0]


def test_compressed_block_form():
    import json

    from scratch_py.parser.deserialize import parse_project

    raw = {
        "targets": [
            {
                "isStage": True,
                "name": "Stage",
                "blocks": {
                    "c1": ["operator_length", {"STRING": [1, [10, "hello"]]}, {}],
                },
                "costumes": [],
            }
        ],
        "monitors": [],
        "extensions": [],
        "meta": {},
    }
    project = parse_project(json.dumps(raw))
    block = project.targets[0].blocks["c1"]
    assert block.opcode == "operator_length"
    assert block.inputs["STRING"].primitive[1] == "hello"
    assert block.shadow is False


def test_dump_scripts(tmp_path):
    loaded, _ = _build(tmp_path)
    text = ScriptDumper().dump_project(loaded)
    assert "event_whenflagclicked" in text
    assert "control_repeat" in text
    assert "msg1" in text


def test_bad_file_raises(tmp_path):
    bad = tmp_path / "bad.sb3"
    bad.write_bytes(b"not a zip")
    try:
        load_sb3(str(bad))
        raised = False
    except SB3Error:
        raised = True
    assert raised

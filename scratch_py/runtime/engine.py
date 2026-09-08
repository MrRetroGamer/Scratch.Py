"""Runtime engine: cooperative thread scheduler replicating scratch-vm semantics."""

from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import datetime

from ..blocks import get_handler, register_all
from ..parser.model import MonitorData, ProjectData
from ..util import jscompat as cast
from .state import STAGE_HEIGHT, STAGE_WIDTH, TargetState
from .thread import DONE, RUNNING, StopAll, StopScript, Thread


class Runtime:
    CLONE_LIMIT = 300
    WARP_TIME_BUDGET = 0.015

    def __init__(self, project: ProjectData, assets: dict[str, bytes] | None = None):
        register_all()
        sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))
        self.project = project
        self.assets = assets or {}
        self.broadcasts: dict[str, str] = {}
        for t in project.targets:
            for bid, name in t.broadcasts.items():
                self.broadcasts[bid] = name
        self.stage = TargetState(project.targets[0], self)
        sprite_states = [TargetState(td, self) for td in project.targets[1:]]
        self.targets = [self.stage] + sprite_states
        self.draw_order = [
            s for s in sorted(sprite_states, key=lambda s: s.data.layer_order) if not s.is_stage
        ]
        self.threads: list[Thread] = []
        self.renderer = None
        self.audio = None
        self.turbo = False
        self.keys_held: set[str] = set()
        self.mouse_down = False
        self.timer_start = 0.0
        self._clock_offset = 0.0
        self.answer = ""
        self.questions: list[tuple[str, dict]] = []
        self.answer_pending = False
        self.tempo = 60
        self.instrument = 1
        self.username = ""
        self.loudness = -1
        self.current_thread: Thread | None = None
        self._events: list[tuple] = []
        self._gt_fired: dict = {}
        self._warned_opcodes: set[str] = set()
        self._compiled: dict = {}
        self._warp_deadline = 0.0
        self._proc_cache: dict[int, dict[str, str]] = {}
        self._pen_prev: dict[int, tuple[float, float]] = {}
        self.monitors = project.monitors

    # ------------------------------------------------------------- lifecycle

    def green_flag(self):
        self.stop_all_threads()
        self.targets = [t for t in self.targets if not t.is_clone]
        alive = set(id(t) for t in self.targets)
        self.draw_order = [t for t in self.draw_order if id(t) in alive]
        if self.audio:
            self.audio.stop_all()
        if self.renderer:
            self.renderer.pen_clear()
        self._pen_prev.clear()
        self._gt_fired.clear()
        for t in self.targets:
            t.say_text = None
            t.say_style = None
        for tgt in self.targets:
            for bid, block in tgt.data.blocks.items():
                if block.top_level and block.opcode == "event_whenflagclicked":
                    self.start_thread(tgt, bid)

    def stop_all_threads(self):
        self.threads = []
        self.current_thread = None

    def start_thread(self, tgt: TargetState, top_block_id: str) -> Thread | None:
        for th in self.threads:
            if th.target is tgt and th.top_block_id == top_block_id:
                th.gen = self._script_gen(tgt, top_block_id)
                th.warp = False
                th.arg_stack = []
                th.status = RUNNING
                return th
        th = Thread(self, tgt, top_block_id, self._script_gen(tgt, top_block_id))
        self.threads.append(th)
        return th

    # ------------------------------------------------------------------ tick

    def tick(self):
        self._now = self.now()
        self._warp_deadline = self._now + self.WARP_TIME_BUDGET
        self._process_events()
        self._poll_greater_than()
        threads = list(self.threads)
        stop_all = False
        for th in threads:
            if th.status != RUNNING:
                continue
            self.current_thread = th
            try:
                next(th.gen)
            except StopIteration:
                th.status = DONE
            except StopScript:
                th.status = DONE
            except StopAll:
                th.status = DONE
                stop_all = True
                break
            except RecursionError:
                th.status = DONE
                self._report_thread_error(th)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                th.status = DONE
                self._report_thread_error(th)
        self.current_thread = None
        if stop_all:
            self.stop_all_threads()
        else:
            self.threads = [t for t in self.threads if t.status == RUNNING]
        self._pen_flush()

    def _report_thread_error(self, thread: Thread):
        top = thread.target.data.blocks.get(thread.top_block_id)
        opcode = top.opcode if top is not None else thread.top_block_id
        print(f"[scratch.py] error in script '{opcode}' on target "
              f"'{thread.target.name}'; stopping that script:")
        traceback.print_exc()

    def warp_deadline_exceeded(self) -> bool:
        return self.now() > self._warp_deadline

    def pen_move(self, tgt, old_x: float, old_y: float):
        """Draw a pen segment for a movement that just happened, so warp loops
        produce continuous artwork instead of one segment per tick."""
        pen = tgt.pen
        if not pen["down"] or self.renderer is None:
            return
        cur = (tgt.x, tgt.y)
        if cur == (old_x, old_y):
            return
        self._pen_prev[id(tgt)] = cur
        self.renderer.pen_line(
            old_x, old_y, cur[0], cur[1],
            pen["rgb"], pen["size"], pen["transparency"],
        )

    def _pen_flush(self):
        if self.renderer is None:
            return
        alive = set(id(t) for t in self.targets)
        for key in [k for k in self._pen_prev if k not in alive]:
            del self._pen_prev[key]
        for tgt in self.targets:
            pen = tgt.pen
            key = id(tgt)
            if not pen["down"]:
                self._pen_prev.pop(key, None)
                continue
            cur = (tgt.x, tgt.y)
            prev = self._pen_prev.get(key)
            self._pen_prev[key] = cur
            if prev is not None and prev != cur:
                self.renderer.pen_line(
                    prev[0], prev[1], cur[0], cur[1],
                    pen["rgb"], pen["size"], pen["transparency"],
                )

    # ---------------------------------------------------------------- events

    def post_event(self, kind: str, data=None):
        self._events.append((kind, data))

    def _process_events(self):
        events = self._events
        self._events = []
        for kind, data in events:
            if kind == "keydown":
                if data not in self.keys_held:
                    self.keys_held.add(data)
                    self._fire_key_hats(data)
            elif kind == "keyup":
                self.keys_held.discard(data)
            elif kind == "mousedown":
                self.mouse_down = True
            elif kind == "mouseup":
                self.mouse_down = False
            elif kind == "click":
                self._handle_click(*data)

    def _fire_key_hats(self, key_name: str):
        for tgt in self.targets:
            for bid, block in tgt.data.blocks.items():
                if not block.top_level or block.opcode != "event_whenkeypressed":
                    continue
                wanted = block.fields.get("KEY_OPTION", [""])[0]
                if wanted.lower() in ("any", key_name.lower()):
                    self.start_thread(tgt, bid)

    def _handle_click(self, x: float, y: float):
        if self.renderer is not None:
            for tgt in reversed(self.draw_order):
                if not tgt.visible or tgt.is_stage:
                    continue
                if self.renderer.hit_test(tgt, x, y):
                    self._fire_click_hats(tgt, "event_whenthisspriteclicked")
                    return
        self._fire_click_hats(self.stage, "event_whenstageclicked")

    def _fire_click_hats(self, tgt, opcode: str):
        for bid, block in tgt.data.blocks.items():
            if block.top_level and block.opcode == opcode:
                self.start_thread(tgt, bid)

    def _poll_greater_than(self):
        for tgt in self.targets:
            for bid, block in tgt.data.blocks.items():
                if not block.top_level or block.opcode != "event_whengreaterthan":
                    continue
                menu = block.fields.get("WHENGREATERTHANMENU", [""])[0]
                threshold = cast.to_number(self.eval_input_or_field(tgt, block, "THRESHOLD"))
                if menu.upper() == "TIMER":
                    cond = self.timer_value() > threshold
                elif menu.upper() == "LOUDNESS":
                    cond = self.loudness > threshold
                else:
                    cond = False
                key = (id(tgt), bid)
                was = self._gt_fired.get(key, False)
                if cond and not was:
                    self._gt_fired[key] = True
                    self.start_thread(tgt, bid)
                elif not cond:
                    self._gt_fired[key] = False

    def eval_input_or_field(self, tgt, block, name):
        inp = block.inputs.get(name)
        if inp is not None:
            return self.eval_input(tgt, inp)
        entry = block.fields.get(name)
        return entry[0] if entry else ""

    # ------------------------------------------------------------- broadcasts

    def restart_broadcast_threads(self, name: str) -> list[Thread]:
        started = []
        for tgt in self.targets:
            for bid, block in tgt.data.blocks.items():
                if not block.top_level or block.opcode != "event_whenbroadcastreceived":
                    continue
                if block.fields.get("BROADCAST_OPTION", [""])[0] == name:
                    th = self.start_thread(tgt, bid)
                    if th:
                        started.append(th)
        return started

    def broadcast_wait_finished(self, name: str) -> bool:
        hat_ids = {
            (id(tgt), bid)
            for tgt in self.targets
            for bid, block in tgt.data.blocks.items()
            if block.top_level
            and block.opcode == "event_whenbroadcastreceived"
            and block.fields.get("BROADCAST_OPTION", [""])[0] == name
        }
        for th in self.threads:
            if th.status == RUNNING and (id(th.target), th.top_block_id) in hat_ids:
                return False
        return True

    def fire_backdrop_switch(self, backdrop_name: str):
        for tgt in self.targets:
            for bid, block in tgt.data.blocks.items():
                if not block.top_level or block.opcode != "event_whenbackdropswitchesto":
                    continue
                if block.fields.get("BACKDROP", [""])[0] == backdrop_name:
                    self.start_thread(tgt, bid)

    # ------------------------------------------------------------------ clones

    def create_clone(self, source: TargetState):
        clone_count = sum(1 for t in self.targets if t.is_clone)
        if clone_count >= self.CLONE_LIMIT:
            return
        clone = TargetState(source.data, self)
        clone.name = source.name
        clone.clone_state_from(source)
        self.targets.append(clone)
        self.draw_order.append(clone)
        for bid, block in clone.data.blocks.items():
            if block.top_level and block.opcode == "control_start_as_clone":
                self.start_thread(clone, bid)

    def delete_clone(self, clone: TargetState):
        if not clone.is_stage:
            self.threads = [t for t in self.threads if t.target is not clone]
            self.targets = [t for t in self.targets if t is not clone]
            self.draw_order = [t for t in self.draw_order if t is not clone]
            self._pen_prev.pop(id(clone), None)

    # ------------------------------------------------------------ script exec

    def _compiled_chain(self, tgt: TargetState, first_id: str | None):
        key = (id(tgt.data), first_id)
        chain = self._compiled.get(key)
        if chain is None:
            parts = []
            bid = first_id
            blocks = tgt.data.blocks
            while bid:
                block = blocks.get(bid)
                if block is None:
                    break
                parts.append((get_handler(block.opcode), block))
                bid = block.next
            chain = tuple(parts)
            self._compiled[key] = chain
        return chain

    def _script_gen(self, tgt: TargetState, first_id: str | None):
        for handler, block in self._compiled_chain(tgt, first_id):
            if handler is None:
                if not block.shadow:
                    self._warn_opcode(block.opcode)
            elif handler.kind == "command":
                if handler.is_gen:
                    yield from handler.fn(self, tgt, block)
                else:
                    handler.fn(self, tgt, block)
            else:
                self.eval_block(tgt, block)

    run_substack = _script_gen

    def eval_block(self, tgt: TargetState, block):
        handler = get_handler(block.opcode)
        if handler is None:
            if not block.shadow:
                self._warn_opcode(block.opcode)
            if block.fields:
                return next(iter(block.fields.values()))[0]
            return ""
        if handler.kind in ("reporter", "boolean"):
            return handler.fn(self, tgt, block)
        return ""

    def eval_input(self, tgt: TargetState, inp):
        if inp.block_id is not None:
            block = tgt.data.blocks.get(inp.block_id)
            if block is not None:
                return self.eval_block(tgt, block)
        primitive = inp.primitive
        if primitive is None:
            if inp.shadow_block_id is not None:
                block = tgt.data.blocks.get(inp.shadow_block_id)
                if block is not None:
                    return self.eval_block(tgt, block)
            return ""
        tag = primitive[0]
        if tag == 11:
            return primitive[1]
        if tag == 12:
            name = primitive[1] if len(primitive) > 1 else ""
            vid = primitive[2] if len(primitive) > 2 else ""
            container = self.var_container(tgt, vid, name)
            return container[1]
        if tag == 13:
            name = primitive[1] if len(primitive) > 1 else ""
            lid = primitive[2] if len(primitive) > 2 else ""
            container = self.list_container(tgt, lid, name)
            return container[1]
        return primitive[1]

    # ------------------------------------------------------------- variables

    def var_container(self, tgt: TargetState, vid: str, name: str):
        scope = tgt.variables
        if vid and vid in scope:
            return scope[vid]
        if name:
            for entry in scope.values():
                if entry[0] == name:
                    return entry
        gscope = self.stage.variables
        if vid and vid in gscope:
            return gscope[vid]
        if name:
            for entry in gscope.values():
                if entry[0] == name:
                    return entry
        key = vid or f"__auto_{name}"
        return gscope.setdefault(key, [name or "?", 0])

    def list_container(self, tgt: TargetState, lid: str, name: str):
        scope = tgt.lists
        if lid and lid in scope:
            return scope[lid]
        if name:
            for entry in scope.values():
                if entry[0] == name:
                    return entry
        gscope = self.stage.lists
        if lid and lid in gscope:
            return gscope[lid]
        if name:
            for entry in gscope.values():
                if entry[0] == name:
                    return entry
        key = lid or f"__auto_{name}"
        return gscope.setdefault(key, [name or "?", []])

    def field_var_container(self, tgt, block, fname="VARIABLE"):
        entry = block.fields.get(fname)
        if not entry:
            return ["?", 0]
        return self.var_container(tgt, entry[1] if len(entry) > 1 else "", entry[0])

    def field_list_container(self, tgt, block, fname="LIST"):
        entry = block.fields.get(fname)
        if not entry:
            return ["?", []]
        return self.list_container(tgt, entry[1] if len(entry) > 1 else "", entry[0])

    # ------------------------------------------------------------ procedures

    def find_procdef(self, tgt: TargetState, proccode: str):
        cache = self._proc_cache.setdefault(id(tgt.data), {})
        if proccode in cache:
            return tgt.data.blocks.get(cache[proccode])
        for block in tgt.data.blocks.values():
            if block.opcode == "procedures_prototype" and block.mutation:
                if block.mutation.get("proccode") == proccode:
                    cache[proccode] = block.parent or ""
                    return tgt.data.blocks.get(block.parent)
        cache[proccode] = ""
        return None

    # ------------------------------------------------------------- ask/answer

    def ask(self, text: str) -> dict:
        token = {"done": False}
        self.questions.append((text, token))
        self.answer_pending = True
        return token

    def submit_answer(self, text: str):
        self.answer = text
        if self.questions:
            _, token = self.questions.pop(0)
            token["done"] = True
        self.answer_pending = bool(self.questions)

    @property
    def active_question(self) -> str | None:
        return self.questions[0][0] if self.questions else None

    # ------------------------------------------------------------------ misc

    def now(self) -> float:
        return time.perf_counter() + self._clock_offset

    def advance_time(self, seconds: float):
        """Test hook: fast-forward the VM's notion of elapsed time."""
        self._clock_offset += seconds

    def timer_value(self) -> float:
        return self.now() - self.timer_start

    def reset_timer(self):
        self.timer_start = self.now()

    def sprite_bounds(self, tgt: TargetState):
        if self.renderer is None:
            return None
        return self.renderer.sprite_bounds(tgt)

    def find_target_by_name(self, name: str) -> TargetState | None:
        for tgt in self.targets:
            if tgt.name == name:
                return tgt
        return None

    def targets_with_name(self, name: str):
        for tgt in self.targets:
            if tgt.name == name:
                yield tgt

    def monitor_value(self, monitor: MonitorData):
        opcode = monitor.opcode
        params = monitor.params
        owner = None
        if monitor.sprite_name:
            owner = self.find_target_by_name(monitor.sprite_name)
        if opcode == "data_variable":
            name = params.get("VARIABLE", "")
            tgt = owner or self.stage
            cont = self.var_container(tgt, params.get("ID", ""), name)
            return cont[1]
        if opcode == "data_listcontents":
            name = params.get("LIST", "")
            tgt = owner or self.stage
            cont = self.list_container(tgt, params.get("ID", ""), name)
            return cont[1]
        if opcode == "sensing_timer":
            return round(self.timer_value(), 4)
        if opcode == "sensing_answer":
            return self.answer
        if opcode == "sensing_loudness":
            return self.loudness
        if opcode == "sensing_mousedown":
            return self.mouse_down
        if opcode == "sensing_mousex":
            return self.renderer.mouse_x() if self.renderer else 0
        if opcode == "sensing_mousey":
            return self.renderer.mouse_y() if self.renderer else 0
        if opcode == "sensing_username":
            return self.username
        if opcode.startswith("sensing_current"):
            menu = params.get("CURRENTMENU", "").upper()
            now = datetime.now()
            table = {
                "YEAR": now.year,
                "MONTH": now.month,
                "DATE": now.day,
                "DAYOFWEEK": (now.isoweekday() % 7) + 1,
                "HOUR": now.hour,
                "MINUTE": now.minute,
                "SECOND": now.second,
            }
            return table.get(menu, 0)
        if opcode == "motion_xposition" and owner:
            return owner.x
        if opcode == "motion_yposition" and owner:
            return owner.y
        if opcode == "motion_direction" and owner:
            return owner.direction
        if opcode == "looks_size" and owner:
            return owner.size
        if opcode == "looks_costumenumbername" and owner:
            return owner.current_costume + 1
        return ""

    def set_monitor_value(self, monitor: MonitorData, value):
        """Write a value back through a monitor (slider drags). Ranges from the
        monitor definition are respected: clamped to slider_min/slider_max and
        rounded when the slider is discrete."""
        if monitor.opcode != "data_variable":
            return
        lo = monitor.slider_min
        hi = monitor.slider_max
        if hi < lo:
            lo, hi = hi, lo
        try:
            raw = value
            if not cast.is_numeric(raw):
                value = float(lo)
            else:
                value = cast.to_number(raw)
        except (TypeError, ValueError):
            value = float(lo)
        value = max(lo, min(hi, value))
        if monitor.is_discrete:
            value = int(cast.js_round(value))
        name = monitor.params.get("VARIABLE", "")
        owner = self.stage
        if monitor.sprite_name:
            owner = self.find_target_by_name(monitor.sprite_name) or self.stage
        container = self.var_container(owner, monitor.params.get("ID", ""), name)
        container[1] = value

    def _warn_opcode(self, opcode: str):
        self._warn_once(f"op:{opcode}", f"unsupported block opcode: {opcode}")

    def _warn_once(self, key: str, message: str):
        if key in self._warned_opcodes:
            return
        self._warned_opcodes.add(key)
        print(f"[scratch.py] {message}")


def proc_arg_names(defn_block) -> list[str]:
    proto_mutation = defn_block.mutation or {}
    try:
        return list(json.loads(proto_mutation.get("argumentnames", "[]")))
    except (ValueError, TypeError):
        return []


def warp_of(defn_block) -> bool:
    return bool(defn_block.mutation and defn_block.mutation.get("warp"))


STAGE_W = STAGE_WIDTH
STAGE_H = STAGE_HEIGHT

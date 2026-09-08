"""pygame-ce stage renderer replicating scratch-render's transform pipeline."""

from __future__ import annotations

import math

import numpy
import pygame

from ..parser.model import Costume
from ..util import jscompat as cast
from .costumes import CostumeCache, LoadedCostume

STAGE_W = 480
STAGE_H = 360

KEY_MAP = {
    pygame.K_SPACE: "space",
    pygame.K_LEFT: "left arrow",
    pygame.K_RIGHT: "right arrow",
    pygame.K_UP: "up arrow",
    pygame.K_DOWN: "down arrow",
    pygame.K_RETURN: "return",
    pygame.K_KP_ENTER: "return",
    pygame.K_a: "a", pygame.K_b: "b", pygame.K_c: "c", pygame.K_d: "d",
    pygame.K_e: "e", pygame.K_f: "f", pygame.K_g: "g", pygame.K_h: "h",
    pygame.K_i: "i", pygame.K_j: "j", pygame.K_k: "k", pygame.K_l: "l",
    pygame.K_m: "m", pygame.K_n: "n", pygame.K_o: "o", pygame.K_p: "p",
    pygame.K_q: "q", pygame.K_r: "r", pygame.K_s: "s", pygame.K_t: "t",
    pygame.K_u: "u", pygame.K_v: "v", pygame.K_w: "w", pygame.K_x: "x",
    pygame.K_y: "y", pygame.K_z: "z",
    pygame.K_0: "0", pygame.K_1: "1", pygame.K_2: "2", pygame.K_3: "3",
    pygame.K_4: "4", pygame.K_5: "5", pygame.K_6: "6", pygame.K_7: "7",
    pygame.K_8: "8", pygame.K_9: "9",
    pygame.K_COMMA: ",", pygame.K_PERIOD: ".", pygame.K_MINUS: "-",
    pygame.K_EQUALS: "=", pygame.K_SLASH: "/", pygame.K_SEMICOLON: ";",
}


class RenderInfo:
    __slots__ = ("surface", "mask", "blit_x", "blit_y", "angle", "flipped",
                 "wr", "hr", "ox", "oy", "ws", "hs", "x", "y", "rs",
                 "fp_size", "fp_direction", "fp_md5")

    def __init__(self):
        self.surface = None
        self.mask = None
        self.blit_x = 0.0
        self.blit_y = 0.0
        self.angle = 0.0
        self.flipped = False
        self.wr = self.hr = self.ox = self.oy = self.ws = self.hs = 0.0
        self.x = 0.0
        self.y = 0.0
        self.rs = 1.0
        self.fp_size = None
        self.fp_direction = None
        self.fp_md5 = None


class Renderer:
    BAR_H = 40

    def __init__(self, rt, assets: dict[str, bytes], scale: int = 2):
        self.rt = rt
        rt.renderer = self
        self.assets = assets
        self.scale = max(1, scale)
        pygame.init()
        self.window = pygame.display.set_mode(
            (STAGE_W * self.scale, STAGE_H * self.scale + self.BAR_H),
            pygame.RESIZABLE,
        )
        try:
            window = pygame.display.get_window()
            if window is not None:
                window.maximize()
        except (AttributeError, pygame.error):
            pass
        pygame.display.set_caption("scratch.py")
        self._rs = 1.0
        self.stage = pygame.Surface((STAGE_W, STAGE_H), pygame.SRCALPHA)
        self.pen_layer = pygame.Surface((STAGE_W, STAGE_H), pygame.SRCALPHA)
        self.costumes = CostumeCache(assets)
        self.font = pygame.font.Font(None, 16)
        self.small_font = pygame.font.Font(None, 13)
        self.clock = pygame.time.Clock()
        self.running = False
        self.info_cache: dict[int, RenderInfo] = {}
        self._typed = ""
        self._font_cache: dict = {}
        self._appearance_cache: dict[tuple, tuple] = {}
        self._slider_rects: dict[int, tuple] = {}
        self._drag_slider: tuple | None = None

    # ------------------------------------------------------------- main loop

    def run(self):
        self.running = True
        while self.running:
            for event in pygame.event.get():
                self._handle_event(event)
            if not self.running:
                break
            self.rt.tick()
            self.draw_frame()
            if not self.rt.turbo:
                self.clock.tick(30)
        pygame.quit()

    def stop(self):
        self.running = False

    def _flag_button_rect(self) -> pygame.Rect:
        return pygame.Rect(10, (self.BAR_H - 28) // 2, 30, 28)

    def _stop_button_rect(self) -> pygame.Rect:
        return pygame.Rect(50, (self.BAR_H - 26) // 2, 26, 26)

    def _stage_rect(self) -> pygame.Rect:
        win_w, win_h = self.window.get_size()
        avail_h = max(STAGE_H, win_h - self.BAR_H)
        scale = min(win_w / STAGE_W, avail_h / STAGE_H)
        w = int(STAGE_W * scale)
        h = int(STAGE_H * scale)
        x = (win_w - w) // 2
        y = self.BAR_H + (avail_h - h) // 2
        return pygame.Rect(x, y, w, h)

    def _handle_event(self, event):
        rt = self.rt
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.WINDOWRESIZED:
            pass
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._flag_button_rect().collidepoint(event.pos):
                rt.green_flag()
                return
            if self._stop_button_rect().collidepoint(event.pos):
                rt.stop_all_threads()
                return
            slider = self._slider_at(event.pos)
            if slider is not None:
                monitor, track, lo, hi = slider
                self._drag_slider = (monitor, track, lo, hi)
                self._update_slider_from_mouse(monitor, track, lo, hi, event.pos[0])
                return
            x, y = self._to_stage(event.pos)
            rt.post_event("mousedown")
            rt.post_event("click", (x, y))
        elif event.type == pygame.MOUSEMOTION:
            if self._drag_slider is not None:
                monitor, track, lo, hi = self._drag_slider
                self._update_slider_from_mouse(monitor, track, lo, hi, event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._drag_slider = None
            rt.post_event("mouseup")
        elif event.type == pygame.KEYDOWN:
            name = KEY_MAP.get(event.key)
            typing = rt.active_question is not None
            if not typing and event.key == pygame.K_t:
                rt.turbo = not rt.turbo
                print(f"[scratch.py] turbo {'on' if rt.turbo else 'off'}")
                return
            if not typing and event.key == pygame.K_f:
                pygame.display.toggle_fullscreen()
                return
            if typing:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    rt.submit_answer(self._typed)
                    self._typed = ""
                elif event.key == pygame.K_BACKSPACE:
                    self._typed = self._typed[:-1]
                elif event.key == pygame.K_ESCAPE:
                    rt.submit_answer(self._typed)
                    self._typed = ""
                elif event.unicode and event.unicode.isprintable():
                    self._typed += event.unicode
                return
            if name:
                rt.post_event("keydown", name)
        elif event.type == pygame.KEYUP:
            name = KEY_MAP.get(event.key)
            if name and rt.active_question is None:
                rt.post_event("keyup", name)

    def _slider_at(self, pos):
        for entry in self._slider_rects.values():
            monitor, track, lo, hi, hit = entry
            if hit.collidepoint(pos):
                return monitor, track, lo, hi
        return None

    def _update_slider_from_mouse(self, monitor, track: pygame.Rect, lo: float, hi: float,
                                  mouse_x: int):
        t = (mouse_x - track.x) / max(1, track.w)
        t = max(0.0, min(1.0, t))
        value = lo + t * (hi - lo)
        self.rt.set_monitor_value(monitor, value)

    def _to_stage(self, window_pos):
        rect = self._stage_rect()
        scale_x = STAGE_W / rect.w
        scale_y = STAGE_H / rect.h
        gx = (window_pos[0] - rect.x) * scale_x
        gy = (rect.y + rect.h - window_pos[1]) * scale_y
        return (gx - STAGE_W / 2, gy - STAGE_H / 2)

    # -------------------------------------------------------------- drawing

    def draw_frame(self):
        rt = self.rt
        rect = self._stage_rect()
        self._resolve_render_scale(rect)
        self.stage.fill((255, 255, 255, 255))
        self._draw_backdrop()
        self.stage.blit(self.pen_layer, (0, 0))
        if len(self._appearance_cache) > 256:
            self._appearance_cache.clear()
        for tgt in rt.draw_order:
            if tgt.visible:
                self._draw_sprite(tgt)

        self.window.fill((32, 32, 40))
        if self.stage.get_size() == rect.size:
            self.window.blit(self.stage, rect.topleft)
        else:
            frame = pygame.transform.smoothscale(self.stage, rect.size)
            self.window.blit(frame, rect.topleft)
        self._draw_controls()
        self._draw_overlays(rect)
        pygame.display.flip()

    MAX_RS = 4.0

    def _resolve_render_scale(self, rect: pygame.Rect):
        raw = rect.w / STAGE_W
        bucket = max(1.0, min(self.MAX_RS, round(raw * 4) / 4))
        if bucket != self._rs:
            self._rebuild_surfaces(bucket)

    def _rebuild_surfaces(self, rs: float):
        self._rs = rs
        size = (round(STAGE_W * rs), round(STAGE_H * rs))
        self.stage = pygame.Surface(size, pygame.SRCALPHA)
        old_pen = self.pen_layer
        self.pen_layer = pygame.Surface(size, pygame.SRCALPHA)
        if old_pen.get_size() != size:
            try:
                scaled = pygame.transform.smoothscale(old_pen, size)
                self.pen_layer.blit(scaled, (0, 0))
            except (pygame.error, ValueError):
                pass
        self._appearance_cache.clear()
        self.info_cache.clear()

    def stage_to_window(self, rect: pygame.Rect, x: float, y: float):
        wx = rect.x + (x + STAGE_W / 2) * (rect.w / STAGE_W)
        wy = rect.y + (STAGE_H / 2 - y) * (rect.h / STAGE_H)
        return wx, wy

    def ui_font(self, size_px: int, bold: bool = False) -> pygame.font.Font:
        size_px = max(8, int(size_px))
        key = (size_px, bold)
        font = self._font_cache.get(key)
        if font is None:
            font = pygame.font.SysFont("segoeui,arial,helvetica,dejavusans", size_px, bold=bold)
            self._font_cache[key] = font
        return font

    def _draw_overlays(self, rect: pygame.Rect):
        factor = rect.w / STAGE_W
        self._draw_bubbles_overlay(rect, factor)
        self._draw_monitors_overlay(rect, factor)
        self._draw_ask_overlay(rect, factor)

    def _draw_controls(self):
        win_w = self.window.get_width()
        pygame.draw.rect(self.window, (252, 252, 252), (0, 0, win_w, self.BAR_H))
        pygame.draw.line(self.window, (219, 223, 232),
                         (0, self.BAR_H - 1), (win_w, self.BAR_H - 1))

        flag_rect = self._flag_button_rect()
        pole_x = flag_rect.x + 7
        pole_top = flag_rect.y + 2
        pole_bottom = flag_rect.bottom - 2
        pygame.draw.line(self.window, (150, 155, 168),
                         (pole_x, pole_top), (pole_x, pole_bottom), 3)
        tip_y = pole_top + 4
        points = [
            (pole_x + 1, tip_y),
            (pole_x + 19, tip_y + 5),
            (pole_x + 1, tip_y + 10),
        ]
        pygame.draw.polygon(self.window, (76, 191, 86), points)

        stop_rect = self._stop_button_rect()
        cx, cy = stop_rect.center
        r = stop_rect.width // 2
        octagon = []
        for i in range(8):
            angle = math.pi / 8 + i * math.pi / 4
            octagon.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        pygame.draw.polygon(self.window, (236, 89, 89), octagon)

    def _draw_backdrop(self):
        costume = self.rt.stage.costume()
        if costume is None:
            return
        loaded = self.costumes.get(costume, self._rs)
        if loaded is None:
            return
        target = self.stage.get_size()
        if loaded.surface.get_size() == target:
            self.stage.blit(loaded.surface, (0, 0))
        else:
            stretched = pygame.transform.smoothscale(loaded.surface, target)
            self.stage.blit(stretched, (0, 0))

    def _rendered_appearance(self, tgt):
        costume = tgt.costume()
        loaded = self.costumes.get(costume, self._rs) if costume else None
        if loaded is None:
            return None
        size_pct = round(tgt.size * 10) / 10.0
        direction_key = round(tgt.direction)
        effects_key = (
            round(tgt.effects["ghost"]),
            round(tgt.effects["brightness"]),
            round(tgt.effects["saturation"]),
            round(tgt.effects["color"]),
            round(tgt.effects["mosaic"]),
            round(tgt.effects["fisheye"]),
            round(tgt.effects["whirl"]),
            round(tgt.effects["pixelate"]),
        )
        key = (costume.md5ext, size_pct, direction_key, effects_key, id(tgt.data), self._rs)
        cached = self._appearance_cache.get(key)
        if cached is not None:
            return cached
        rendered = self._build_appearance(tgt, loaded, costume, size_pct, direction_key)
        self._appearance_cache[key] = rendered
        return rendered

    def _build_appearance(self, tgt, loaded: LoadedCostume, costume: Costume,
                          size_pct: float, direction_key: float):
        px_per_unit = (size_pct / 100.0) * self._rs
        resize_factor = px_per_unit / loaded.px_per_unit
        base = loaded.surface
        w = max(1, int(round(base.get_width() * resize_factor)))
        h = max(1, int(round(base.get_height() * resize_factor)))
        if (w, h) == base.get_size():
            surf = base.copy()
        else:
            surf = pygame.transform.smoothscale(base, (w, h))

        eff = tgt.effects
        if eff["color"]:
            surf = self._hue_shift(surf, eff["color"])
        if eff["saturation"]:
            surf = self._adjust_saturation(surf, eff["saturation"])
        if eff["brightness"]:
            surf = self._adjust_brightness(surf, eff["brightness"])
        if eff["pixelate"]:
            surf = self._pixelate(surf, eff["pixelate"])
        if eff["whirl"]:
            surf = self._whirl(surf, eff["whirl"])
        if eff["fisheye"]:
            surf = self._fisheye(surf, eff["fisheye"])
        if eff["mosaic"]:
            surf = self._mosaic(surf, eff["mosaic"])

        style = tgt.rotation_style
        flipped = False
        if style == "all around":
            angle = 90.0 - direction_key
        elif style == "left-right":
            flipped = direction_key < 0
            angle = 90.0 - abs(direction_key)
        else:
            angle = 0.0
        if abs(angle % 360) > 0.01:
            surf = pygame.transform.rotate(surf, angle)

        ghost = eff["ghost"]
        if ghost > 0:
            surf = surf.copy()
            surf.set_alpha(int(max(0.0, min(1.0, (100.0 - ghost) / 100.0)) * 255))
        return surf, angle, flipped, px_per_unit, costume

    @staticmethod
    def _adjust_brightness(surface, brightness: float):
        amount = max(-100.0, min(100.0, float(brightness))) / 100.0
        result = surface.copy()
        if amount > 0:
            result.fill((int(255 * amount), int(255 * amount), int(255 * amount)),
                        special_flags=pygame.BLEND_RGB_ADD)
        elif amount < 0:
            v = int(255 * (1 + amount))
            result.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
        return result

    @staticmethod
    def _adjust_saturation(surface, saturation: float):
        arr = pygame.surfarray.array3d(surface).astype(numpy.float32)
        alpha = pygame.surfarray.pixels_alpha(surface).copy()
        gray = arr @ numpy.array([0.299, 0.587, 0.114], dtype=numpy.float32)
        s = max(-100.0, min(100.0, float(saturation))) / 100.0
        if s >= 0:
            factor = 1.0 + s
            out = gray[:, :, None] + (arr - gray[:, :, None]) * factor
        else:
            out = gray[:, :, None] + (arr - gray[:, :, None]) * (1.0 + s)
        out = numpy.clip(out, 0, 255).astype(numpy.uint8)
        new = pygame.surfarray.make_surface(out).convert_alpha()
        new_array = pygame.surfarray.pixels_alpha(new)
        new_array[:] = alpha
        del new_array
        return new

    @staticmethod
    def _hue_shift(surface, color_value: float):

        arr = pygame.surfarray.array3d(surface).astype(numpy.float32) / 255.0
        alpha = pygame.surfarray.pixels_alpha(surface).copy()
        shift = (float(color_value) / 200.0) % 1.0
        flat = arr.reshape(-1, 3)
        mx = flat.max(axis=1)
        mn = flat.min(axis=1)
        diff = mx - mn + 1e-9
        hue = numpy.zeros(len(flat), dtype=numpy.float32)
        r, g, b = flat[:, 0], flat[:, 1], flat[:, 2]
        m_r = mx == r
        m_g = (mx == g) & ~m_r
        m_b = ~(m_r | m_g)
        hue[m_r] = ((g - b) / diff)[m_r] % 6
        hue[m_g] = (((b - r) / diff) + 2)[m_g]
        hue[m_b] = (((r - g) / diff) + 4)[m_b]
        sat = numpy.where(mx > 1e-6, diff / (mx + 1e-9), 0)
        val = mx
        hue = (hue + shift * 6.0) % 6.0
        c = val * sat
        x = c * (1 - numpy.abs(hue % 2 - 1))
        m = val - c
        zero = numpy.zeros_like(c)
        conditions = [
            (hue < 1), (hue < 2), (hue < 3), (hue < 4), (hue < 5), (hue >= 5),
        ]
        choices = [
            (c, x, zero), (x, c, zero), (zero, c, x),
            (zero, x, c), (x, zero, c), (c, zero, x),
        ]
        rgb_out = numpy.zeros_like(flat)
        for cond, choice in zip(conditions, choices, strict=True):
            mask = cond
            for channel in range(3):
                rgb_out[mask, channel] = choice[channel][mask]
        rgb_out += m[:, None]
        rgb_out = numpy.clip(rgb_out * 255, 0, 255).astype(numpy.uint8)
        out_img = rgb_out.reshape(arr.shape[0], arr.shape[1], 3)
        new = pygame.surfarray.make_surface(out_img).convert_alpha()
        na = pygame.surfarray.pixels_alpha(new)
        na[:] = alpha
        del na
        return new

    @staticmethod
    def _remap_surface(surface, src_x, src_y):
        """Sample `surface` at arrays of source coordinates (both shape (h, w),
        y-major) and rebuild a per-pixel-alpha surface from the lookup."""
        w, h = surface.get_size()
        x = numpy.clip(numpy.round(src_x), 0, w - 1).astype(numpy.int32)
        y = numpy.clip(numpy.round(src_y), 0, h - 1).astype(numpy.int32)
        arr = pygame.surfarray.array3d(surface)
        alpha = pygame.surfarray.pixels_alpha(surface).copy()
        out = arr[y, x].transpose(1, 0, 2)
        new = pygame.surfarray.make_surface(out).convert_alpha()
        na = pygame.surfarray.pixels_alpha(new)
        na[:] = alpha[y, x].transpose(1, 0)
        del na
        return new

    @staticmethod
    def _pixelate(surface, pixelate: float):
        if pixelate <= 0:
            return surface
        w, h = surface.get_size()
        if w < 3 or h < 3:
            return surface
        block = max(2, min(int(round(pixelate * 0.12)), min(w, h)))
        small = pygame.transform.smoothscale(surface, (max(1, w // block), max(1, h // block)))
        return pygame.transform.smoothscale(small, (w, h))

    @staticmethod
    def _whirl(surface, whirl: float):
        value = float(whirl)
        if abs(value) < 0.5:
            return surface
        w, h = surface.get_size()
        if w < 4 or h < 4:
            return surface
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        xs = numpy.arange(w, dtype=numpy.float32) - cx
        ys = numpy.arange(h, dtype=numpy.float32) - cy
        xx, yy = numpy.meshgrid(xs, ys)
        r = numpy.sqrt(xx * xx + yy * yy)
        max_r = math.hypot(cx, cy) or 1.0
        angle = numpy.radians(value * 1.8) * (r / max_r)
        cos_a, sin_a = numpy.cos(angle), numpy.sin(angle)
        src_x = xx * cos_a - yy * sin_a + cx
        src_y = xx * sin_a + yy * cos_a + cy
        return Renderer._remap_surface(surface, src_x, src_y)

    @staticmethod
    def _fisheye(surface, fisheye: float):
        value = float(fisheye) / 100.0
        if abs(value) < 0.01:
            return surface
        w, h = surface.get_size()
        if w < 4 or h < 4:
            return surface
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        xs = numpy.arange(w, dtype=numpy.float32) - cx
        ys = numpy.arange(h, dtype=numpy.float32) - cy
        xx, yy = numpy.meshgrid(xs, ys)
        r = numpy.sqrt(xx * xx + yy * yy)
        max_r = math.hypot(cx, cy) or 1.0
        theta = numpy.arctan2(yy, xx)
        nuclear = 1.0 - 0.6 * value
        new_r = max_r * (r / max_r) ** nuclear
        src_x = cx + new_r * numpy.cos(theta)
        src_y = cy + new_r * numpy.sin(theta)
        return Renderer._remap_surface(surface, src_x, src_y)

    @staticmethod
    def _mosaic(surface, mosaic: float):
        value = float(mosaic)
        if abs(value) < 0.5:
            return surface
        w, h = surface.get_size()
        if w < 4 or h < 4:
            return surface
        n = max(1, min(16, int(round(1 + abs(value) * 0.09))))
        xs = numpy.arange(w, dtype=numpy.float32) / w * n
        ys = numpy.arange(h, dtype=numpy.float32) / h * n
        xx, yy = numpy.meshgrid(xs, ys)
        fx = xx - numpy.floor(xx)
        fy = yy - numpy.floor(yy)
        mirrored_x = (numpy.floor(xx).astype(numpy.int32) % 2) == 1
        mirrored_y = (numpy.floor(yy).astype(numpy.int32) % 2) == 1
        src_x = numpy.where(mirrored_x, 1.0 - fx, fx) * w
        src_y = numpy.where(mirrored_y, 1.0 - fy, fy) * h
        return Renderer._remap_surface(surface, src_x, src_y)

    def _draw_sprite(self, tgt):
        appearance = self._rendered_appearance(tgt)
        if appearance is None:
            self.info_cache.pop(id(tgt), None)
            return
        surf, angle, flipped, px_per_unit, costume = appearance
        rs = self._rs
        ws = surf.get_width() / rs
        hs = surf.get_height() / rs
        rcx = costume.rotation_center_x * (tgt.size / 100.0)
        rcy = costume.rotation_center_y * (tgt.size / 100.0)
        theta = math.radians(angle)
        c, s = math.cos(theta), math.sin(theta)
        px, py = rcx - ws / 2.0, rcy - hs / 2.0
        ox = px * c + py * s
        oy = -px * s + py * c
        wr, hr = ws, hs
        blit_x = (tgt.x + STAGE_W / 2) - (wr / 2.0 + ox)
        blit_y = (STAGE_H / 2 - tgt.y) - (hr / 2.0 + oy)

        draw_surf = surf
        if flipped:
            draw_surf = pygame.transform.flip(surf, True, False)

        info = self.info_cache.setdefault(id(tgt), RenderInfo())
        info.surface = draw_surf
        info.mask = None
        info.blit_x = blit_x
        info.blit_y = blit_y
        info.angle = angle
        info.flipped = flipped
        info.wr, info.hr = wr, hr
        info.ox, info.oy = ox, oy
        info.ws, info.hs = ws, hs
        info.x, info.y = tgt.x, tgt.y
        info.rs = rs
        self._stamp_info_fingerprint(info, tgt)

        ix, iy = int(round(blit_x * rs)), int(round(blit_y * rs))
        self.stage.blit(draw_surf, (ix, iy))

    # ------------------------------------------------------------- bubbles

    def _draw_bubbles_overlay(self, rect: pygame.Rect, factor: float):
        for tgt in self.rt.targets:
            if not tgt.visible or not tgt.say_text:
                continue
            self._draw_bubble_overlay(rect, factor, tgt)

    def _draw_bubble_overlay(self, rect: pygame.Rect, factor: float, tgt):
        text = str(tgt.say_text)
        if len(text) > 200:
            text = text[:200]
        font = self.ui_font(12 * factor)
        lines = self._wrap_text(text, font, int(180 * factor))
        line_surfs = [font.render(ln, True, (87, 94, 117)) for ln in lines]
        pad = int(8 * factor)
        tw = max(s.get_width() for s in line_surfs) + pad * 2
        th = sum(s.get_height() for s in line_surfs) + pad * 2 - int(4 * factor)
        bounds = self.sprite_bounds(tgt)
        if bounds is None:
            ax, ay = self.stage_to_window(rect, tgt.x, tgt.y)
        else:
            ax, ay = self.stage_to_window(rect, bounds[1], bounds[2])
        margin = int(4 * factor)
        tail_side = "right"
        bx = ax + margin
        by = ay - th - int(6 * factor)
        if bx + tw > rect.right - margin:
            left_anchor, _ = self.stage_to_window(rect, bounds[0], bounds[2]) if bounds else (ax - tw - margin, ay)
            bx = left_anchor - tw - margin
            tail_side = "left"
        bx = max(rect.left + margin, min(rect.right - tw - margin, bx))
        by = max(rect.top + margin, min(rect.bottom - th - int(20 * factor), by))
        bubble_rect = pygame.Rect(int(bx), int(by), int(tw), int(th))
        pygame.draw.rect(self.window, (255, 255, 255), bubble_rect,
                         border_radius=int(14 * factor))
        pygame.draw.rect(self.window, (87, 94, 117), bubble_rect,
                         width=max(1, int(1.5 * factor)),
                         border_radius=int(14 * factor))
        if getattr(tgt, "say_style", "say") == "think":
            dot_r = max(2, int(2.5 * factor))
            base_x = bx + int(12 * factor) if tail_side == "right" else bx + tw - int(12 * factor)
            pygame.draw.circle(self.window, (87, 94, 117),
                               (base_x, bubble_rect.bottom + dot_r * 3), dot_r, 2)
            pygame.draw.circle(self.window, (87, 94, 117),
                               (base_x + (dot_r * 4 if tail_side == "right" else -dot_r * 4),
                                bubble_rect.bottom + dot_r * 6), int(dot_r * 1.4), 2)
        else:
            tail_x = bubble_rect.x + int(16 * factor) if tail_side == "right" \
                else bubble_rect.right - int(16 * factor)
            tip_y = min(ay + int(4 * factor), rect.bottom - margin)
            p1 = (tail_x, bubble_rect.bottom - 1)
            p2 = (ax, tip_y)
            p3 = (tail_x + int(14 * factor) if tail_side == "right"
                  else tail_x - int(14 * factor), bubble_rect.bottom - 1)
            pygame.draw.polygon(self.window, (255, 255, 255), [p1, p2, p3])
            pygame.draw.lines(self.window, (87, 94, 117), False, [p1, p2, p3],
                              max(1, int(1.5 * factor)))
            pygame.draw.line(self.window, (255, 255, 255),
                             (p1[0] + (2 if tail_side == "right" else -2), bubble_rect.bottom - 1),
                             (p3[0] - (2 if tail_side == "right" else -2), bubble_rect.bottom - 1),
                             max(2, int(2 * factor)))
        ty = bubble_rect.y + pad - int(2 * factor)
        for ls in line_surfs:
            self.window.blit(ls, (bubble_rect.x + pad, ty))
            ty += ls.get_height()

    @staticmethod
    def _wrap_text(text, font, max_width):
        words = text.split(" ")
        lines = []
        current = ""
        for word in words:
            trial = word if not current else current + " " + word
            if font.size(trial)[0] <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [""]

    # ------------------------------------------------------------ monitors

    def _draw_monitors_overlay(self, rect: pygame.Rect, factor: float):
        self._slider_rects.clear()
        for monitor in self.rt.monitors:
            if not monitor.visible:
                continue
            value = self.rt.monitor_value(monitor)
            wx = rect.x + monitor.x * factor
            wy = rect.y + monitor.y * factor
            self._draw_monitor_overlay(rect, factor, wx, wy, monitor, value)

    def _draw_monitor_overlay(self, rect: pygame.Rect, factor: float,
                              x: float, y: float, monitor, value):
        opcode = monitor.opcode
        label = self._monitor_label(monitor)
        if opcode == "data_listcontents":
            self._draw_list_monitor(rect, factor, x, y, label, value)
            return
        text_color = (87, 94, 117)
        large = monitor.mode == "large"
        font = self.ui_font((15 if large else 11) * factor)
        value_text = self._format_monitor_value(value)
        if large:
            value_surf = font.render(value_text[:40], True, text_color)
            pad = int(6 * factor)
            chip_w = max(int(34 * factor), value_surf.get_width() + pad * 2)
            chip_h = int(22 * factor)
            chip = pygame.Rect(int(x), int(y), chip_w, chip_h)
            self._value_chip(chip, factor, value_surf, pad)
            return
        label_surf = font.render(label, True, text_color) if label else None
        value_surf = font.render(value_text[:30], True, text_color)
        outer, _chip = self._variable_row(x, y, factor, label_surf, value_surf)
        if monitor.mode == "slider":
            self._draw_slider_track(factor, monitor, value, outer)

    def _variable_row(self, x: float, y: float, factor: float, label_surf, value_surf):
        outer_pad = int(4 * factor)
        inner_gap = int(5 * factor)
        chip_pad = int(4 * factor)
        lw = (label_surf.get_width() + inner_gap) if label_surf else 0
        vw = max(int(30 * factor), value_surf.get_width() + chip_pad * 2)
        chip_h = int(17 * factor)
        outer_h = chip_h + outer_pad * 2
        outer = pygame.Rect(int(x), int(y), int(outer_pad + lw + vw + outer_pad), int(outer_h))
        pygame.draw.rect(self.window, (233, 237, 243), outer,
                         border_radius=int(4 * factor))
        pygame.draw.rect(self.window, (206, 212, 224), outer,
                         width=1, border_radius=int(4 * factor))
        chip = pygame.Rect(outer.right - outer_pad - vw, outer.y + outer_pad, vw, chip_h)
        self._value_chip(chip, factor, value_surf, chip_pad)
        if label_surf:
            self.window.blit(label_surf, (outer.x + outer_pad,
                                          outer.y + (outer_h - label_surf.get_height()) // 2))
        return outer, chip

    def _draw_slider_track(self, factor: float, monitor, value, outer: pygame.Rect):
        lo = float(monitor.slider_min)
        hi = float(monitor.slider_max)
        if hi < lo:
            lo, hi = hi, lo
        track_h = max(3, int(4 * factor))
        thumb_r = max(5, int(6 * factor))
        track = pygame.Rect(outer.x + int(4 * factor),
                            outer.bottom + int(7 * factor),
                            outer.w - int(8 * factor),
                            track_h)
        pygame.draw.rect(self.window, (206, 212, 224), track,
                         border_radius=track_h)
        span = hi - lo
        t = 0.0 if span <= 0 else (float(value) - lo) / span
        t = max(0.0, min(1.0, t))
        thumb_cx = int(track.x + t * track.w)
        thumb_cy = track.centery
        pygame.draw.circle(self.window, (255, 255, 255), (thumb_cx, thumb_cy), thumb_r)
        border = (76, 151, 255) if (self._drag_slider is not None
                                    and self._drag_slider[0] is monitor) else (137, 146, 163)
        pygame.draw.circle(self.window, border, (thumb_cx, thumb_cy), thumb_r,
                           width=max(2, int(1.5 * factor)))
        hit = pygame.Rect(track.x - thumb_r, track.y - thumb_r * 2,
                          track.w + thumb_r * 2, track_h + thumb_r * 4)
        self._slider_rects[id(monitor)] = (monitor, track, lo, hi, hit)

    def _value_chip(self, chip: pygame.Rect, factor: float, value_surf, pad: int):
        pygame.draw.rect(self.window, (255, 255, 255), chip,
                         border_radius=int(4 * factor))
        pygame.draw.rect(self.window, (255, 140, 26), chip,
                         width=max(1, int(1.5 * factor)),
                         border_radius=int(4 * factor))
        self.window.blit(value_surf, (chip.x + pad,
                                      chip.y + (chip.height - value_surf.get_height()) // 2))

    def _draw_list_monitor(self, rect: pygame.Rect, factor: float,
                           x: float, y: float, label: str, value):
        items = value if isinstance(value, list) else []
        shown = items[:9]
        text_color = (87, 94, 117)
        font = self.ui_font(11 * factor)
        row_h = int(16 * factor)
        header_h = int(20 * factor)
        width = int(130 * factor)
        height = header_h + len(shown) * row_h + int(18 * factor)
        card = pygame.Rect(int(x), int(y), width, height)
        pygame.draw.rect(self.window, (255, 255, 255), card,
                         border_radius=int(6 * factor))
        pygame.draw.rect(self.window, (204, 204, 204), card,
                         width=max(1, int(1.2 * factor)),
                         border_radius=int(6 * factor))
        header_rect = pygame.Rect(card.x, card.y, card.w, header_h)
        pygame.draw.rect(self.window, (233, 237, 243), header_rect,
                         border_radius=int(6 * factor))
        header_cap = pygame.Rect(card.x, card.bottom - int(8 * factor),
                                 card.w, int(8 * factor))
        pygame.draw.rect(self.window, (255, 255, 255), header_cap)
        title_font = self.ui_font(11 * factor, bold=True)
        title = title_font.render((label or "list")[:16], True, text_color)
        self.window.blit(title, (card.x + int(8 * factor),
                                 card.y + (header_h - title.get_height()) // 2))
        yy = card.y + header_h
        for i, item in enumerate(shown):
            item_text = self._format_monitor_value(item)[:18]
            if i % 2 == 1:
                stripe = pygame.Rect(card.x + 1, yy, card.w - 2, row_h)
                pygame.draw.rect(self.window, (247, 249, 252), stripe)
            index_surf = font.render(str(i + 1), True, (185, 185, 185))
            item_surf = font.render(item_text, True, text_color)
            self.window.blit(index_surf, (card.x + int(6 * factor),
                                          yy + (row_h - index_surf.get_height()) // 2))
            self.window.blit(item_surf, (card.x + int(28 * factor),
                                         yy + (row_h - item_surf.get_height()) // 2))
            pygame.draw.line(self.window, (235, 235, 235),
                             (card.x + 2, yy + row_h), (card.right - 2, yy + row_h))
            yy += row_h
        footer = font.render(f"{len(items)} items", True, (150, 150, 150))
        self.window.blit(footer, (card.right - footer.get_width() - int(6 * factor),
                                  card.bottom - footer.get_height() - int(3 * factor)))

    @staticmethod
    def _format_monitor_value(value) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return cast.num_to_string(value)
        return str(value)

    @staticmethod
    def _monitor_label(monitor) -> str:
        params = monitor.params
        opcode = monitor.opcode
        if opcode == "data_variable":
            return str(params.get("VARIABLE", ""))
        if opcode == "data_listcontents":
            return str(params.get("LIST", ""))
        names = {
            "sensing_timer": "Timer", "sensing_answer": "Answer",
            "sensing_mousedown": "Mouse Down?", "sensing_mousex": "Mouse X",
            "sensing_mousey": "Mouse Y", "sensing_loudness": "Loudness",
            "sensing_username": "Username",
        }
        if opcode in names:
            return names[opcode]
        if opcode.startswith("sensing_current"):
            menu = str(params.get("CURRENTMENU", "")).lower()
            return {"year": "year", "month": "month", "date": "date",
                    "dayofweek": "day of week", "hour": "hour",
                    "minute": "minute", "second": "second"}.get(menu, menu)
        if monitor.sprite_name:
            return f"{monitor.sprite_name}: {opcode.split('_')[-1]}"
        return ""

    # ---------------------------------------------------------- ask answer

    def _ask_bar_rect(self) -> pygame.Rect:
        rect = self._stage_rect()
        factor = rect.w / STAGE_W
        bar_h = int(24 * factor)
        bar_w = int(rect.w * 0.7)
        x = rect.x + (rect.w - bar_w) // 2
        y = rect.bottom - bar_h - int(8 * factor)
        return pygame.Rect(x, y, bar_w, bar_h)

    def _draw_ask_overlay(self, rect: pygame.Rect, factor: float):
        question = self.rt.active_question
        if question is None:
            self._typed = ""
            return
        bar = self._ask_bar_rect()
        text_color = (87, 94, 117)
        font = self.ui_font(12 * factor)

        if question:
            q_font = self.ui_font(11 * factor)
            q_text = str(question)[:60]
            q_surf = q_font.render(q_text, True, text_color)
            pad = int(8 * factor)
            chip = pygame.Rect(bar.x, bar.y - int(30 * factor),
                               q_surf.get_width() + pad * 2, int(22 * factor))
            chip.clamp_ip(pygame.Rect(rect.x, rect.y - int(28 * factor), rect.w, rect.h + int(28 * factor)))
            pygame.draw.rect(self.window, (255, 255, 255), chip,
                             border_radius=int(8 * factor))
            pygame.draw.rect(self.window, (219, 219, 219), chip,
                             width=max(1, int(1.2 * factor)),
                             border_radius=int(8 * factor))
            self.window.blit(q_surf, (chip.x + pad,
                                      chip.y + (chip.height - q_surf.get_height()) // 2))
            tail_start = (chip.x + int(18 * factor), chip.bottom - 1)
            pygame.draw.polygon(self.window, (255, 255, 255), [
                tail_start,
                (tail_start[0] + int(6 * factor), bar.y + 1),
                (tail_start[0] + int(12 * factor), chip.bottom - 1),
            ])

        pygame.draw.rect(self.window, (255, 255, 255), bar,
                         border_radius=int(8 * factor))
        pygame.draw.rect(self.window, (76, 151, 255), bar,
                         width=max(2, int(2 * factor)),
                         border_radius=int(8 * factor))
        caret_on = (pygame.time.get_ticks() // 450) % 2 == 0
        shown = self._typed + ("|" if caret_on else "")
        text_surf = font.render(shown, True, text_color)
        self.window.blit(text_surf, (bar.x + int(10 * factor),
                                     bar.y + (bar.height - text_surf.get_height()) // 2))

    # ------------------------------------------------------------ queries

    def mouse_x(self) -> float:
        return self._to_stage(pygame.mouse.get_pos())[0]

    def mouse_y(self) -> float:
        return self._to_stage(pygame.mouse.get_pos())[1]

    def _info_for(self, tgt) -> RenderInfo | None:
        info = self.info_cache.get(id(tgt))
        if info is None or info.surface is None:
            self.draw_frame_sprites_only_for(tgt)
            info = self.info_cache.get(id(tgt))
        elif self._info_is_stale(tgt, info):
            self.draw_frame_sprites_only_for(tgt)
            info = self.info_cache.get(id(tgt))
        return info if (info is not None and info.surface is not None) else None

    def _info_is_stale(self, tgt, info: RenderInfo) -> bool:
        if info.x != tgt.x or info.y != tgt.y:
            return True
        size_pct = round(tgt.size * 10) / 10.0
        direction_key = round(tgt.direction)
        costume = tgt.costume()
        md5 = costume.md5ext if costume else None
        if info.fp_size != size_pct or info.fp_direction != direction_key or info.fp_md5 != md5:
            return True
        return False

    def _stamp_info_fingerprint(self, info: RenderInfo, tgt):
        costume = tgt.costume()
        info.fp_size = round(tgt.size * 10) / 10.0
        info.fp_direction = round(tgt.direction)
        info.fp_md5 = costume.md5ext if costume else None

    def draw_frame_sprites_only_for(self, tgt):
        self._rendered_appearance(tgt)
        self._draw_sprite(tgt)

    def _ensure_mask(self, info: RenderInfo) -> pygame.mask.Mask:
        if info.mask is None:
            info.mask = pygame.mask.from_surface(info.surface, threshold=1)
        return info.mask

    def hit_test(self, tgt, x: float, y: float) -> bool:
        info = self._info_for(tgt)
        if info is None:
            return False
        local = self._world_to_pixel(info, x, y)
        if local is None:
            return False
        lx, ly = local
        if not (0 <= lx < info.surface.get_width() and 0 <= ly < info.surface.get_height()):
            return False
        return bool(info.surface.get_at((lx, ly))[3] > 8)

    def _world_to_pixel(self, info: RenderInfo, x: float, y: float):
        ex = x - info.x
        ey = -(y - info.y)
        u = ex + info.wr / 2.0 + info.ox
        v = ey + info.hr / 2.0 + info.oy
        cu = u - info.wr / 2.0
        cv = v - info.hr / 2.0
        theta = math.radians(info.angle)
        c, s = math.cos(theta), math.sin(theta)
        px = c * (cu - info.ox) - s * (cv - info.oy)
        py = s * (cu - info.ox) + c * (cv - info.oy)
        su = px + info.ws / 2.0
        sv = py + info.hs / 2.0
        if info.flipped:
            su = info.ws - su
        return int(su * info.rs), int(sv * info.rs)

    def sprites_touching(self, a, b) -> bool:
        ia = self._info_for(a)
        ib = self._info_for(b)
        if ia is None or ib is None:
            return False
        if not a.visible or not b.visible:
            return False
        ma = self._ensure_mask(ia)
        mb = self._ensure_mask(ib)
        rs_a, rs_b = ia.rs, ib.rs
        ax = int(round(ia.blit_x * rs_a))
        ay = int(round(ia.blit_y * rs_a))
        bx = int(round(ib.blit_x * rs_b))
        by = int(round(ib.blit_y * rs_b))
        return ma.overlap(mb, (bx - ax, by - ay)) is not None

    def touching_point(self, tgt, x: float, y: float) -> bool:
        return self.hit_test(tgt, x, y)

    def sprite_bounds(self, tgt):
        info = self._info_for(tgt)
        if info is None:
            return None
        left = info.blit_x - STAGE_W / 2
        right = left + info.wr
        top = STAGE_H / 2 - info.blit_y
        bottom = top - info.hr
        return (left, right, top, bottom)

    def touching_color(self, tgt, color) -> bool:
        info = self._info_for(tgt)
        if info is None:
            return False
        mask = self._ensure_mask(info)
        rs = info.rs
        ax = int(round(info.blit_x * rs))
        ay = int(round(info.blit_y * rs))
        w, h = info.surface.get_size()
        step = max(1, (w * h) // 60000)
        stage_arr = pygame.surfarray.array3d(self.stage)
        stage_w, stage_h = self.stage.get_size()
        target = numpy.array(color, dtype=numpy.int32)
        for ly in range(0, h, step):
            gy = ay + ly
            if gy < 0 or gy >= stage_h:
                continue
            for lx in range(0, w, step):
                gx = ax + lx
                if gx < 0 or gx >= stage_w:
                    continue
                if mask.get_at((lx, ly)):
                    sp = stage_arr[gx, gy]
                    d = int(sp[0]) - target[0], int(sp[1]) - target[1], int(sp[2]) - target[2]
                    if d[0] * d[0] + d[1] * d[1] + d[2] * d[2] <= 900:
                        return True
        return False

    def color_touching_color(self, tgt, color1, color2) -> bool:
        info = self._info_for(tgt)
        if info is None:
            return False
        mask = self._ensure_mask(info)
        rs = info.rs
        ax = int(round(info.blit_x * rs))
        ay = int(round(info.blit_y * rs))
        w, h = info.surface.get_size()
        step = max(1, (w * h) // 50000)
        sprite_arr = pygame.surfarray.array3d(info.surface)
        stage_arr = pygame.surfarray.array3d(self.stage)
        stage_w, stage_h = self.stage.get_size()
        t1 = numpy.array(color1, dtype=numpy.int32)
        t2 = numpy.array(color2, dtype=numpy.int32)
        for ly in range(0, h, step):
            gy = ay + ly
            if gy < 0 or gy >= stage_h:
                continue
            for lx in range(0, w, step):
                gx = ax + lx
                if gx < 0 or gx >= stage_w:
                    continue
                if not mask.get_at((lx, ly)):
                    continue
                sp = sprite_arr[lx, ly]
                d1 = (int(sp[0]) - t1[0], int(sp[1]) - t1[1], int(sp[2]) - t1[2])
                if d1[0] * d1[0] + d1[1] * d1[1] + d1[2] * d1[2] > 900:
                    continue
                stp = stage_arr[gx, gy]
                d2 = (int(stp[0]) - t2[0], int(stp[1]) - t2[1], int(stp[2]) - t2[2])
                if d2[0] * d2[0] + d2[1] * d2[1] + d2[2] * d2[2] <= 900:
                    return True
        return False

    # ----------------------------------------------------------------- pen

    def pen_clear(self):
        self.pen_layer.fill((0, 0, 0, 0))

    def pen_line(self, x1, y1, x2, y2, rgb, width: float, transparency: float):
        rs = self._rs
        alpha = int(255 * (1.0 - transparency / 100.0))
        color = (int(rgb[0]), int(rgb[1]), int(rgb[2]), alpha)
        sx1 = (x1 + STAGE_W / 2) * rs
        sy1 = (STAGE_H / 2 - y1) * rs
        sx2 = (x2 + STAGE_W / 2) * rs
        sy2 = (STAGE_H / 2 - y2) * rs
        w = max(1, int(round(width * rs)))
        pygame.draw.line(self.pen_layer, color, (sx1, sy1), (sx2, sy2), w)
        radius = w / 2.0
        if radius > 0.4:
            pygame.draw.circle(self.pen_layer, color, (sx1, sy1), radius)
            pygame.draw.circle(self.pen_layer, color, (sx2, sy2), radius)

    def stamp_sprite(self, tgt):
        info = self._fresh_info_for(tgt)
        if info is None:
            return
        pos = (int(round(info.blit_x * info.rs)), int(round(info.blit_y * info.rs)))
        self.pen_layer.blit(info.surface, pos)

    def _fresh_info_for(self, tgt):
        appearance = self._rendered_appearance(tgt)
        if appearance is None:
            return None
        surf, angle, flipped, px_per_unit, costume = appearance
        rs = self._rs
        ws = surf.get_width() / rs
        hs = surf.get_height() / rs
        rcx = costume.rotation_center_x * (tgt.size / 100.0)
        rcy = costume.rotation_center_y * (tgt.size / 100.0)
        theta = math.radians(angle)
        c, s = math.cos(theta), math.sin(theta)
        px, py = rcx - ws / 2.0, rcy - hs / 2.0
        ox = px * c + py * s
        oy = -px * s + py * c
        wr, hr = ws, hs
        blit_x = (tgt.x + STAGE_W / 2) - (wr / 2.0 + ox)
        blit_y = (STAGE_H / 2 - tgt.y) - (hr / 2.0 + oy)

        draw_surf = surf
        if flipped:
            draw_surf = pygame.transform.flip(surf, True, False)

        info = RenderInfo()
        info.surface = draw_surf
        info.mask = None
        info.blit_x = blit_x
        info.blit_y = blit_y
        info.angle = angle
        info.flipped = flipped
        info.wr, info.hr = wr, hr
        info.ox, info.oy = ox, oy
        info.ws, info.hs = ws, hs
        info.x, info.y = tgt.x, tgt.y
        info.rs = rs
        self._stamp_info_fingerprint(info, tgt)
        return info

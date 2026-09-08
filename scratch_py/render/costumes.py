"""Costume loading: PNG via pygame, SVG rasterized through resvg/cairosvg/svglib.

LoadedCostume.scale = surface pixels per stage unit at 100% sprite size.
SVGs rasterize at zoom = rs / bitmapResolution so one stage unit maps to rs
pixels, keeping vectors crisp at the display resolution of the window."""

from __future__ import annotations

import io

import pygame


class LoadedCostume:
    __slots__ = ("surface", "px_per_unit")

    def __init__(self, surface: pygame.Surface, px_per_unit: float):
        self.surface = surface
        self.px_per_unit = px_per_unit

    @property
    def width(self) -> float:
        return self.surface.get_width() / self.px_per_unit

    @property
    def height(self) -> float:
        return self.surface.get_height() / self.px_per_unit


class CostumeCache:
    def __init__(self, assets: dict[str, bytes]):
        self.assets = assets
        self.cache: dict[tuple[str, float], LoadedCostume | None] = {}
        self._svg_backend_warned = False
        self._warned_missing: set[str] = set()

    def get(self, costume, rs: float = 1.0) -> LoadedCostume | None:
        rs = max(1.0, float(rs))
        key = (costume.md5ext, rs)
        if key in self.cache:
            return self.cache[key]
        loaded = self._load(costume, rs)
        self.cache[key] = loaded
        return loaded

    def _surface_from_png(self, data: bytes) -> pygame.Surface:
        surface = pygame.image.load(io.BytesIO(data))
        try:
            return surface.convert_alpha()
        except (pygame.error, ValueError):
            return surface

    def _load(self, costume, rs: float) -> LoadedCostume | None:
        data = self.assets.get(costume.md5ext)
        if data is None:
            return self._placeholder(costume, f"missing asset {costume.md5ext}")
        fmt = costume.data_format.lower()
        try:
            if fmt == "svg":
                bitmap_res = max(1.0, float(costume.bitmap_resolution))
                surface = self._load_svg(data, rs / bitmap_res)
                if surface is None:
                    return self._placeholder(costume, "no SVG backend available")
                return LoadedCostume(surface, rs)
            surface = self._surface_from_png(data)
            return LoadedCostume(surface, max(1.0, float(costume.bitmap_resolution)))
        except (pygame.error, ValueError) as exc:
            print(f"[scratch.py render] costume {costume.md5ext} failed: {exc}")
            return None

    def _placeholder(self, costume, reason: str) -> LoadedCostume | None:
        if costume.md5ext not in self._warned_missing:
            self._warned_missing.add(costume.md5ext)
            print(f"[scratch.py render] {reason}")
        surface = pygame.Surface((32, 32), pygame.SRCALPHA)
        surface.fill((200, 80, 200, 160))
        pygame.draw.rect(surface, (60, 0, 60, 255), surface.get_rect(), 2)
        return LoadedCostume(surface, 1.0)

    def _load_svg(self, data: bytes, zoom: float) -> pygame.Surface | None:
        zoom = max(0.5, float(zoom))
        surface = self._load_svg_resvg(data, zoom)
        if surface is not None:
            return surface
        surface = self._load_svg_cairo(data, zoom)
        if surface is not None:
            return surface
        return self._load_svg_svglib(data, zoom)

    def _warn_svg(self, message: str):
        if not self._svg_backend_warned:
            self._svg_backend_warned = True
            print(f"[scratch.py render] {message}")

    def _load_svg_resvg(self, data: bytes, zoom: float) -> pygame.Surface | None:
        try:
            import resvg_py
        except ImportError:
            return None
        try:
            png_bytes = resvg_py.svg_to_bytes(
                svg_string=data.decode("utf-8", errors="replace"),
                zoom=zoom,
            )
            png_bytes = bytes(png_bytes)
        except Exception as exc:
            self._warn_svg(f"resvg failed ({exc})")
            return None
        if not png_bytes:
            return None
        try:
            return self._surface_from_png(png_bytes)
        except (pygame.error, ValueError) as exc:
            self._warn_svg(f"resvg output undecodable ({exc})")
            return None

    def _load_svg_cairo(self, data: bytes, zoom: float) -> pygame.Surface | None:
        try:
            import cairosvg
        except (ImportError, OSError):
            return None
        try:
            png_bytes = cairosvg.svg2png(bytestring=data, scale=zoom)
        except Exception as exc:
            self._warn_svg(f"cairosvg failed ({exc}); trying svglib")
            return None
        if png_bytes is None:
            return None
        return self._surface_from_png(png_bytes)

    def _load_svg_svglib(self, data: bytes, zoom: float) -> pygame.Surface | None:
        try:
            from reportlab.graphics import renderPM
            from svglib.svglib import svg2rlg
        except ImportError:
            self._warn_svg(
                "SVG rendering needs resvg-py (bundled by default); "
                "showing placeholders until then"
            )
            return None
        try:
            drawing = svg2rlg(io.BytesIO(data))
            if drawing is None:
                return None
            png_bytes = renderPM.drawToString(
                drawing, fmt="PNG", dpi=72 * zoom
            )
        except Exception as exc:
            self._warn_svg(f"svglib failed ({exc})")
            return None
        return self._surface_from_png(png_bytes)

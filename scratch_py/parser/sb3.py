"""Load .sb3 files (ZIP archives of project.json + content-addressed assets)."""

from __future__ import annotations

import zipfile

from .deserialize import parse_project
from .model import ProjectData


class SB3Error(Exception):
    pass


def load_sb3(path: str) -> tuple[ProjectData, dict[str, bytes]]:
    """Return (project model, assets keyed by md5.ext filename)."""
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, FileNotFoundError) as exc:
        raise SB3Error(f"cannot open sb3: {exc}") from exc
    with zf:
        names = zf.namelist()
        if "project.json" not in names:
            raise SB3Error("missing project.json; not a valid .sb3 archive")
        project = parse_project(zf.read("project.json").decode("utf-8-sig"))
        assets: dict[str, bytes] = {}
        for name in names:
            if name == "project.json":
                continue
            assets[name] = zf.read(name)
    return project, assets


def asset_bytes(assets: dict[str, bytes], md5ext: str) -> bytes | None:
    return assets.get(md5ext)

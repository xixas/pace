"""XDG paths and atomic JSON files. Files are created mode 600: they hold one person's hours or session."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def xdg(kind: str, fallback: str) -> Path:
    return Path(os.environ.get(f"XDG_{kind}_HOME") or Path.home() / fallback) / "pace"


def state_dir() -> Path:
    return xdg("STATE", ".local/state")


def data_dir() -> Path:
    return xdg("DATA", ".local/share")


def write_json(path: Path, obj) -> Path:
    """Replace path atomically, so a reader never sees half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}-")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)
    return path


def read_json(path: Path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None

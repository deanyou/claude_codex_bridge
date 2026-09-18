from __future__ import annotations

import os
from pathlib import Path


def run_dir() -> Path:
    override = (os.environ.get("CC_BRIDGE_RUN_DIR") or "").strip()
    if override:
        return Path(override).expanduser()

    if os.name == "nt":
        base = (os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or "").strip()
        if base:
            return Path(base) / "cc_bridge"
        return Path.home() / "AppData" / "Local" / "cc_bridge"

    xdg_cache = (os.environ.get("XDG_CACHE_HOME") or "").strip()
    if xdg_cache:
        return Path(xdg_cache) / "cc_bridge"
    return Path.home() / ".cache" / "cc_bridge"


def state_file_path(name: str) -> Path:
    if name.endswith(".json"):
        return run_dir() / name
    return run_dir() / f"{name}.json"


def log_path(name: str) -> Path:
    if name.endswith(".log"):
        return run_dir() / name
    return run_dir() / f"{name}.log"


__all__ = ["log_path", "run_dir", "state_file_path"]

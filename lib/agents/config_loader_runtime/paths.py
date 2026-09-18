from __future__ import annotations

from pathlib import Path

from project.discovery import CC_BRIDGE_DIRNAME

from .common import CONFIG_FILENAME


def project_config_path(project_root: Path) -> Path:
    return Path(project_root).expanduser().resolve() / CC_BRIDGE_DIRNAME / CONFIG_FILENAME


def user_default_config_path() -> Path:
    return Path.home().expanduser().resolve() / CC_BRIDGE_DIRNAME / CONFIG_FILENAME


__all__ = ['project_config_path', 'user_default_config_path']

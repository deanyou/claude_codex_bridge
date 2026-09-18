from __future__ import annotations

from pathlib import Path


CC_BRIDGE_PROJECT_CONFIG_DIRNAME = '.cc-bridge'


def project_config_dir(work_dir: Path) -> Path:
    return Path(work_dir).resolve() / CC_BRIDGE_PROJECT_CONFIG_DIRNAME


def resolve_project_config_dir(work_dir: Path) -> Path:
    return project_config_dir(work_dir)


__all__ = ['CC_BRIDGE_PROJECT_CONFIG_DIRNAME', 'project_config_dir', 'resolve_project_config_dir']

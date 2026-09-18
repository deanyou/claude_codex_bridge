from __future__ import annotations

import json
from pathlib import Path

from provider_core.pathing import session_filename_for_agent
from storage.path_helpers import runtime_project_anchor_from_path


def session_file_for_runtime_dir(runtime_dir: Path) -> Path | None:
    cc_bridge_dir = find_project_cc_bridge_dir(runtime_dir)
    if cc_bridge_dir is None:
        return None
    try:
        agent_name = runtime_dir.parents[1].name
    except Exception:
        return None
    agent_name = str(agent_name or '').strip()
    if not agent_name:
        return None
    return cc_bridge_dir / session_filename_for_agent('gemini', agent_name)


def state_dir_for_runtime_dir(runtime_dir: Path) -> Path | None:
    current = Path(runtime_dir)
    normalized_provider = str(current.name or '').strip().lower()
    if not normalized_provider:
        return None
    parent = current.parent
    if parent.name != 'provider-runtime':
        return None
    agent_dir = parent.parent
    if not agent_dir.name:
        return None
    return agent_dir / 'provider-state' / normalized_provider


def find_project_cc_bridge_dir(runtime_dir: Path) -> Path | None:
    current = Path(runtime_dir)
    for parent in (current, *current.parents):
        if parent.name == '.cc-bridge':
            return parent
    return runtime_project_anchor_from_path(current)


def read_session_payload(session_path: Path) -> dict[str, object] | None:
    try:
        data = json.loads(session_path.read_text(encoding='utf-8'))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


__all__ = ['find_project_cc_bridge_dir', 'read_session_payload', 'session_file_for_runtime_dir', 'state_dir_for_runtime_dir']

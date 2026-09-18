from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable


def publish_claude_registry(
    *,
    session_info: dict[str, Any],
    terminal: str,
    pane_id: str | None,
    project_session_file: str | None,
    compute_cc_bridge_project_id_fn: Callable[[Path], str],
    upsert_registry_fn: Callable[[dict[str, object]], None],
    cwd_fn: Callable[[], Path],
) -> None:
    try:
        cc_bridge_session_id = str(session_info.get('cc_bridge_session_id') or os.environ.get('CC_BRIDGE_SESSION_ID') or '').strip()
        if not cc_bridge_session_id:
            return
        work_dir = _work_dir(session_info, cwd_fn=cwd_fn)
        cc_bridge_project_id = str(session_info.get('cc_bridge_project_id') or '').strip() or compute_cc_bridge_project_id_fn(work_dir)
        upsert_registry_fn(
            {
                'cc_bridge_session_id': cc_bridge_session_id,
                'cc_bridge_project_id': cc_bridge_project_id or None,
                'work_dir': str(work_dir),
                'terminal': terminal,
                'providers': {
                    'claude': {
                        'pane_id': pane_id or None,
                        'pane_title_marker': session_info.get('pane_title_marker'),
                        'session_file': project_session_file,
                        'claude_session_id': session_info.get('claude_session_id'),
                        'claude_session_path': session_info.get('claude_session_path'),
                    }
                },
            }
        )
    except Exception:
        pass


def _work_dir(session_info: dict[str, Any], *, cwd_fn: Callable[[], Path]) -> Path:
    wd = session_info.get('work_dir')
    if isinstance(wd, str) and wd:
        return Path(wd)
    return cwd_fn()


__all__ = ['publish_claude_registry']

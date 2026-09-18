from __future__ import annotations

from pathlib import Path

from provider_core.inherited_skills import (
    materialize_required_control_skills,
    required_control_skills_ready,
)


GROK_CC_BRIDGE_SKILL_NAMES = ('ask', 'cc-bridge-clear', 'cc-bridge-compact', 'cc-bridge-diagnose')


def materialize_grok_skills(target_home: Path, *, profile=None) -> tuple[str, ...]:
    del profile
    target_root = Path(target_home).expanduser() / '.grok' / 'skills'
    return materialize_required_control_skills(
        provider='grok',
        target_dir=target_root,
    )


def grok_cc_bridge_skills_ready(target_home: Path) -> bool:
    target_root = Path(target_home).expanduser() / '.grok' / 'skills'
    return required_control_skills_ready(
        provider='grok',
        target_dir=target_root,
    )


def grok_skill_permission_args() -> tuple[str, ...]:
    return (
        '--allow',
        'Bash(command ask *)',
        '--allow',
        'Bash(command cc_bridge clear*)',
        '--allow',
        'Bash(command cc_bridge ping *)',
        '--allow',
        'Bash(command cc_bridge ps)',
        '--allow',
        'Bash(command cc_bridge queue *)',
        '--allow',
        'Bash(command cc_bridge pend *)',
        '--allow',
        'Bash(command cc_bridge doctor *)',
        '--allow',
        'Bash(command cc_bridge trace *)',
        '--allow',
        'Bash(command cc_bridge cancel *)',
        '--allow',
        'Bash(command cc_bridge repair *)',
        '--allow',
        'Bash(command cc_bridge restart *)',
        '--allow',
        'Bash(command cc_bridge config *)',
        '--allow',
        'Bash(command cc_bridge reload *)',
        '--allow',
        'Bash(command tmux -S * display-message *)',
        '--allow',
        'Bash(command tmux -S * capture-pane *)',
    )


__all__ = [
    'GROK_CC_BRIDGE_SKILL_NAMES',
    'grok_cc_bridge_skills_ready',
    'grok_skill_permission_args',
    'materialize_grok_skills',
]

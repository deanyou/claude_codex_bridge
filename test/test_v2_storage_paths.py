from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from storage.paths import PathLayout
from storage.path_helpers import runtime_project_anchor_from_path, runtime_state_root_from_anchor_ref


def test_path_layout_uses_project_scoped_locations(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    assert layout.cc_bridge_dir == (tmp_path / 'repo' / '.cc-bridge').resolve()
    assert layout.project_anchor_dir == layout.cc_bridge_dir
    assert layout.runtime_state_root == layout.cc_bridge_dir
    assert layout.runtime_state_placement.root_kind == 'project'
    assert layout.runtime_marker_status == 'not_required'
    assert layout.config_path == layout.cc_bridge_dir / 'cc_bridge.config'
    assert layout.cc_bridge_daemon_lifecycle_path == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'lifecycle.json'
    assert layout.cc_bridge_daemon_lease_path == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'lease.json'
    assert layout.cc_bridge_daemon_socket_path.name in {'cc_bridge_daemon.sock', f'cc_bridge_daemon-{layout.project_socket_key}.sock'}
    assert len(os.fsencode(str(layout.cc_bridge_daemon_socket_path))) <= 100
    assert layout.cc_bridge_daemon_state_path == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'state.json'
    assert layout.cc_bridge_daemon_start_policy_path == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'start-policy.json'
    assert layout.cc_bridge_daemon_startup_report_path == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'startup-report.json'
    assert layout.cc_bridge_daemon_shutdown_report_path == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'shutdown-report.json'
    assert layout.cc_bridge_daemon_tmux_socket_path.name in {'tmux.sock', f'tmux-{layout.project_socket_key}.sock'}
    assert len(os.fsencode(str(layout.cc_bridge_daemon_tmux_socket_path))) <= 100
    assert layout.cc_bridge_daemon_tmux_session_name == f'cc_bridge-{layout.project_slug}'
    assert layout.cc_bridge_daemon_lifecycle_log_path == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'lifecycle.jsonl'
    assert layout.cc_bridge_daemon_support_dir == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'support'
    assert layout.cc_bridge_daemon_keeper_path == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'keeper.json'
    assert layout.cc_bridge_daemon_shutdown_intent_path == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'shutdown-intent.json'
    assert layout.agent_mailbox_path('Agent1') == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'mailboxes' / 'agent1' / 'mailbox.json'
    assert layout.agent_inbox_path('Agent1') == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'mailboxes' / 'agent1' / 'inbox.jsonl'
    assert layout.cc_bridge_daemon_messages_path == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'messages' / 'messages.jsonl'
    assert layout.cc_bridge_daemon_attempts_path == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'attempts' / 'attempts.jsonl'
    assert layout.cc_bridge_daemon_replies_path == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'replies' / 'replies.jsonl'
    assert layout.mailbox_lease_path('Agent1') == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'leases' / 'agent1.json'
    assert layout.provider_health_path('job-1') == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'provider-health' / 'job-1.jsonl'
    assert layout.agent_runtime_path('Agent1') == layout.cc_bridge_dir / 'agents' / 'agent1' / 'runtime.json'
    assert layout.agent_provider_state_dir('Agent1', 'CoDeX') == layout.cc_bridge_dir / 'agents' / 'agent1' / 'provider-state' / 'codex'
    assert layout.snapshot_path('job-1') == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'snapshots' / 'job-1.json'
    assert layout.cursor_path('job-1') == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'cursors' / 'job-1.json'
    assert layout.support_bundle_path('bundle-1') == layout.cc_bridge_dir / 'cc_bridge_daemon' / 'support' / 'bundle-1.tar.gz'
    assert layout.workspace_path('Agent1') == layout.cc_bridge_dir / 'workspaces' / 'agent1'
    assert layout.provider_profiles_dir == layout.cc_bridge_dir / 'provider-profiles'


def test_path_layout_supports_external_workspace_root(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    external = tmp_path / 'external-workspaces'
    workspace = layout.workspace_path('agent1', workspace_root=str(external))
    assert workspace == external / layout.project_slug / 'agent1'
    assert layout.workspace_binding_path('agent1', workspace_root=str(external)).name == '.cc_bridge-workspace.json'


def test_path_layout_shortens_socket_paths_when_project_path_is_too_long(tmp_path: Path) -> None:
    project_root = tmp_path / ('very-long-project-name-' * 4) / ('nested-segment-' * 4) / 'repo'
    layout = PathLayout(project_root)

    assert layout.cc_bridge_daemon_socket_path.name == f'cc_bridge_daemon-{layout.project_socket_key}.sock'
    assert layout.cc_bridge_daemon_tmux_socket_path.name == f'tmux-{layout.project_socket_key}.sock'
    assert '.cc-bridge/cc_bridge_daemon' not in str(layout.cc_bridge_daemon_socket_path)
    assert '.cc-bridge/cc_bridge_daemon' not in str(layout.cc_bridge_daemon_tmux_socket_path)
    assert len(os.fsencode(str(layout.cc_bridge_daemon_socket_path))) <= 100
    assert len(os.fsencode(str(layout.cc_bridge_daemon_tmux_socket_path))) <= 100


def test_path_layout_falls_back_for_wsl_mounted_drive_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv('WSL_INTEROP', '1')
    monkeypatch.setenv('XDG_RUNTIME_DIR', '/mnt/e/runtime')
    monkeypatch.setenv('XDG_STATE_HOME', '/t')

    layout = PathLayout(Path('/mnt/c/Users/demo/repo'))

    assert layout.runtime_state_placement.root_kind == 'relocated'
    assert layout.runtime_state_placement.relocation_reason == 'wsl_drvfs'
    assert layout.runtime_state_root == Path('/t/cc_bridge/projects') / layout.project_id
    assert layout.cc_bridge_daemon_dir == layout.runtime_state_root / 'cc_bridge_daemon'
    assert layout.agents_dir == layout.runtime_state_root / 'agents'
    assert layout.config_path == Path('/mnt/c/Users/demo/repo/.cc-bridge/cc_bridge.config')
    assert layout.workspaces_dir == Path('/mnt/c/Users/demo/repo/.cc-bridge/workspaces')
    assert layout.cc_bridge_daemon_socket_placement.root_kind == 'runtime'
    assert layout.cc_bridge_daemon_socket_placement.fallback_reason is None
    assert layout.cc_bridge_daemon_socket_placement.filesystem_hint is None
    assert layout.cc_bridge_daemon_socket_placement.preferred_path == layout.runtime_state_root / 'cc_bridge_daemon' / 'cc_bridge_daemon.sock'
    assert layout.cc_bridge_daemon_socket_path == layout.runtime_state_root / 'cc_bridge_daemon' / 'cc_bridge_daemon.sock'
    assert layout.cc_bridge_daemon_tmux_socket_placement.root_kind == 'runtime'
    assert layout.cc_bridge_daemon_tmux_socket_placement.fallback_reason is None
    assert layout.cc_bridge_daemon_tmux_socket_placement.filesystem_hint is None
    assert layout.cc_bridge_daemon_tmux_socket_placement.preferred_path == layout.runtime_state_root / 'cc_bridge_daemon' / 'tmux.sock'
    assert layout.cc_bridge_daemon_tmux_socket_path == layout.runtime_state_root / 'cc_bridge_daemon' / 'tmux.sock'


def test_path_layout_uses_anchor_ref_for_relocated_runtime(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-ref'
    layout = PathLayout(project_root)
    relocated_root = Path('/r')
    layout.cc_bridge_dir.mkdir(parents=True, exist_ok=True)
    layout.runtime_root_ref_path.write_text(
        '{"schema_version":1,"record_type":"cc_bridge_runtime_root_ref","project_id":"'
        + layout.project_id
        + '","runtime_state_root":"'
        + str(relocated_root)
        + '","created_at":"2026-05-07T00:00:00Z"}',
        encoding='utf-8',
    )

    relocated = PathLayout(project_root)

    assert relocated.runtime_state_placement.root_kind == 'relocated'
    assert relocated.runtime_state_placement.relocation_reason == 'runtime_root_ref'
    assert relocated.runtime_state_root == relocated_root
    assert relocated.cc_bridge_daemon_dir == relocated_root / 'cc_bridge_daemon'
    assert relocated.agents_dir == relocated_root / 'agents'
    assert relocated.cc_bridge_daemon_socket_path == relocated_root / 'cc_bridge_daemon' / 'cc_bridge_daemon.sock'
    assert relocated.cc_bridge_daemon_tmux_socket_path == relocated_root / 'cc_bridge_daemon' / 'tmux.sock'
    assert relocated.runtime_marker_status == 'missing'


def test_path_layout_relocated_runtime_root_falls_back_only_for_socket_path_length(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv('WSL_INTEROP', '1')
    monkeypatch.setenv('XDG_RUNTIME_DIR', '/mnt/e/runtime')
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))

    layout = PathLayout(Path('/mnt/c/Users/demo/repo'))

    assert layout.cc_bridge_daemon_socket_placement.preferred_path == layout.runtime_state_root / 'cc_bridge_daemon' / 'cc_bridge_daemon.sock'
    assert layout.cc_bridge_daemon_socket_placement.root_kind == 'runtime'
    assert layout.cc_bridge_daemon_socket_placement.fallback_reason == 'path_too_long'
    assert str(layout.cc_bridge_daemon_socket_path).startswith('/tmp/cc_bridge-runtime/')
    assert layout.cc_bridge_daemon_tmux_socket_placement.preferred_path == layout.runtime_state_root / 'cc_bridge_daemon' / 'tmux.sock'
    assert layout.cc_bridge_daemon_tmux_socket_placement.fallback_reason == 'path_too_long'
    assert str(layout.cc_bridge_daemon_tmux_socket_path).startswith('/tmp/cc_bridge-runtime/')


def test_path_layout_wsl_runtime_state_uses_account_home_instead_of_process_home(monkeypatch, tmp_path: Path) -> None:
    provider_home = tmp_path / 'provider-home'
    account_home = tmp_path / 'account-home'
    monkeypatch.setenv('WSL_INTEROP', '1')
    monkeypatch.setenv('HOME', str(provider_home))
    monkeypatch.delenv('XDG_STATE_HOME', raising=False)
    monkeypatch.setattr('storage.path_helpers._account_home_dir', lambda: account_home)

    layout = PathLayout(Path('/mnt/c/Users/demo/repo'))

    assert layout.runtime_state_root == account_home / '.local' / 'state' / 'cc_bridge' / 'projects' / layout.project_id
    assert str(layout.runtime_state_root).startswith(str(account_home))
    assert not str(layout.runtime_state_root).startswith(str(provider_home))


def test_path_layout_honors_runtime_state_home_without_anchor_ref(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-source-dev'
    runtime_state_home = tmp_path / 'source-dev-state' / 'runtime-state'
    monkeypatch.setenv('CC_BRIDGE_RUNTIME_STATE_HOME', str(runtime_state_home))

    layout = PathLayout(project_root)

    assert layout.runtime_state_placement.root_kind == 'relocated'
    assert layout.runtime_state_placement.relocation_reason == 'runtime_state_home'
    assert layout.runtime_state_root == runtime_state_home / layout.project_id
    assert layout.cc_bridge_daemon_dir == layout.runtime_state_root / 'cc_bridge_daemon'
    assert layout.runtime_marker_status == 'missing'


def test_runtime_state_root_from_anchor_ref_rejects_invalid_payloads(tmp_path: Path) -> None:
    anchor = tmp_path / 'repo' / '.cc-bridge'
    anchor.mkdir(parents=True, exist_ok=True)
    ref_path = anchor / 'runtime-root-ref.json'

    ref_path.write_text(
        '{"schema_version":1,"record_type":"wrong","project_id":"proj-1","runtime_state_root":"/tmp/state"}',
        encoding='utf-8',
    )
    assert runtime_state_root_from_anchor_ref(anchor, project_id='proj-1') is None

    ref_path.write_text(
        '{"schema_version":1,"record_type":"cc_bridge_runtime_root_ref","project_id":"proj-1","runtime_state_root":"relative/state"}',
        encoding='utf-8',
    )
    assert runtime_state_root_from_anchor_ref(anchor, project_id='proj-1') is None


def test_runtime_project_anchor_from_path_rejects_invalid_marker_payloads(tmp_path: Path) -> None:
    relocated_root = tmp_path / 'state-root'
    relocated_root.mkdir(parents=True, exist_ok=True)
    marker_path = relocated_root / 'runtime-root.json'

    marker_path.write_text(
        '{"schema_version":1,"record_type":"wrong","project_id":"proj-1","project_root":"/tmp/repo","anchor_path":"/tmp/repo/.cc-bridge","runtime_root_path":"'
        + str(relocated_root)
        + '"}',
        encoding='utf-8',
    )
    assert runtime_project_anchor_from_path(relocated_root / 'agents') is None

    marker_path.write_text(
        '{"schema_version":1,"record_type":"cc_bridge_runtime_root","project_id":"","project_root":"/tmp/repo","anchor_path":"/tmp/repo/.cc-bridge","runtime_root_path":"'
        + str(relocated_root)
        + '"}',
        encoding='utf-8',
    )
    assert runtime_project_anchor_from_path(relocated_root / 'agents') is None

    marker_path.write_text(
        '{"schema_version":1,"record_type":"cc_bridge_runtime_root","project_id":"proj-1","project_root":"/tmp/repo","anchor_path":"/tmp/repo/.cc-bridge","runtime_root_path":"'
        + str(tmp_path / 'other-root')
        + '"}',
        encoding='utf-8',
    )
    assert runtime_project_anchor_from_path(relocated_root / 'agents') is None


def test_storage_paths_and_project_runtime_paths_import_without_cycle() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            '-c',
            (
                'from storage.paths import PathLayout; '
                'from project.runtime_paths import project_cc_bridge_daemon_dir; '
                'print(PathLayout); print(project_cc_bridge_daemon_dir)'
            ),
        ],
        cwd=repo_root,
        env={**os.environ, 'PYTHONPATH': str(repo_root / 'lib')},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr

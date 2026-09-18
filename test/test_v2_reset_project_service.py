from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from agents.models import PermissionMode, QueuePolicy, RestoreMode, RuntimeMode, WorkspaceMode
from agents.models import AgentSpec
from cli.services.reset_project import reset_project_state
from project.identity_store import ensure_project_identity, load_project_identity
from project.resolver import bootstrap_project
from storage.paths import PathLayout
from workspace.materializer import WorkspaceMaterializer
from workspace.planner import WorkspacePlanner


def _spec() -> AgentSpec:
    return AgentSpec(
        name='agent1',
        provider='codex',
        target='.',
        workspace_mode=WorkspaceMode.GIT_WORKTREE,
        workspace_root=None,
        runtime_mode=RuntimeMode.PANE_BACKED,
        restore_default=RestoreMode.AUTO,
        permission_default=PermissionMode.MANUAL,
        queue_policy=QueuePolicy.SERIAL_PER_AGENT,
        branch_template=None,
    )


def test_reset_project_state_preserves_config_memory_and_same_named_provider_history(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = tmp_path / 'repo-reset'
    cc_bridge_dir = project_root / '.cc-bridge'
    cc_bridge_dir.mkdir(parents=True)
    (cc_bridge_dir / 'cc_bridge.config').write_text('cmd; agent1:codex, agent2:claude\n', encoding='utf-8')
    (cc_bridge_dir / 'cc_bridge_memory.md').write_text('shared memory\n', encoding='utf-8')
    (cc_bridge_dir / 'history' / 'handoff.md').parent.mkdir(parents=True, exist_ok=True)
    (cc_bridge_dir / 'history' / 'handoff.md').write_text('handoff\n', encoding='utf-8')
    (cc_bridge_dir / 'cc_bridge_daemon' / 'state.json').parent.mkdir(parents=True, exist_ok=True)
    (cc_bridge_dir / 'cc_bridge_daemon' / 'state.json').write_text('{}', encoding='utf-8')
    identity = ensure_project_identity(
        project_root,
        clock=lambda: '2026-07-24T00:00:00Z',
        id_factory=lambda: 'f' * 64,
    )
    (cc_bridge_dir / 'agents' / 'agent1' / 'runtime.json').parent.mkdir(parents=True, exist_ok=True)
    (cc_bridge_dir / 'agents' / 'agent1' / 'runtime.json').write_text('{}', encoding='utf-8')
    (cc_bridge_dir / 'agents' / 'agent1' / 'memory.md').write_text('private memory\n', encoding='utf-8')
    (cc_bridge_dir / 'agents' / 'agent1' / 'provider-state' / 'codex' / 'home' / 'sessions').mkdir(
        parents=True,
        exist_ok=True,
    )
    (cc_bridge_dir / 'agents' / 'agent1' / 'provider-state' / 'codex' / 'home' / 'sessions' / 'rollout.jsonl').write_text(
        'codex history\n',
        encoding='utf-8',
    )
    (cc_bridge_dir / 'agents' / 'agent1' / 'provider-state' / 'claude' / 'home').mkdir(parents=True, exist_ok=True)
    (cc_bridge_dir / 'agents' / 'agent1' / 'provider-state' / 'claude' / 'home' / 'old.jsonl').write_text(
        'wrong provider\n',
        encoding='utf-8',
    )
    (
        cc_bridge_dir
        / 'agents'
        / 'agent2'
        / 'provider-state'
        / 'claude'
        / 'home'
        / '.claude'
        / 'projects'
    ).mkdir(parents=True, exist_ok=True)
    (
        cc_bridge_dir
        / 'agents'
        / 'agent2'
        / 'provider-state'
        / 'claude'
        / 'home'
        / '.claude'
        / 'projects'
        / 'conversation.jsonl'
    ).write_text('claude history\n', encoding='utf-8')
    (cc_bridge_dir / 'agents' / 'agent2' / 'provider-runtime' / 'claude' / 'fifo').parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    (cc_bridge_dir / 'agents' / 'agent2' / 'provider-runtime' / 'claude' / 'fifo').write_text(
        'runtime\n',
        encoding='utf-8',
    )
    (cc_bridge_dir / 'agents' / 'agent3' / 'provider-state' / 'codex' / 'home').mkdir(parents=True, exist_ok=True)
    (cc_bridge_dir / 'agents' / 'agent3' / 'provider-state' / 'codex' / 'home' / 'old.jsonl').write_text(
        'unconfigured\n',
        encoding='utf-8',
    )
    (cc_bridge_dir / 'workspaces' / 'agent1' / 'memory.txt').parent.mkdir(parents=True, exist_ok=True)
    (cc_bridge_dir / 'workspaces' / 'agent1' / 'memory.txt').write_text('old', encoding='utf-8')
    (cc_bridge_dir / '.codex-agent1-session').write_text('session', encoding='utf-8')
    (cc_bridge_dir / '.claude-agent2-session').write_text('claude-session', encoding='utf-8')
    (cc_bridge_dir / '.codex-agent2-session').write_text('wrong-session', encoding='utf-8')

    seen: dict[str, object] = {}

    def _fake_stop(context) -> None:
        seen['project_root'] = context.project.project_root

    monkeypatch.setattr('cli.services.reset_project._stop_project_runtime', _fake_stop)

    summary = reset_project_state(project_root)

    assert summary.reset_performed is True
    assert summary.preserved_config is True
    assert summary.preserved_provider_histories == 2
    assert summary.preserved_session_files == 2
    assert summary.preserved_user_files == 3
    assert load_project_identity(project_root) == identity
    assert seen['project_root'] == project_root.resolve()
    assert cc_bridge_dir.is_dir()
    assert (cc_bridge_dir / 'cc_bridge.config').read_text(encoding='utf-8') == 'cmd; agent1:codex, agent2:claude\n'
    assert sorted(path.relative_to(cc_bridge_dir).as_posix() for path in cc_bridge_dir.rglob('*') if path.is_file()) == [
        '.claude-agent2-session',
        '.codex-agent1-session',
        'agents/agent1/memory.md',
        'agents/agent1/provider-state/codex/home/sessions/rollout.jsonl',
        'agents/agent2/provider-state/claude/home/.claude/projects/conversation.jsonl',
        'cc_bridge.config',
        'cc_bridge_memory.md',
        'history/handoff.md',
        'project.identity.json',
    ]


def test_reset_project_state_fails_fast_when_runtime_cleanup_cannot_stop_project(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-reset-fails'
    cc_bridge_dir = project_root / '.cc-bridge'
    cc_bridge_dir.mkdir(parents=True)
    (cc_bridge_dir / 'cc_bridge.config').write_text('cmd; agent1:codex\n', encoding='utf-8')
    (cc_bridge_dir / 'agents' / 'agent1' / 'runtime.json').parent.mkdir(parents=True, exist_ok=True)
    (cc_bridge_dir / 'agents' / 'agent1' / 'runtime.json').write_text('{}', encoding='utf-8')

    def _raise(label: str):
        def _inner(*args, **kwargs):
            del args, kwargs
            raise RuntimeError(f'{label} failed')
        return _inner

    class _FailingNamespaceController:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def destroy(self, *args, **kwargs) -> None:
            del args, kwargs
            raise RuntimeError('namespace failed')

    monkeypatch.setattr('cli.services.reset_project.kill_project', _raise('kill'))
    monkeypatch.setattr('cli.services.reset_project.shutdown_daemon', _raise('shutdown'))
    monkeypatch.setattr('cli.services.reset_project.ProjectNamespaceController', _FailingNamespaceController)

    with pytest.raises(RuntimeError, match='cc_bridge kill -f'):
        reset_project_state(project_root)

    assert cc_bridge_dir.is_dir()
    assert (cc_bridge_dir / 'cc_bridge.config').read_text(encoding='utf-8') == 'cmd; agent1:codex\n'
    assert (cc_bridge_dir / 'agents' / 'agent1' / 'runtime.json').is_file()


def test_reset_project_state_drops_invalid_runtime_root_ref(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-reset-invalid-ref'
    cc_bridge_dir = project_root / '.cc-bridge'
    cc_bridge_dir.mkdir(parents=True)
    (cc_bridge_dir / 'cc_bridge.config').write_text('cmd; agent1:codex\n', encoding='utf-8')
    (cc_bridge_dir / 'runtime-root-ref.json').write_text(
        '{"schema_version":1,"record_type":"cc_bridge_runtime_root_ref","project_id":"proj-1","runtime_state_root":"relative/state"}',
        encoding='utf-8',
    )
    (cc_bridge_dir / 'agents' / 'agent1' / 'runtime.json').parent.mkdir(parents=True, exist_ok=True)
    (cc_bridge_dir / 'agents' / 'agent1' / 'runtime.json').write_text('{}', encoding='utf-8')

    monkeypatch.setattr('cli.services.reset_project._stop_project_runtime', lambda context: None)

    summary = reset_project_state(project_root)

    assert summary.reset_performed is True
    assert (cc_bridge_dir / 'cc_bridge.config').read_text(encoding='utf-8') == 'cmd; agent1:codex\n'
    assert (cc_bridge_dir / 'runtime-root-ref.json').exists() is False


def test_reset_project_state_preserves_relocated_same_named_provider_history(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = tmp_path / 'repo-reset-relocated-history'
    cc_bridge_dir = project_root / '.cc-bridge'
    relocated_root = tmp_path / 'state-root'
    cc_bridge_dir.mkdir(parents=True)
    relocated_root.mkdir(parents=True)
    (cc_bridge_dir / 'cc_bridge.config').write_text('agent1:codex\n', encoding='utf-8')
    initial_layout = PathLayout(project_root)
    (cc_bridge_dir / 'runtime-root-ref.json').write_text(
        '{"schema_version":1,"record_type":"cc_bridge_runtime_root_ref","project_id":"'
        + initial_layout.project_id
        + '","runtime_state_root":"'
        + str(relocated_root)
        + '","created_at":"2026-05-22T00:00:00Z"}',
        encoding='utf-8',
    )
    reset_layout = PathLayout(project_root)
    reset_layout.ensure_runtime_state_root(created_at='2026-05-22T00:00:00Z')
    provider_history = reset_layout.agent_provider_state_dir('agent1', 'codex') / 'home' / 'sessions' / 'keep.jsonl'
    provider_history.parent.mkdir(parents=True, exist_ok=True)
    provider_history.write_text('relocated history\n', encoding='utf-8')
    runtime_junk = reset_layout.agent_provider_runtime_dir('agent1', 'codex') / 'completion' / 'job.json'
    runtime_junk.parent.mkdir(parents=True, exist_ok=True)
    runtime_junk.write_text('{}', encoding='utf-8')

    monkeypatch.setattr('cli.services.reset_project._stop_project_runtime', lambda context: None)

    summary = reset_project_state(project_root)

    assert summary.reset_performed is True
    assert summary.preserved_provider_histories == 1
    assert provider_history.read_text(encoding='utf-8') == 'relocated history\n'
    assert runtime_junk.exists() is False
    assert (cc_bridge_dir / 'runtime-root-ref.json').is_file()


def test_reset_project_state_restores_staged_history_when_clear_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = tmp_path / 'repo-reset-clear-fails'
    cc_bridge_dir = project_root / '.cc-bridge'
    cc_bridge_dir.mkdir(parents=True)
    (cc_bridge_dir / 'cc_bridge.config').write_text('agent1:codex\n', encoding='utf-8')
    history_file = cc_bridge_dir / 'agents' / 'agent1' / 'provider-state' / 'codex' / 'home' / 'sessions' / 'keep.jsonl'
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text('history survives\n', encoding='utf-8')

    monkeypatch.setattr('cli.services.reset_project._stop_project_runtime', lambda context: None)

    def _fail_clear(layout) -> None:
        del layout
        raise RuntimeError('clear failed')

    monkeypatch.setattr('cli.services.reset_project._clear_runtime_state', _fail_clear)

    with pytest.raises(RuntimeError, match='clear failed'):
        reset_project_state(project_root)

    assert history_file.read_text(encoding='utf-8') == 'history survives\n'


def test_reset_project_state_unregisters_git_worktrees_before_clearing_anchor(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-reset-git-worktree'
    project_root.mkdir(parents=True)
    (project_root / 'README.md').write_text('hello\n', encoding='utf-8')
    subprocess.run(['git', 'init'], cwd=project_root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=project_root, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=project_root, check=True)
    subprocess.run(['git', 'add', '.'], cwd=project_root, check=True)
    subprocess.run(['git', 'commit', '-m', 'init'], cwd=project_root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    cc_bridge_dir = project_root / '.cc-bridge'
    cc_bridge_dir.mkdir(parents=True, exist_ok=True)
    (cc_bridge_dir / 'cc_bridge.config').write_text('agent1:codex\n', encoding='utf-8')

    ctx = bootstrap_project(project_root)
    plan = WorkspacePlanner().plan(_spec(), ctx)
    WorkspaceMaterializer().materialize(plan)
    assert plan.workspace_path.exists()

    monkeypatch.setattr('cli.services.reset_project._stop_project_runtime', lambda context: None)

    summary = reset_project_state(project_root)

    assert summary.reset_performed is True
    assert (cc_bridge_dir / 'cc_bridge.config').read_text(encoding='utf-8') == 'agent1:codex\n'
    assert plan.workspace_path.exists() is False

    worktrees = subprocess.run(
        ['git', '-C', str(project_root), 'worktree', 'list', '--porcelain'],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout
    assert str(plan.workspace_path) not in worktrees

    rebuilt_ctx = bootstrap_project(project_root)
    rebuilt_plan = WorkspacePlanner().plan(_spec(), rebuilt_ctx)
    result = WorkspaceMaterializer().materialize(rebuilt_plan)

    assert result.created is True
    assert rebuilt_plan.workspace_path.exists()


def test_reset_project_state_blocks_unmerged_worktree_before_runtime_stop(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-reset-block-worktree'
    project_root.mkdir(parents=True)
    (project_root / 'README.md').write_text('hello\n', encoding='utf-8')
    subprocess.run(['git', 'init'], cwd=project_root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=project_root, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=project_root, check=True)
    subprocess.run(['git', 'add', '.'], cwd=project_root, check=True)
    subprocess.run(['git', 'commit', '-m', 'init'], cwd=project_root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    cc_bridge_dir = project_root / '.cc-bridge'
    cc_bridge_dir.mkdir(parents=True, exist_ok=True)
    (cc_bridge_dir / 'cc_bridge.config').write_text('agent1:codex(worktree)\n', encoding='utf-8')

    ctx = bootstrap_project(project_root)
    plan = WorkspacePlanner().plan(_spec(), ctx)
    WorkspaceMaterializer().materialize(plan)
    (plan.workspace_path / 'feature.txt').write_text('worktree-only\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(plan.workspace_path), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(plan.workspace_path), 'commit', '-m', 'worktree'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    seen: dict[str, object] = {}

    def _fake_stop(context) -> None:
        seen['stopped'] = context.project.project_root

    monkeypatch.setattr('cli.services.reset_project._stop_project_runtime', _fake_stop)

    with pytest.raises(RuntimeError, match='cc_bridge -n blocked'):
        reset_project_state(project_root)

    assert seen == {}
    assert plan.workspace_path.exists() is True
    assert cc_bridge_dir.exists() is True

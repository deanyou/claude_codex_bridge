from __future__ import annotations

from agents.config_loader import load_project_config
from cc_bridge_daemon.supervisor import RuntimeSupervisor
from project.resolver import bootstrap_project
from storage.paths import PathLayout


def test_runtime_supervisor_stop_all_ignores_invalid_runtime_file_for_unknown_agent(tmp_path, monkeypatch) -> None:
    project_root = tmp_path / 'repo-supervisor-invalid-extra-runtime'
    (project_root / '.cc-bridge').mkdir(parents=True, exist_ok=True)
    (project_root / '.cc-bridge' / 'cc_bridge.config').write_text('demo:codex\n', encoding='utf-8')
    project = bootstrap_project(project_root)
    paths = PathLayout(project_root)
    invalid_runtime = paths.agent_runtime_path('legacy')
    invalid_runtime.parent.mkdir(parents=True, exist_ok=True)
    invalid_runtime.write_text('{"agent_name":"legacy"}\n', encoding='utf-8')

    seen: list[str] = []

    class FakeRegistry:
        def list_known_agents(self):
            return ('demo',)

        def get(self, agent_name: str):
            seen.append(agent_name)
            if agent_name == 'legacy':
                raise AssertionError('unknown extra agent dir should not use registry.get')
            return None

        def upsert(self, runtime):
            raise AssertionError(f'unexpected upsert for {runtime.agent_name}')

    monkeypatch.setattr('cc_bridge_daemon.supervisor.cleanup_project_tmux_orphans_by_socket', lambda **kwargs: ())
    monkeypatch.setattr(
        'cc_bridge_daemon.supervisor.TmuxCleanupHistoryStore',
        lambda paths: type('Store', (), {'append': staticmethod(lambda event: None)})(),
    )

    supervisor = RuntimeSupervisor(
        project_root=project_root,
        project_id=project.project_id,
        paths=paths,
        config=load_project_config(project_root).config,
        registry=FakeRegistry(),
        runtime_service=None,
    )

    execution = supervisor.stop_all(force=True)

    assert execution.summary.state == 'unmounted'
    assert seen == ['demo']

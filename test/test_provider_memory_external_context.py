from __future__ import annotations

import os
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get('CC_BRIDGE_REAL_PROJECT_MEMORY_CHECK') != '1',
    reason='set CC_BRIDGE_REAL_PROJECT_MEMORY_CHECK=1 to inspect an external CC_BRIDGE test project',
)


SOURCE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REAL_PROJECT = Path('/home/bfly/yunwei/test_ccb2')


def test_external_project_managed_memory_context_has_expected_source_ownership() -> None:
    project_root = Path(os.environ.get('CC_BRIDGE_REAL_TEST_PROJECT') or DEFAULT_REAL_PROJECT).expanduser().resolve()
    if not project_root.exists():
        pytest.skip(f'external CC_BRIDGE test project does not exist: {project_root}')
    if project_root == SOURCE_ROOT.resolve():
        pytest.fail('external context check must not target cc_bridge_source itself')
    if not (project_root / '.cc-bridge').is_dir():
        pytest.skip(f'external CC_BRIDGE test project has no .cc-bridge directory: {project_root}')

    memory_files = _managed_memory_files(project_root)
    if not memory_files:
        pytest.skip(f'no generated managed provider memory files under {project_root / ".cc-bridge"}')

    shared_memory = _read_source(project_root / '.cc-bridge' / 'cc_bridge_memory.md')
    project_agents = _read_source(project_root / 'AGENTS.md')
    project_claude = _read_source(project_root / 'CLAUDE.md')
    project_gemini = _read_source(project_root / 'GEMINI.md')

    inspected = 0
    for path in memory_files:
        text = path.read_text(encoding='utf-8')
        if '# CC_BRIDGE Managed Agent Memory' not in text:
            continue
        inspected += 1
        provider = _provider_from_bundle(text)

        assert text.count('## CC_BRIDGE Runtime Coordination Rules') == 1, str(path)
        assert text.count('command ask "$TARGET"') == 1, str(path)
        _assert_contains_source(text, shared_memory, path, '.cc-bridge/cc_bridge_memory.md')

        if provider == 'claude':
            _assert_not_contains_source(text, project_claude, path, 'project CLAUDE.md')
        elif provider in {'codex', 'opencode'}:
            _assert_not_contains_source(text, project_agents, path, 'project AGENTS.md')
        elif provider == 'gemini':
            _assert_contains_source(text, project_gemini, path, 'project GEMINI.md')

    assert inspected > 0, f'no CC_BRIDGE managed memory bundles found in {len(memory_files)} candidate files'


def _managed_memory_files(project_root: Path) -> list[Path]:
    cc_bridge_root = project_root / '.cc-bridge'
    files = [
        *cc_bridge_root.glob('agents/*/provider-state/claude/home/.claude/CLAUDE.md'),
        *cc_bridge_root.glob('agents/*/provider-state/codex/home/AGENTS.md'),
        *cc_bridge_root.glob('runtime/memory/*.md'),
    ]
    return sorted(set(files))


def _provider_from_bundle(text: str) -> str:
    for line in text.splitlines():
        if line.startswith('provider:'):
            return line.split(':', 1)[1].strip().lower()
    return ''


def _read_source(path: Path) -> str:
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return ''
    return text.strip()


def _assert_contains_source(text: str, source: str, path: Path, label: str) -> None:
    if len(source) < 16:
        return
    assert source in text, f'{path} does not include expected {label} content'


def _assert_not_contains_source(text: str, source: str, path: Path, label: str) -> None:
    if len(source) < 16:
        return
    assert source not in text, f'{path} unexpectedly includes full {label} content'

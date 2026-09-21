"""M3 Test 1: store.py save/load roundtrip with B1 plan A+C compatibility.

The B1 fix touches AgentSpec persistence:
  - to_record() writes BOTH 'restore' and 'restore_default' keys (plan C)
  - to_record() writes BOTH 'permission' and 'permission_default' keys (plan C)
  - _agent_spec_from_record prefers 'restore' over 'restore_default' if both
    present, otherwise falls back to whichever exists (plan A)
  - Same for 'permission' / 'permission_default'

This test pins:
  - new-format record loads (with both keys → uses new key)
  - legacy-format record loads (with old keys only → uses old keys)
  - save → load roundtrip preserves values
  - record missing schema_version or record_type raises ValueError
    (NOT KeyError as I originally claimed in this test's docstring)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.models import (
    AgentApiSpec,
    AgentSpec,
    PermissionMode,
    QueuePolicy,
    RestoreMode,
    RuntimeMode,
    WorkspaceMode,
)
from agents.store import (
    SCHEMA_VERSION,
    AgentSpecStore,
)
from storage.paths import PathLayout


@pytest.fixture
def layout(tmp_path: Path) -> PathLayout:
    return PathLayout(tmp_path / 'repo')


@pytest.fixture
def spec() -> AgentSpec:
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
        model='gpt-5',
        api=AgentApiSpec(key='sk-store', url='https://api.store.example.test/v1'),
        branch_template='cc_bridge/{agent_name}',
    )


def test_save_load_roundtrip_new_keys(layout: PathLayout, spec: AgentSpec) -> None:
    """Save a spec and load it back — both old and new keys persisted, load works."""
    store = AgentSpecStore(layout=layout)
    store.save(spec)
    loaded = store.load(spec.name)
    assert loaded is not None
    assert loaded.restore_default == RestoreMode.AUTO
    assert loaded.permission_default == PermissionMode.MANUAL


def test_to_record_writes_both_keys(spec: AgentSpec) -> None:
    """to_record() double-writes both old and new key formats (plan C)."""
    record = spec.to_record()
    assert 'restore' in record
    assert 'restore_default' in record
    assert record['restore'] == 'auto'
    assert record['restore_default'] == 'auto'
    assert 'permission' in record
    assert 'permission_default' in record
    assert record['permission'] == 'manual'
    assert record['permission_default'] == 'manual'


def test_load_legacy_format_record(layout: PathLayout) -> None:
    """A record with only old key format ('restore_default'/'permission_default')
    should still load via the tolerant reader (plan A)."""
    legacy_record = {
        'schema_version': SCHEMA_VERSION,
        'record_type': 'agent_spec',
        'name': 'legacy',
        'provider': 'codex',
        'target': '.',
        'workspace_mode': 'git-worktree',
        'runtime_mode': 'pane-backed',
        'restore_default': 'fresh',
        'permission_default': 'manual',
        'queue_policy': 'serial-per-agent',
        'api': {},
        'provider_profile': {},
    }
    spec_path = layout.agent_spec_path('legacy')
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(legacy_record))
    store = AgentSpecStore(layout=layout)
    loaded = store.load('legacy')
    assert loaded is not None
    assert loaded.restore_default == RestoreMode.FRESH
    assert loaded.permission_default == PermissionMode.MANUAL


def test_load_mixed_record_prefers_new_key(layout: PathLayout) -> None:
    """When both keys are present, the new ('restore'/'permission') key wins.
    This matches what to_record() writes and what fresh readers expect."""
    mixed_record = {
        'schema_version': SCHEMA_VERSION,
        'record_type': 'agent_spec',
        'name': 'mixed',
        'provider': 'codex',
        'target': '.',
        'workspace_mode': 'git-worktree',
        'runtime_mode': 'pane-backed',
        'restore': 'auto',
        'restore_default': 'fresh',
        'permission': 'manual',
        'permission_default': 'readonly',
        'queue_policy': 'serial-per-agent',
        'api': {},
        'provider_profile': {},
    }
    spec_path = layout.agent_spec_path('mixed')
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(mixed_record))
    store = AgentSpecStore(layout=layout)
    loaded = store.load('mixed')
    assert loaded is not None
    assert loaded.restore_default == RestoreMode.AUTO  # 'restore' wins
    assert loaded.permission_default == PermissionMode.MANUAL


def test_record_missing_schema_version_raises_valueerror(layout: PathLayout) -> None:
    """A record missing schema_version is rejected by _validate_record
    with ValueError (not KeyError). This pin protects against silent acceptance
    of unsupported record formats."""
    malformed = {
        'record_type': 'agent_spec',
        'name': 'malformed',
        'provider': 'codex',
        'target': '.',
        'workspace_mode': 'git-worktree',
        'runtime_mode': 'pane-backed',
        'restore': 'auto',
        'restore_default': 'auto',
        'permission': 'manual',
        'permission_default': 'manual',
        'queue_policy': 'serial-per-agent',
        'api': {},
        'provider_profile': {},
    }
    spec_path = layout.agent_spec_path('malformed')
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(malformed))
    store = AgentSpecStore(layout=layout)
    with pytest.raises(ValueError, match='schema_version'):
        store.load('malformed')


def test_record_missing_record_type_raises_valueerror(layout: PathLayout) -> None:
    """A record missing record_type is rejected — prevents spec/runtime confusion."""
    malformed = {
        'schema_version': SCHEMA_VERSION,
        'name': 'malformed2',
        'provider': 'codex',
        'target': '.',
        'workspace_mode': 'git-worktree',
        'runtime_mode': 'pane-backed',
        'restore': 'auto',
        'restore_default': 'auto',
        'permission': 'manual',
        'permission_default': 'manual',
        'queue_policy': 'serial-per-agent',
        'api': {},
        'provider_profile': {},
    }
    spec_path = layout.agent_spec_path('malformed2')
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(malformed))
    store = AgentSpecStore(layout=layout)
    with pytest.raises(ValueError, match='record_type'):
        store.load('malformed2')

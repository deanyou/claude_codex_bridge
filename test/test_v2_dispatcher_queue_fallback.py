"""M3 Test 3: queue dispatcher fallback path — pins M5 contract.

Pins the contract established by the B2 fix in queue.py:start_next_queued_job:

    if not is_headless:
        mb_result = _start_agent_mailbox_job(dispatcher, slot)
        if mb_result is not None:
            return mb_result
    # Headless path: bypass mailbox, pop job directly from queue
    job_id = dispatcher._state.pop_next_for(slot.target_kind, slot.target_name)

This means:
  - headless agents NEVER call mailbox (always pop directly)
  - non-headless agents call mailbox first
  - if mailbox returns None (couldn't claim), BOTH headless and non-headless
    fall through to dispatcher._state.pop_next_for(...)

The M5 risk flagged in the review was that this fall-through could cause
double-start if mailbox silently claimed a job but didn't return it. This
test pins the actual behavior (fall-through is unconditional after mailbox
returns None) and asserts the dispatcher calls pop_next_for even when
mailbox fails — so any future change must update this test intentionally.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cc_bridge_daemon.api_models import TargetKind

from agents.models import (
    AgentApiSpec,
    AgentSpec,
    PermissionMode,
    QueuePolicy,
    RestoreMode,
    RuntimeMode,
    WorkspaceMode,
)


def _make_spec(provider: str, runtime_mode: RuntimeMode) -> AgentSpec:
    return AgentSpec(
        name=provider,
        provider=provider,
        target='.',
        workspace_mode=WorkspaceMode.GIT_WORKTREE,
        workspace_root=None,
        runtime_mode=runtime_mode,
        restore_default=RestoreMode.AUTO,
        permission_default=PermissionMode.MANUAL,
        queue_policy=QueuePolicy.SERIAL_PER_AGENT,
        model=None,
        api=AgentApiSpec(key='k', url='u'),
        branch_template='cc/{agent_name}',
    )


def _make_dispatcher(spec: AgentSpec) -> MagicMock:
    """Build a minimal dispatcher mock where spec_for(name) returns the spec."""
    dispatcher = MagicMock()
    dispatcher._registry = MagicMock()
    dispatcher._registry.spec_for.return_value = spec
    dispatcher._state.pop_next_for.return_value = None
    dispatcher._state.active_job.return_value = None
    dispatcher._execution_service = MagicMock()
    dispatcher._message_bureau = MagicMock()
    dispatcher._snapshot_writer = MagicMock()
    return dispatcher


def test_is_headless_helper_returns_true_for_headless_spec() -> None:
    """B2 sanity check: _is_headless_agent returns True for HEADLESS spec."""
    from cc_bridge_daemon.services.dispatcher_runtime.lifecycle_start_runtime.recovery_runtime.slots import (
        _is_headless_agent,
    )

    dispatcher = _make_dispatcher(_make_spec('peri', RuntimeMode.HEADLESS))
    assert _is_headless_agent(dispatcher, 'peri') is True


def test_is_headless_helper_returns_false_for_pane_backed_spec() -> None:
    """B2 sanity check: _is_headless_agent returns False for PANE_BACKED spec."""
    from cc_bridge_daemon.services.dispatcher_runtime.lifecycle_start_runtime.recovery_runtime.slots import (
        _is_headless_agent,
    )

    dispatcher = _make_dispatcher(_make_spec('codex', RuntimeMode.PANE_BACKED))
    assert _is_headless_agent(dispatcher, 'codex') is False


def test_is_headless_helper_returns_false_for_missing_spec() -> None:
    """Defensive: missing spec returns False (no crash)."""
    from cc_bridge_daemon.services.dispatcher_runtime.lifecycle_start_runtime.recovery_runtime.slots import (
        _is_headless_agent,
    )

    dispatcher = MagicMock()
    dispatcher._registry = MagicMock()
    dispatcher._registry.spec_for.side_effect = KeyError('not found')
    assert _is_headless_agent(dispatcher, 'missing') is False


def test_headless_agent_bypasses_mailbox_and_pops_directly() -> None:
    """Headless spec: mailbox is NEVER called; pop_next_for IS called.

    Pins the contract: the `if not is_headless` guard in queue.py skips
    mailbox entirely for headless agents. This is the new behavior introduced
    by B2 — if mailbox gets called for a headless agent, that's a regression.
    """
    from cc_bridge_daemon.services.dispatcher_runtime.lifecycle_start_runtime.queue import (
        _start_agent_mailbox_job,
        start_next_queued_job,
    )

    spec = _make_spec('peri', RuntimeMode.HEADLESS)
    dispatcher = _make_dispatcher(spec)
    dispatcher._state.pop_next_for.return_value = 'job_xyz'

    slot = MagicMock(target_kind=TargetKind.AGENT, target_name='peri')

    with patch.object(
        __import__('cc_bridge_daemon.services.dispatcher_runtime.lifecycle_start_runtime.queue',
                   fromlist=['_start_agent_mailbox_job']),
        '_start_agent_mailbox_job',
    ) as mock_mb:
        with patch(
            'cc_bridge_daemon.services.dispatcher_runtime.lifecycle_start_runtime.queue.get_job',
            return_value=None,
        ):
            start_next_queued_job(dispatcher, slot)

    # Headless must NOT call mailbox
    assert mock_mb.call_count == 0, (
        'headless agent must skip mailbox entirely'
    )
    # But pop_next_for MUST be called (fall-through path)
    assert dispatcher._state.pop_next_for.call_count == 1


def test_non_headless_calls_mailbox_then_falls_through_to_pop() -> None:
    """Non-headless spec: mailbox IS called; if mailbox returns None, fall through to pop.

    Pins the M5 contract: when mailbox fails to claim, dispatcher still
    attempts to pop_next_for. This is the actual behavior on this branch.
    A future fix to suppress the fall-through must update this test.
    """
    from cc_bridge_daemon.services.dispatcher_runtime.lifecycle_start_runtime.queue import (
        start_next_queued_job,
    )

    spec = _make_spec('codex', RuntimeMode.PANE_BACKED)
    dispatcher = _make_dispatcher(spec)
    dispatcher._state.pop_next_for.return_value = 'job_abc'

    slot = MagicMock(target_kind=TargetKind.AGENT, target_name='codex')

    with patch(
        'cc_bridge_daemon.services.dispatcher_runtime.lifecycle_start_runtime.queue._start_agent_mailbox_job',
        return_value=None,
    ) as mock_mb:
        with patch(
            'cc_bridge_daemon.services.dispatcher_runtime.lifecycle_start_runtime.queue.get_job',
            return_value=None,
        ):
            start_next_queued_job(dispatcher, slot)

    # Mailbox MUST be called for non-headless
    assert mock_mb.call_count == 1, (
        'non-headless agent must attempt mailbox first'
    )
    # pop_next_for IS also called (fall-through after mailbox=None)
    assert dispatcher._state.pop_next_for.call_count == 1, (
        'non-headless with mailbox=None must still fall through to pop_next_for '
        '(this is the M5 risk pinned by this test)'
    )


def test_non_headless_returns_early_when_mailbox_succeeds() -> None:
    """Non-headless spec: when mailbox claims a job, pop_next_for is NOT called.

    Pins the positive case: mailbox claim → early return → no double-pop.
    """
    from cc_bridge_daemon.services.dispatcher_runtime.lifecycle_start_runtime.queue import (
        start_next_queued_job,
    )

    spec = _make_spec('codex', RuntimeMode.PANE_BACKED)
    dispatcher = _make_dispatcher(spec)

    slot = MagicMock(target_kind=TargetKind.AGENT, target_name='codex')

    mailbox_result = MagicMock(name='mailbox_claim')

    with patch(
        'cc_bridge_daemon.services.dispatcher_runtime.lifecycle_start_runtime.queue._start_agent_mailbox_job',
        return_value=mailbox_result,
    ):
        result = start_next_queued_job(dispatcher, slot)

    # pop_next_for MUST NOT be called when mailbox returns a claim
    assert dispatcher._state.pop_next_for.call_count == 0, (
        'mailbox success must short-circuit before pop_next_for'
    )
    # Result is whatever mailbox returned
    assert result is mailbox_result

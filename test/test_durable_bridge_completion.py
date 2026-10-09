"""durable-bridge completion 映射（v4 09 节规格表）测试。"""

from __future__ import annotations

import pytest

from durable_bridge.completion import (
    CompletionDecision,
    CompletionStatus,
    is_intermediate_or_unfinished,
    map_worker_outcome,
)


# ---- 5 种 outcome 映射 ----


@pytest.mark.parametrize(
    'outcome,reply,expected_status,expected_reason,expected_kind',
    [
        # stop + 非空 reply → COMPLETED
        ('stop', 'final answer', CompletionStatus.COMPLETED, 'pi_run_stop', 'final'),
        # error → FAILED
        ('error', None, CompletionStatus.FAILED, 'pi_run_error', 'error'),
        # stop + 空 reply → INCOMPLETE
        ('stop', '', CompletionStatus.INCOMPLETE, 'pi_empty_reply', 'incomplete'),
        # 缺 outcome → INCOMPLETE
        (None, None, CompletionStatus.INCOMPLETE, 'pi_native_outcome_missing', 'inconclusive'),
        # 其他 outcome → INCOMPLETE
        (
            'withdrawn', None,
            CompletionStatus.INCOMPLETE, 'pi_run_finished:withdrawn', 'inconclusive',
        ),
        (
            'stale', None,
            CompletionStatus.INCOMPLETE, 'pi_run_finished:stale', 'inconclusive',
        ),
        # whitespace-only reply 视作空
        ('stop', '   \n  ', CompletionStatus.INCOMPLETE, 'pi_empty_reply', 'incomplete'),
    ],
)
def test_map_worker_outcome(
    outcome, reply, expected_status, expected_reason, expected_kind
):
    decision = map_worker_outcome(outcome=outcome, reply=reply)
    assert isinstance(decision, CompletionDecision)
    assert decision.status is expected_status
    assert decision.reason == expected_reason
    assert decision.result_kind == expected_kind


def test_completion_decision_to_record():
    decision = map_worker_outcome(outcome='stop', reply='ok')
    blob = decision.to_record()
    assert blob['status'] == 'completed'
    assert blob['reason'] == 'pi_run_stop'
    assert blob['result_kind'] == 'final'


# ---- 中间态判定 ----


def test_intermediate_when_pending_tool_call():
    assert is_intermediate_or_unfinished(
        has_pending_tool_call=True,
        in_queue_or_pending=False,
        bridge_epoch_expired=False,
    ) is True


def test_intermediate_when_in_queue():
    assert is_intermediate_or_unfinished(
        has_pending_tool_call=False,
        in_queue_or_pending=True,
        bridge_epoch_expired=False,
    ) is True


def test_intermediate_when_bridge_epoch_expired():
    assert is_intermediate_or_unfinished(
        has_pending_tool_call=False,
        in_queue_or_pending=False,
        bridge_epoch_expired=True,
    ) is True


def test_not_intermediate_when_clean_finish():
    """clean 终态：stop + reply + no pending + no expired → 不算中间态。"""
    assert is_intermediate_or_unfinished(
        has_pending_tool_call=False,
        in_queue_or_pending=False,
        bridge_epoch_expired=False,
    ) is False

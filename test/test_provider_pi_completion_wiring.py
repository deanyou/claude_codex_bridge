"""round 01 接线测试：``map_worker_outcome`` + ``DurableDispatcher.report_result`` 接入 Pi provider 终态。

覆盖：
- 5 种 outcome 各自命中 ``decision.status`` / ``decision.reason`` / ``decision.result_kind``
- ``reply`` 进入 ``result_payload``
- ``dispatcher.report_result`` 异常被吞进 ``state['wiring_errors']``，主结果保留
- ``state`` 无 dispatcher 时退化为原行为（不调 report_result，不抛异常）
- ``RESULT_DELIVERED`` 成功 → 持久化 outcome 不记 wiring_errors
- ``RESULT_CONFLICT`` / ``LEDGER_CONFLICT`` / ``ALREADY_TERMINAL`` → 记 wiring_errors
  + 标记 ``state['dispatch_recovery_required'] = True``
- ``_reply_delivery_result`` 不再调用 ``report_result``，只记录 transport sent 标记

设计原则：
- ``report_result`` 返回 ``DispatchResult``：测试用 ``MagicMock(return_value=...)``
  注入真实 ``DispatchResult(outcome=..., binding=..., detail=...)``
- 直接调用模块级 ``_settled_result`` / ``_reply_delivery_result`` /
  ``_wire_dispatcher_report_result``，避开适配器初始化路径
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from completion.models import (
    CompletionConfidence,
    CompletionSourceKind,
    CompletionStatus,
)
from provider_backends.pi.pane_events import PiAssistantSnapshot
from provider_backends.pi.pane_execution import (
    _reply_delivery_result,
    _settled_result,
    _wire_dispatcher_report_result,
)
from provider_execution.base import ProviderSubmission
from durable_bridge.binding_ledger import BindingRecord
from durable_bridge.completion import CompletionStatus as DurableCompletionStatus
from durable_bridge.dispatcher import DispatchOutcome, DispatchResult


# ---- helpers ----


def _submission(runtime_state: dict[str, object] | None = None) -> ProviderSubmission:
    state = dict(runtime_state or {})
    state.setdefault("mode", "pi_pane")
    state.setdefault("provider", "pi")
    state.setdefault("session_field_prefix", "pi")
    state.setdefault("terminal_authority", "pi_extension_agent_settled")
    state.setdefault("anchor_seen", True)
    state.setdefault("request_anchor", "req_test_001")
    state.setdefault("provider_turn_ref", "turn_test_001")
    state.setdefault("next_seq", 1)
    state.setdefault("prompt_sent", True)
    return ProviderSubmission(
        job_id="job_wiring_1",
        agent_name="agent_wiring",
        provider="pi",
        accepted_at="2026-10-09T00:00:00Z",
        ready_at="2026-10-09T00:00:00Z",
        source_kind=CompletionSourceKind.SESSION_EVENT_LOG,
        reply="",
        diagnostics={"provider": "pi", "mode": "pi_pane"},
        runtime_state=state,
    )


def _snapshot(
    *,
    text: str = "",
    stop_reason: str = "stop",
    error: str = "",
    response_id: str = "resp_1",
) -> PiAssistantSnapshot:
    return PiAssistantSnapshot(
        text=text,
        stop_reason=stop_reason,
        error=error,
        response_id=response_id,
        timestamp=None,
    )


def _make_state(*, dispatcher: Any = None, binding_id: str = "") -> dict[str, object]:
    state: dict[str, object] = {}
    if dispatcher is not None:
        state["dispatcher"] = dispatcher
    if binding_id:
        state["binding_id"] = binding_id
    return state


def _fake_binding(delivery_phase: str = "submitted") -> BindingRecord:
    """构造一个最小 BindingRecord，仅用于 DispatchResult.binding 字段。"""
    return BindingRecord(
        schema_version=2,
        binding_id="bdg_test",
        inbound_event_id="evt_test",
        message_id="msg_test",
        attempt_id="att_test",
        request_id="req_test",
        input_hash="hash_test",
        storage_path="/tmp/x",
        bridge_epoch="epoch_test",
        delivery_phase=delivery_phase,
        conversation_id=None,
        submission_id=None,
        result_id=None,
        result_kind=None,
        result_payload_hash=None,
        result_payload_ref=None,
    )


def _delivered_result(detail: str | None = None) -> DispatchResult:
    return DispatchResult(
        outcome=DispatchOutcome.RESULT_DELIVERED,
        binding=_fake_binding(delivery_phase="delivered"),
        submission_id="sub_test",
        conversation_id="conv_test",
        detail=detail,
    )


def _conflict_result(
    *,
    outcome: DispatchOutcome = DispatchOutcome.RESULT_CONFLICT,
    detail: str = "ledger conflict",
    phase: str = "submitted",
) -> DispatchResult:
    return DispatchResult(
        outcome=outcome,
        binding=_fake_binding(delivery_phase=phase),
        detail=detail,
    )


def _dispatcher_returning(result: DispatchResult | None = None, **side_effect: Any) -> MagicMock:
    """构造一个会返回 ``result`` 的 dispatcher mock。

    ``side_effect`` 例外优先；若 ``result is None`` 则用 ``MagicMock()`` 默认返回值。
    """
    mock = MagicMock(name="DurableDispatcher")
    if result is not None:
        mock.report_result.return_value = result
    for attr, value in side_effect.items():
        setattr(mock.report_result, attr, value)
    return mock


# ---- 5 种 outcome 各自命中 decision.status/reason/result_kind（成功路径）----


def test_settled_stop_with_reply_calls_report_result_with_final_kind() -> None:
    """outcome='stop' + 非空 reply → COMPLETED / pi_run_stop / final + RESULT_DELIVERED。"""
    dispatcher = _dispatcher_returning(_delivered_result())
    state = _make_state(dispatcher=dispatcher, binding_id="bdg_stop_ok")
    submission = _submission(state)

    result = _settled_result(
        submission,
        state,
        _snapshot(text="hello world", stop_reason="stop"),
        items=[],
        now="2026-10-09T00:00:01Z",
    )

    assert state["last_completion_status"] == "completed"
    assert state["last_completion_reason"] == "pi_run_stop"
    assert state["last_result_kind"] == "final"
    assert state["last_dispatch_outcome"] == "result_delivered"
    assert state["dispatch_recovery_required"] is False
    dispatcher.report_result.assert_called_once()
    kwargs = dispatcher.report_result.call_args.kwargs
    assert kwargs["binding_id"] == "bdg_stop_ok"
    assert kwargs["result_kind"] == "final"
    assert kwargs["result_payload"]["reply"] == "hello world"
    assert kwargs["result_payload"]["finish_reason"] == "stop"
    assert "wiring_errors" not in state
    # 主结果保留：本地 _settled_result 仍然按既有契约给 COMPLETED
    assert result.decision is not None
    assert result.decision.status is CompletionStatus.COMPLETED


def test_settled_error_calls_report_result_with_error_kind() -> None:
    """outcome='error' → FAILED / pi_run_error / error。"""
    dispatcher = _dispatcher_returning(_delivered_result())
    state = _make_state(dispatcher=dispatcher, binding_id="bdg_err")
    submission = _submission(state)

    result = _settled_result(
        submission,
        state,
        _snapshot(text="", stop_reason="error", error="boom"),
        items=[],
        now="2026-10-09T00:00:01Z",
    )

    assert state["last_completion_status"] == "failed"
    assert state["last_completion_reason"] == "pi_run_error"
    assert state["last_result_kind"] == "error"
    assert state["last_dispatch_outcome"] == "result_delivered"
    assert state["dispatch_recovery_required"] is False
    dispatcher.report_result.assert_called_once()
    kwargs = dispatcher.report_result.call_args.kwargs
    assert kwargs["binding_id"] == "bdg_err"
    assert kwargs["result_kind"] == "error"
    assert kwargs["result_payload"]["finish_reason"] == "error"
    assert kwargs["result_payload"]["error"] == "boom"
    assert "wiring_errors" not in state
    assert result.decision is not None
    assert result.decision.status is CompletionStatus.FAILED


def test_settled_stop_empty_reply_calls_report_result_with_incomplete_kind() -> None:
    """outcome='stop' + 空 reply → INCOMPLETE / pi_empty_reply / incomplete。"""
    dispatcher = _dispatcher_returning(_delivered_result())
    state = _make_state(dispatcher=dispatcher, binding_id="bdg_empty")
    submission = _submission(state)

    result = _settled_result(
        submission,
        state,
        _snapshot(text="", stop_reason="stop"),
        items=[],
        now="2026-10-09T00:00:01Z",
    )

    assert state["last_completion_status"] == "incomplete"
    assert state["last_completion_reason"] == "pi_empty_reply"
    assert state["last_result_kind"] == "incomplete"
    assert state["last_dispatch_outcome"] == "result_delivered"
    dispatcher.report_result.assert_called_once()
    kwargs = dispatcher.report_result.call_args.kwargs
    assert kwargs["result_kind"] == "incomplete"
    assert "wiring_errors" not in state
    assert result.decision is not None
    assert result.decision.status is CompletionStatus.INCOMPLETE


def test_settled_missing_outcome_calls_report_result_with_inconclusive_kind() -> None:
    """outcome 缺失 → INCOMPLETE / pi_native_outcome_missing / inconclusive。"""
    dispatcher = _dispatcher_returning(_delivered_result())
    state = _make_state(dispatcher=dispatcher, binding_id="bdg_no_outcome")
    submission = _submission(state)

    _settled_result(
        submission,
        state,
        _snapshot(text="anything", stop_reason=""),
        items=[],
        now="2026-10-09T00:00:01Z",
    )

    assert state["last_completion_status"] == "incomplete"
    assert state["last_completion_reason"] == "pi_native_outcome_missing"
    assert state["last_result_kind"] == "inconclusive"
    assert state["last_dispatch_outcome"] == "result_delivered"
    dispatcher.report_result.assert_called_once()
    kwargs = dispatcher.report_result.call_args.kwargs
    assert kwargs["result_kind"] == "inconclusive"
    assert "wiring_errors" not in state


def test_settled_other_outcome_calls_report_result_with_inconclusive_kind() -> None:
    """outcome='withdrawn' 等 → INCOMPLETE / pi_run_finished:withdrawn / inconclusive。"""
    dispatcher = _dispatcher_returning(_delivered_result())
    state = _make_state(dispatcher=dispatcher, binding_id="bdg_withdrawn")
    submission = _submission(state)

    _settled_result(
        submission,
        state,
        _snapshot(text="x", stop_reason="withdrawn"),
        items=[],
        now="2026-10-09T00:00:01Z",
    )

    assert state["last_completion_status"] == "incomplete"
    assert state["last_completion_reason"] == "pi_run_finished:withdrawn"
    assert state["last_result_kind"] == "inconclusive"
    assert state["last_dispatch_outcome"] == "result_delivered"
    dispatcher.report_result.assert_called_once()
    kwargs = dispatcher.report_result.call_args.kwargs
    assert kwargs["result_kind"] == "inconclusive"


# ---- 交付失败（RESULT_CONFLICT / LEDGER_CONFLICT / ALREADY_TERMINAL）记账 ----


def test_settled_result_conflict_is_logged_as_wiring_error() -> None:
    """``report_result`` 返回 ``RESULT_CONFLICT`` → 记 wiring_errors + recovery_required=True。"""
    dispatcher = _dispatcher_returning(
        _conflict_result(
            outcome=DispatchOutcome.RESULT_CONFLICT,
            detail="mailbox event status is 'abandoned'",
        )
    )
    state = _make_state(dispatcher=dispatcher, binding_id="bdg_conflict")
    submission = _submission(state)

    result = _settled_result(
        submission,
        state,
        _snapshot(text="hi", stop_reason="stop"),
        items=[],
        now="2026-10-09T00:00:01Z",
    )

    # 主结果保留（model 端 COMPLETED），但交付层有冲突需对账
    assert result.decision is not None
    assert result.decision.status is CompletionStatus.COMPLETED
    assert result.decision.reply == "hi"

    # 交付结果状态
    assert state["last_dispatch_outcome"] == "result_conflict"
    assert "abandoned" in (state["last_dispatch_detail"] or "")
    assert state["dispatch_recovery_required"] is True

    # wiring_errors 应记录
    assert state.get("wiring_errors"), "RESULT_CONFLICT 应该有 wiring_errors"
    record = state["wiring_errors"][0]
    assert record["where"] == "report_result"
    assert record["kind"] == "non_delivered_outcome"
    assert record["outcome"] == "result_conflict"
    assert "result_conflict" in record["error"]


def test_settled_ledger_conflict_is_logged_as_wiring_error() -> None:
    """``LEDGER_CONFLICT``（phase 非 submitted/result_pending）同样记账。"""
    dispatcher = _dispatcher_returning(
        _conflict_result(
            outcome=DispatchOutcome.LEDGER_CONFLICT,
            detail="cannot report result in phase 'abandoned'",
            phase="abandoned",
        )
    )
    state = _make_state(dispatcher=dispatcher, binding_id="bdg_lc")
    submission = _submission(state)

    result = _settled_result(
        submission,
        state,
        _snapshot(text="ok", stop_reason="stop"),
        items=[],
        now="2026-10-09T00:00:01Z",
    )

    assert result.decision is not None
    assert result.decision.status is CompletionStatus.COMPLETED
    assert state["last_dispatch_outcome"] == "ledger_conflict"
    assert state["dispatch_recovery_required"] is True
    assert state.get("wiring_errors"), "LEDGER_CONFLICT 应该有 wiring_errors"
    record = state["wiring_errors"][0]
    assert record["outcome"] == "ledger_conflict"


def test_settled_already_terminal_is_logged_as_wiring_error() -> None:
    """``ALREADY_TERMINAL``（已 abandoned/delivered 的 binding）同样记账。"""
    dispatcher = _dispatcher_returning(
        _conflict_result(
            outcome=DispatchOutcome.ALREADY_TERMINAL,
            detail="binding already abandoned",
        )
    )
    state = _make_state(dispatcher=dispatcher, binding_id="bdg_terminal")
    submission = _submission(state)

    result = _settled_result(
        submission,
        state,
        _snapshot(text="ok", stop_reason="stop"),
        items=[],
        now="2026-10-09T00:00:01Z",
    )

    assert result.decision is not None
    assert result.decision.status is CompletionStatus.COMPLETED
    assert state["last_dispatch_outcome"] == "already_terminal"
    assert state["dispatch_recovery_required"] is True
    assert state.get("wiring_errors")
    record = state["wiring_errors"][0]
    assert record["outcome"] == "already_terminal"


def test_settled_recovery_required_resets_after_delivered() -> None:
    """连续两次：先 conflict 后 delivered → ``dispatch_recovery_required`` 重置 False。"""
    dispatcher = _dispatcher_returning(
        _conflict_result(outcome=DispatchOutcome.RESULT_CONFLICT)
    )
    state = _make_state(dispatcher=dispatcher, binding_id="bdg_reset")
    submission = _submission(state)

    _settled_result(
        submission,
        state,
        _snapshot(text="x", stop_reason="stop"),
        items=[],
        now="2026-10-09T00:00:01Z",
    )
    assert state["dispatch_recovery_required"] is True

    # 第二次返回 delivered
    dispatcher.report_result.return_value = _delivered_result()
    _settled_result(
        submission,
        state,
        _snapshot(text="y", stop_reason="stop"),
        items=[],
        now="2026-10-09T00:00:02Z",
    )
    assert state["dispatch_recovery_required"] is False
    assert state["last_dispatch_outcome"] == "result_delivered"


# ---- dispatcher 异常吞进 state['wiring_errors']，主结果保留 ----


def test_settled_dispatcher_exception_is_swallowed_and_main_result_preserved() -> None:
    """``report_result`` 抛异常 → 写入 ``state['wiring_errors']`` + recovery_required=True，主结果保留。"""
    dispatcher = MagicMock(name="DurableDispatcher")
    dispatcher.report_result.side_effect = RuntimeError("ledger write failed")
    state = _make_state(dispatcher=dispatcher, binding_id="bdg_explode")
    submission = _submission(state)

    result = _settled_result(
        submission,
        state,
        _snapshot(text="hello", stop_reason="stop"),
        items=[],
        now="2026-10-09T00:00:01Z",
    )

    assert state.get("wiring_errors"), "wiring_errors 应该有记录"
    record = state["wiring_errors"][0]
    assert record["where"] == "report_result"
    assert record["kind"] == "exception"
    assert record["outcome"] == "exception"
    assert "RuntimeError" in record["error"]
    assert "ledger write failed" in record["error"]
    assert state["dispatch_recovery_required"] is True

    assert result.decision is not None
    assert result.decision.terminal is True
    assert result.decision.status is CompletionStatus.COMPLETED
    assert result.decision.reply == "hello"
    assert state["last_completion_status"] == "completed"
    # round 02 修复：异常路径必须覆盖 outcome/detail
    assert state["last_dispatch_outcome"] == "exception"
    assert "RuntimeError" in state["last_dispatch_detail"]


def test_settled_dispatcher_exception_overrides_stale_success_in_state() -> None:
    """_settled_result 层面：如果 state 之前有成功 outcome，异常后被覆盖为 'exception'。"""
    dispatcher = MagicMock(name="DurableDispatcher")
    dispatcher.report_result.side_effect = OSError("disk full")
    state = _make_state(dispatcher=dispatcher, binding_id="bdg_stale")
    # 预存陈旧成功状态（模拟上一次提交后状态）
    state["last_dispatch_outcome"] = "result_delivered"
    state["last_dispatch_detail"] = "previous success"
    state["dispatch_recovery_required"] = False
    submission = _submission(state)

    _settled_result(
        submission,
        state,
        _snapshot(text="ok", stop_reason="stop"),
        items=[],
        now="2026-10-09T00:00:01Z",
    )

    # 陈旧成功状态必须被覆盖
    assert state["last_dispatch_outcome"] == "exception"
    assert "OSError" in state["last_dispatch_detail"]
    assert "disk full" in state["last_dispatch_detail"]
    assert state["dispatch_recovery_required"] is True


def test_settled_dispatcher_unknown_return_fails_closed() -> None:
    """_settled_result 层面：dispatcher 返回非 DispatchResult → fail-closed。"""
    dispatcher = MagicMock(name="DurableDispatcher")
    dispatcher.report_result.return_value = "weird future return"  # 非 DispatchResult
    state = _make_state(dispatcher=dispatcher, binding_id="bdg_unknown")
    state["last_dispatch_outcome"] = "result_delivered"  # 陈旧成功
    state["dispatch_recovery_required"] = False
    submission = _submission(state)

    result = _settled_result(
        submission,
        state,
        _snapshot(text="ok", stop_reason="stop"),
        items=[],
        now="2026-10-09T00:00:01Z",
    )

    # 主结果保留
    assert result.decision is not None
    assert result.decision.status is CompletionStatus.COMPLETED
    # 未验证交付成功 → fail-closed
    assert state["last_dispatch_outcome"] == "unknown_return"
    assert state["dispatch_recovery_required"] is True
    assert state["wiring_errors"][0]["kind"] == "unknown_return"
    assert "weird future return" in state["wiring_errors"][0]["error"]


# ---- state 无 dispatcher 时不调用 report_result ----


def test_settled_without_dispatcher_in_state_skips_report_result() -> None:
    """state 无 dispatcher → 不调 report_result，退化为原行为。"""
    state = _make_state(dispatcher=None, binding_id="bdg_orphan")
    submission = _submission(state)

    result = _settled_result(
        submission,
        state,
        _snapshot(text="ok", stop_reason="stop"),
        items=[],
        now="2026-10-09T00:00:01Z",
    )

    assert "wiring_errors" not in state, "无 dispatcher 不该有 wiring_errors"
    assert state["last_completion_status"] == "completed"
    assert state["last_result_kind"] == "final"
    # last_dispatch_outcome / recovery_required 不该写
    assert "last_dispatch_outcome" not in state
    assert result.decision is not None
    assert result.decision.status is CompletionStatus.COMPLETED


def test_settled_without_binding_id_skips_report_result() -> None:
    """state 有 dispatcher 但缺 binding_id → 不调 report_result。"""
    dispatcher = _dispatcher_returning(_delivered_result())
    state = _make_state(dispatcher=dispatcher, binding_id="")
    submission = _submission(state)

    _settled_result(
        submission,
        state,
        _snapshot(text="ok", stop_reason="stop"),
        items=[],
        now="2026-10-09T00:00:01Z",
    )

    dispatcher.report_result.assert_not_called()
    assert "wiring_errors" not in state
    assert "last_dispatch_outcome" not in state
    assert state["last_completion_status"] == "completed"


# ---- reply 进入 result_payload ----


def test_settled_reply_appears_in_result_payload() -> None:
    """``reply`` 作为 ``result_payload['reply']`` 传给 dispatcher。"""
    dispatcher = _dispatcher_returning(_delivered_result())
    state = _make_state(dispatcher=dispatcher, binding_id="bdg_payload")
    submission = _submission(state)

    _settled_result(
        submission,
        state,
        _snapshot(text="cleaned reply text", stop_reason="stop"),
        items=[],
        now="2026-10-09T00:00:01Z",
    )

    dispatcher.report_result.assert_called_once()
    payload = dispatcher.report_result.call_args.kwargs["result_payload"]
    assert payload["reply"] == "cleaned reply text"
    assert payload["finish_reason"] == "stop"
    assert payload["decision"]["status"] == "completed"
    assert payload["decision"]["reason"] == "pi_run_stop"
    assert payload["decision"]["result_kind"] == "final"


# ---- _reply_delivery_result：仅记录 transport sent，不调 report_result ----


def test_reply_delivery_does_not_call_report_result() -> None:
    """``_reply_delivery_result`` 不调 ``report_result``（避免与 worker 终态混淆）。"""
    dispatcher = _dispatcher_returning(_delivered_result())
    state = _make_state(dispatcher=dispatcher, binding_id="bdg_ack")
    submission = _submission(state)

    result = _reply_delivery_result(submission, state, now="2026-10-09T00:00:01Z")

    dispatcher.report_result.assert_not_called()
    # transport sent 标记已写
    assert state["reply_delivery_transport"] == "sent"
    assert state["reply_delivery_transport_sent_at"] == "2026-10-09T00:00:01Z"
    # 不该动 dispatcher outcome
    assert "last_dispatch_outcome" not in state
    # 主结果保留
    assert result.decision is not None
    assert result.decision.status is CompletionStatus.COMPLETED
    assert result.decision.reason == "reply_delivery_sent"


def test_reply_delivery_records_transport_marker_without_dispatcher() -> None:
    """无 dispatcher 也能记录 transport sent（不依赖 dispatcher）。"""
    state = _make_state(dispatcher=None, binding_id="bdg_ack_orphan")
    submission = _submission(state)

    result = _reply_delivery_result(submission, state, now="2026-10-09T00:00:01Z")

    assert state["reply_delivery_transport"] == "sent"
    assert state["reply_delivery_transport_sent_at"] == "2026-10-09T00:00:01Z"
    assert "wiring_errors" not in state
    assert result.decision is not None
    assert result.decision.reason == "reply_delivery_sent"


def test_reply_delivery_does_not_touch_dispatcher_even_if_dispatcher_raises() -> None:
    """dispatcher 抛异常也不该触发（``_reply_delivery_result`` 不调 report_result）。"""
    dispatcher = MagicMock(name="DurableDispatcher")
    dispatcher.report_result.side_effect = ValueError("would explode")
    state = _make_state(dispatcher=dispatcher, binding_id="bdg_ack_explode")
    submission = _submission(state)

    result = _reply_delivery_result(submission, state, now="2026-10-09T00:00:01Z")

    dispatcher.report_result.assert_not_called()
    assert state.get("wiring_errors") is None
    assert state["reply_delivery_transport"] == "sent"
    assert result.decision is not None
    assert result.decision.status is CompletionStatus.COMPLETED


# ---- _wire_dispatcher_report_result helper：直接单测 ----


def test_wire_helper_records_delivered_outcome() -> None:
    """直接调用 helper：RESULT_DELIVERED → outcome 写入，无 wiring_errors。"""
    dispatcher = _dispatcher_returning(_delivered_result(detail="ok"))
    state: dict[str, object] = {"dispatcher": dispatcher}

    _wire_dispatcher_report_result(
        state=state,
        binding_id="bdg_x",
        result_kind="final",
        result_payload={"reply": "hi"},
        error_source="report_result",
    )

    dispatcher.report_result.assert_called_once()
    assert state["last_dispatch_outcome"] == "result_delivered"
    assert state["last_dispatch_detail"] == "ok"
    assert state["dispatch_recovery_required"] is False
    assert "wiring_errors" not in state


def test_wire_helper_records_conflict_and_marks_recovery() -> None:
    """直接调用 helper：RESULT_CONFLICT → outcome + recovery_required=True + wiring_errors。"""
    dispatcher = _dispatcher_returning(
        _conflict_result(
            outcome=DispatchOutcome.RESULT_CONFLICT,
            detail="mailbox returned None",
        )
    )
    state: dict[str, object] = {"dispatcher": dispatcher}

    _wire_dispatcher_report_result(
        state=state,
        binding_id="bdg_x",
        result_kind="final",
        result_payload={"reply": "hi"},
        error_source="report_result",
    )

    assert state["last_dispatch_outcome"] == "result_conflict"
    assert state["last_dispatch_detail"] == "mailbox returned None"
    assert state["dispatch_recovery_required"] is True
    assert state["wiring_errors"][0]["kind"] == "non_delivered_outcome"
    assert state["wiring_errors"][0]["outcome"] == "result_conflict"


def test_wire_helper_records_exception_and_marks_recovery() -> None:
    """直接调用 helper：dispatcher 抛异常 → wiring_errors + recovery_required=True
    + last_dispatch_outcome='exception'（覆盖可能的陈旧成功状态）。
    """
    dispatcher = MagicMock(name="DurableDispatcher")
    dispatcher.report_result.side_effect = KeyError("boom")
    state: dict[str, object] = {"dispatcher": dispatcher}

    _wire_dispatcher_report_result(
        state=state,
        binding_id="bdg_x",
        result_kind="final",
        result_payload={"reply": "hi"},
        error_source="report_result",
    )

    assert state["dispatch_recovery_required"] is True
    assert state["wiring_errors"][0]["kind"] == "exception"
    assert state["wiring_errors"][0]["outcome"] == "exception"
    assert "KeyError" in state["wiring_errors"][0]["error"]
    # round 02 修复：异常路径必须覆盖 outcome/detail，否则陈旧成功状态
    # 会误导恢复逻辑
    assert state["last_dispatch_outcome"] == "exception"
    assert "KeyError" in state["last_dispatch_detail"]
    assert "'boom'" in state["last_dispatch_detail"]


def test_wire_helper_exception_overrides_stale_success_outcome() -> None:
    """如果 state 之前是成功状态，异常后必须被覆盖为 'exception'。"""
    dispatcher = MagicMock(name="DurableDispatcher")
    dispatcher.report_result.side_effect = ValueError("transient")
    state: dict[str, object] = {
        "dispatcher": dispatcher,
        # 预存陈旧成功状态
        "last_dispatch_outcome": "result_delivered",
        "last_dispatch_detail": "previous successful delivery",
        "dispatch_recovery_required": False,
    }

    _wire_dispatcher_report_result(
        state=state,
        binding_id="bdg_x",
        result_kind="final",
        result_payload={"reply": "hi"},
        error_source="report_result",
    )

    assert state["last_dispatch_outcome"] == "exception"
    assert "ValueError" in state["last_dispatch_detail"]
    assert "transient" in state["last_dispatch_detail"]
    assert state["dispatch_recovery_required"] is True
    assert state["wiring_errors"][0]["kind"] == "exception"


def test_wire_helper_unknown_return_fails_closed() -> None:
    """非 ``DispatchResult`` 返回：视为未知失败，fail-closed。
    未知返回不能证明交付成功，应记 wiring_errors + recovery_required=True。
    """
    dispatcher = MagicMock(name="DurableDispatcher")
    # 返回非 DispatchResult（例：未来接口变更 / 部分 mock）
    dispatcher.report_result.return_value = "not a dispatch result"
    state: dict[str, object] = {"dispatcher": dispatcher}

    _wire_dispatcher_report_result(
        state=state,
        binding_id="bdg_x",
        result_kind="final",
        result_payload={"reply": "hi"},
        error_source="report_result",
    )

    assert state["dispatch_recovery_required"] is True
    assert state["last_dispatch_outcome"] == "unknown_return"
    assert "non-DispatchResult" in state["last_dispatch_detail"]
    # 未知返回也写 wiring_errors
    assert state["wiring_errors"], "未知返回应该有 wiring_errors"
    record = state["wiring_errors"][0]
    assert record["kind"] == "unknown_return"
    assert record["outcome"] == "unknown_return"
    assert "not a dispatch result" in record["error"]


def test_wire_helper_unknown_return_overrides_stale_success_outcome() -> None:
    """非 ``DispatchResult`` 返回也要覆盖陈旧成功状态。"""
    dispatcher = MagicMock(name="DurableDispatcher")
    dispatcher.report_result.return_value = None  # 假阳性 return
    state: dict[str, object] = {
        "dispatcher": dispatcher,
        "last_dispatch_outcome": "result_delivered",
        "last_dispatch_detail": "stale success",
        "dispatch_recovery_required": False,
    }

    _wire_dispatcher_report_result(
        state=state,
        binding_id="bdg_x",
        result_kind="final",
        result_payload={"reply": "hi"},
        error_source="report_result",
    )

    assert state["last_dispatch_outcome"] == "unknown_return"
    assert state["dispatch_recovery_required"] is True
    assert state["wiring_errors"][0]["kind"] == "unknown_return"


def test_wire_helper_no_dispatcher_is_silent_noop() -> None:
    """state 没 dispatcher：helper 直接 return，不写任何字段。"""
    state: dict[str, object] = {}

    _wire_dispatcher_report_result(
        state=state,
        binding_id="bdg_x",
        result_kind="final",
        result_payload={"reply": "hi"},
        error_source="report_result",
    )

    assert state == {}, "无 dispatcher 不该修改 state"


# ---- decision 状态值稳定（durable_bridge.completion.CompletionStatus 字符串值） ----


@pytest.mark.parametrize(
    "outcome,reply,expected_status_value,expected_reason,expected_kind",
    [
        ("stop", "answer", "completed", "pi_run_stop", "final"),
        ("error", None, "failed", "pi_run_error", "error"),
        ("stop", "", "incomplete", "pi_empty_reply", "incomplete"),
        (None, None, "incomplete", "pi_native_outcome_missing", "inconclusive"),
        ("withdrawn", None, "incomplete", "pi_run_finished:withdrawn", "inconclusive"),
    ],
)
def test_decision_record_writes_expected_string_values(
    outcome: str | None,
    reply: str | None,
    expected_status_value: str,
    expected_reason: str,
    expected_kind: str,
) -> None:
    """5 种 outcome 走完 ``map_worker_outcome``，state 里写下的 status/reason/result_kind 字符串值稳定。"""
    state = _make_state(dispatcher=None, binding_id="")
    submission = _submission(state)
    stop_reason = outcome or ""
    text = reply or ""
    _settled_result(
        submission,
        state,
        _snapshot(text=text, stop_reason=stop_reason),
        items=[],
        now="2026-10-09T00:00:01Z",
    )
    assert state["last_completion_status"] == expected_status_value
    assert state["last_completion_reason"] == expected_reason
    assert state["last_result_kind"] == expected_kind
    enum_value = getattr(DurableCompletionStatus, expected_status_value.upper()).value
    assert enum_value == expected_status_value


# ---- 完成态可观测：CompletionConfidence 不被绕开 ----


def test_settled_main_decision_uses_existing_confidence_contract() -> None:
    """接线层不动 ``_terminal_result`` 的本地契约（status / reason / confidence）。"""
    dispatcher = _dispatcher_returning(_delivered_result())
    state = _make_state(dispatcher=dispatcher, binding_id="bdg_conf")
    submission = _submission(state)

    result = _settled_result(
        submission,
        state,
        _snapshot(text="ok", stop_reason="stop"),
        items=[],
        now="2026-10-09T00:00:01Z",
    )

    assert result.decision is not None
    assert result.decision.confidence is CompletionConfidence.EXACT
    assert result.decision.status is CompletionStatus.COMPLETED
    assert result.decision.terminal is True

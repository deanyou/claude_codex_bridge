"""Round 02 集成测试：真实 DurableDispatcher + MailboxKernelService + ResultStore round-trip。

验证 daemon 端 plumbing（bootstrap._inject_durable_dispatcher_into_pi_adapter）后：
- 真实 DurableDispatcher 实例能完成完整 dispatch → report_result 链路，ResultStore 写盘
- PiExecutionAdapter(dispatcher=real) → pane._durable_dispatcher 是同一个实例
- PiPaneExecutionAdapter 把 dispatcher 注入 runtime_state（start() 路径）

复用 test_durable_bridge_real_mailbox 已建好的真实 mailbox + TCP server 模式。
"""

from __future__ import annotations

import hashlib

import pytest

from durable_bridge.backend import InMemoryDurableBackend
from durable_bridge.binding_ledger import BindingLedger
from durable_bridge.dispatcher import DispatchOutcome, DurableDispatcher
from durable_bridge.endpoint import make_endpoint
from durable_bridge.result_store import ResultStore
from durable_bridge.tcp_client import DurableBridgeClient
from durable_bridge.tcp_server import TcpServer
from mailbox_kernel import MailboxKernelService
from mailbox_kernel.models import InboundEventRecord
from mailbox_kernel.model_enums import InboundEventStatus, InboundEventType
from provider_backends.pi.execution import PiExecutionAdapter
from provider_backends.pi.pane_execution import PiPaneExecutionAdapter
from storage.paths import PathLayout


# ---- helpers (从 test_durable_bridge_real_mailbox.py 复刻) ----


def _step_clock(start: str = "2026-10-09T08:00:00+00:00"):
    state = {"now": start}

    def clock() -> str:
        return state["now"]

    return clock, lambda seconds: state.__setitem__("now", state["now"])


def _make_event(*, event_id: str, agent: str = "agent-rt-002"):
    return InboundEventRecord(
        inbound_event_id=event_id,
        agent_name=agent,
        event_type=InboundEventType.TASK_REQUEST,
        message_id=f"msg-{event_id}",
        attempt_id="att-1",
        payload_ref=None,
        priority=0,
        status=InboundEventStatus.QUEUED,
        created_at="2026-10-09T08:00:00+00:00",
    )


def _spawn_bridge(backend: InMemoryDurableBackend):
    ep = make_endpoint()
    server = TcpServer(ep, backend)
    server.bind()
    server.start()
    final = ep.__class__(
        host=ep.host,
        port=server.bound_port,
        pid=ep.pid,
        bridge_epoch=ep.bridge_epoch,
        protocol_version=ep.protocol_version,
        token=ep.token,
    )
    server._endpoint = final
    return server, final


def _build_with_real_mailbox(layout: PathLayout):
    backend = InMemoryDurableBackend()
    server, ep = _spawn_bridge(backend)
    clock, _ = _step_clock()
    mailbox = MailboxKernelService(layout, clock=clock)
    ledger = BindingLedger(layout)
    client = DurableBridgeClient(ep)
    dispatcher = DurableDispatcher(
        ledger=ledger,
        mailbox=mailbox,
        bridge_client=client,
        bridge_epoch="epoch-rt-002",
        agent_name="agent-rt-002",
    )
    store = ResultStore(layout)
    dispatcher._result_store = store
    return {
        "dispatcher": dispatcher,
        "server": server,
        "client": client,
        "ledger": ledger,
        "mailbox": mailbox,
        "store": store,
        "clock": clock,
        "backend": backend,
    }


def _teardown(ctx):
    try:
        ctx["client"].close()
    except Exception:
        pass
    try:
        ctx["server"].shutdown()
    except Exception:
        pass


def _params(**overrides):
    base = dict(
        binding_id="b-rt-002",
        inbound_event_id="evt-rt-002",
        message_id="msg-rt-002",
        attempt_id="att-rt-002",
        request_id="req-rt-002",
        input_hash=hashlib.sha256(b"test prompt").hexdigest(),
        storage_path="/tmp/rt-002.sqlite",
        input_text="test prompt",
    )
    base.update(overrides)
    return base


@pytest.fixture
def layout(tmp_path):
    return PathLayout(project_root=tmp_path)


@pytest.fixture
def ctx(layout):
    c = _build_with_real_mailbox(layout)
    yield c
    _teardown(c)


# ============================================================
# PiExecutionAdapter / PiPaneExecutionAdapter plumbing
# ============================================================


def test_pi_execution_adapter_constructs_with_real_dispatcher(ctx):
    """PiExecutionAdapter(dispatcher=real) → pane._durable_dispatcher is real。"""
    dispatcher = ctx["dispatcher"]
    adapter = PiExecutionAdapter(dispatcher=dispatcher, binding_id="bdg-exec-rt-002")
    assert adapter.pane._durable_dispatcher is dispatcher
    assert adapter.pane._default_binding_id == "bdg-exec-rt-002"


def test_pi_execution_adapter_default_construction_has_no_dispatcher():
    """PiExecutionAdapter() 默认构造：pane._durable_dispatcher is None。"""
    adapter = PiExecutionAdapter()
    assert adapter.pane._durable_dispatcher is None
    assert adapter.pane._default_binding_id is None


def test_pi_pane_adapter_with_real_dispatcher_keeps_reference(ctx):
    """PiPaneExecutionAdapter(dispatcher=real) 持有引用。"""
    dispatcher = ctx["dispatcher"]
    pane = PiPaneExecutionAdapter(dispatcher=dispatcher, binding_id="bdg-pane-rt-002")
    assert pane._durable_dispatcher is dispatcher
    assert pane._default_binding_id == "bdg-pane-rt-002"


# ============================================================
# 真实 DurableDispatcher round-trip：dispatch + report_result → ResultStore 落盘
# ============================================================


def test_real_dispatcher_full_round_trip_persists_payload_to_delivered(layout):
    """完整 round-trip：dispatcher.dispatch → report_result → ledger.delivered + ResultStore 落盘。

    用 layout-fixture（不是 ctx），自己负责 cleanup，避开 ctx-fixture 共享问题。
    """
    ctx = _build_with_real_mailbox(layout)
    try:
        dispatcher = ctx["dispatcher"]
        ledger = ctx["ledger"]
        store = ctx["store"]
        mailbox = ctx["mailbox"]

        # 预置 inbound event（claim 需要它）
        mailbox._inbound_store.append(_make_event(event_id="evt-rt-002"))

        dispatched = dispatcher.dispatch(**_params())
        # 真实 mailbox happy path：SUBMITTED 推进到 submitted phase
        assert dispatched.outcome is DispatchOutcome.SUBMITTED
        assert dispatched.binding.delivery_phase == "submitted"

        # report_result 走 ResultStore（推荐路径）
        payload = {
            "reply": "round-trip reply body",
            "finish_reason": "stop",
            "decision": {
                "status": "completed",
                "reason": "pi_run_stop",
                "result_kind": "final",
            },
        }
        reported = dispatcher.report_result(
            binding_id="b-rt-002",
            result_kind="final",
            result_payload=payload,
        )
        assert reported.outcome is DispatchOutcome.RESULT_DELIVERED

        # ledger 已推进到 delivered
        record = ledger.lookup_by_binding_id("b-rt-002")
        assert record is not None
        assert record.delivery_phase == "delivered"
        assert record.result_payload_hash is not None

        # ResultStore 落盘
        on_disk = store.load("b-rt-002")
        assert on_disk is not None
        assert on_disk.payload["reply"] == "round-trip reply body"
        assert on_disk.payload["decision"]["status"] == "completed"
    finally:
        _teardown(ctx)


def test_real_dispatcher_report_result_payload_alone_persists_to_store(layout):
    """仅 result_payload 路径：ResultStore 落盘 + ledger delivered。"""
    ctx = _build_with_real_mailbox(layout)
    try:
        dispatcher = ctx["dispatcher"]
        ledger = ctx["ledger"]
        store = ctx["store"]
        mailbox = ctx["mailbox"]

        # 预置 inbound event
        mailbox._inbound_store.append(_make_event(event_id="evt-rt-002-payload"))

        # dispatch
        params = _params(
            binding_id="b-rt-002-payload",
            inbound_event_id="evt-rt-002-payload",
            message_id="msg-rt-002-payload",
            attempt_id="att-002-payload",
            request_id="req-002-payload",
            input_hash=hashlib.sha256(b"payload test").hexdigest(),
            storage_path="/tmp/rt-002-payload.sqlite",
            input_text="payload test",
        )
        dispatched = dispatcher.dispatch(**params)
        assert dispatched.outcome is DispatchOutcome.SUBMITTED

        # report_result with full payload
        payload = {"reply": "hello back", "finish_reason": "stop"}
        reported = dispatcher.report_result(
            binding_id="b-rt-002-payload",
            result_kind="final",
            result_payload=payload,
        )
        assert reported.outcome is DispatchOutcome.RESULT_DELIVERED

        # store 落盘
        on_disk = store.load("b-rt-002-payload")
        assert on_disk is not None
        assert on_disk.payload["reply"] == "hello back"

        # ledger 推进到 delivered
        record = ledger.lookup_by_binding_id("b-rt-002-payload")
        assert record is not None
        assert record.delivery_phase == "delivered"
        assert record.result_payload_ref is not None
        assert "results/b-rt-002-payload.json" in record.result_payload_ref
    finally:
        _teardown(ctx)


# ============================================================
# Wiring 端到端可观察性（不依赖真实 mailbox，验证 plumbing）
# ============================================================


def test_pane_adapter_state_includes_dispatcher_when_injected(ctx):
    """PiPaneExecutionAdapter 注入 dispatcher 后，state 可携带该 dispatcher（无需完整 start() 路径）。"""
    dispatcher = ctx["dispatcher"]
    pane = PiPaneExecutionAdapter(dispatcher=dispatcher, binding_id="bdg-state-002")

    state = {
        "dispatcher": pane._durable_dispatcher,
        "binding_id": pane._default_binding_id,
        "request_anchor": "anchor-002",
    }
    assert state["dispatcher"] is dispatcher
    assert state["binding_id"] == "bdg-state-002"


def test_pane_adapter_default_state_skips_wiring():
    """无 dispatcher 注入时，state 仍可构建（wiring 自动跳过）。"""
    pane = PiPaneExecutionAdapter()
    state = {
        "dispatcher": pane._durable_dispatcher,
        "binding_id": pane._default_binding_id,
    }
    assert state["dispatcher"] is None
    assert state["binding_id"] is None

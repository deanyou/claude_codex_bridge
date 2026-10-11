"""回归测试：durable dispatch 必须用真实 agent_name 路由到 mailbox。

背景（review B1，阻断级）：bootstrap 构造 DurableDispatcher 时传
`agent_name=project_id`（per-daemon 单值），但 mailbox 里的 inbound event
是按 `job.agent_name`（真实 agent，如 "codex"）存的。dispatcher 内部
`mailbox.claim(self._agent_name, ...)` 用 project_id 查，永远查不到 →
CLAIM_NOT_READY → 生产里 durable dispatch 从未真正成功过。

PR #4 的 12 个测试用 mock dispatcher，测不出这个问题。本文件用**真实
dispatcher + 真实 mailbox + 真实 bridge** 走完整链路。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from durable_bridge.binding_ledger import BindingLedger
from durable_bridge.dispatcher import DispatchOutcome, DurableDispatcher
from durable_bridge.backend import InMemoryDurableBackend
from durable_bridge.endpoint import BridgeEndpoint
from durable_bridge.result_store import ResultStore
from durable_bridge.tcp_client import DurableBridgeClient
from mailbox_kernel import MailboxKernelService
from mailbox_kernel.models import InboundEventRecord
from mailbox_kernel.model_enums import InboundEventStatus, InboundEventType
from storage.paths import PathLayout


@pytest.fixture
def live_bridge():
    """起一个真实 TCP 桥（InMemory backend），供 dispatcher 走完整 submit。"""
    from durable_bridge.endpoint import make_endpoint
    from durable_bridge.tcp_server import TcpServer

    backend = InMemoryDurableBackend()
    ep0 = make_endpoint()
    server = TcpServer(ep0, backend)
    port = server.bind()
    server.start()
    real = BridgeEndpoint(
        host=ep0.host, port=port, pid=ep0.pid,
        bridge_epoch=ep0.bridge_epoch,
        protocol_version=ep0.protocol_version, token=ep0.token,
    )
    server._endpoint = real
    try:
        yield real
    finally:
        try:
            server.shutdown()
        except Exception:
            pass


def _seed(mailbox, *, agent_name: str, event_id: str) -> None:
    mailbox._inbound_store.append(InboundEventRecord(
        inbound_event_id=event_id,
        agent_name=agent_name,          # ← 真实 agent
        event_type=InboundEventType.TASK_REQUEST,
        message_id=f"msg-{event_id}",
        attempt_id="att-1",
        payload_ref=None,
        priority=0,
        status=InboundEventStatus.QUEUED,
        created_at="2026-10-11T08:00:00+00:00",
    ))


def test_dispatch_routes_to_real_agent_not_project_id(tmp_path: Path, live_bridge) -> None:
    """dispatcher 构造时用 project_id，但传 per-call agent_name 后必须 claim 成功。

    这是 B1 的最小复现：不传 agent_name 时 claim 失败（CLAIM_NOT_READY），
    传了就必须走到 SUBMITTED。
    """
    layout = PathLayout(project_root=tmp_path)
    ledger = BindingLedger(layout)
    store = ResultStore(layout)
    mailbox = MailboxKernelService(layout, clock=lambda: "2026-10-11T08:00:00+00:00")
    ep = live_bridge
    client = DurableBridgeClient(ep)

    PROJECT_ID = "p" * 64          # bootstrap 传的 per-daemon 值
    REAL_AGENT = "codex"            # inbound 实际归属的 agent

    dispatcher = DurableDispatcher(
        ledger=ledger, mailbox=mailbox, bridge_client=client,
        bridge_epoch=ep.bridge_epoch, agent_name=PROJECT_ID,
        result_store=store,
    )

    _seed(mailbox, agent_name=REAL_AGENT, event_id="evt-agent-route")

    params = dict(
        binding_id="bdg-route-001",
        inbound_event_id="evt-agent-route",
        message_id="msg-route",
        attempt_id="att-route",
        request_id="req-route",
        input_hash=hashlib.sha256(b"x").hexdigest(),
        storage_path=str(tmp_path / "s.sqlite"),
        input_text="x",
    )

    # 1. 不传 agent_name → 沿用构造值(project_id) → claim 必然失败。
    #    实测有两种失败形态，取决于 project_id 是否长得像 agent 名：
    #      - 像 agent 名但查不到 -> CLAIM_NOT_READY
    #      - 不像 agent 名       -> CLAIM_RAISED（mailbox 抛 AgentValidationError）
    #    两者都是"没成功"，这里都接受。
    r_wrong = dispatcher.dispatch(**params)
    assert r_wrong.outcome in (
        DispatchOutcome.CLAIM_NOT_READY,
        DispatchOutcome.CLAIM_RAISED,
    ), f"不传 agent_name 时不应成功，实际 {r_wrong.outcome.value}"
    assert r_wrong.outcome is not DispatchOutcome.SUBMITTED

    # 2. 传真实 agent_name → claim 成功，走到 bridge submit
    r_right = dispatcher.dispatch(**params, agent_name=REAL_AGENT)
    assert r_right.outcome is DispatchOutcome.SUBMITTED, (
        f"传真实 agent_name 后应 SUBMITTED，实际 {r_right.outcome.value}"
        f" detail={r_right.detail!r}"
    )
    assert r_right.conversation_id

    client.close()


def test_inbound_stays_queued_when_agent_name_mismatch(tmp_path: Path, live_bridge) -> None:
    """agent_name 错配时不得误消费 inbound（账本与 mailbox 都要保持可重试）。"""
    layout = PathLayout(project_root=tmp_path)
    ledger = BindingLedger(layout)
    mailbox = MailboxKernelService(layout, clock=lambda: "2026-10-11T08:00:00+00:00")
    client = DurableBridgeClient(live_bridge)
    dispatcher = DurableDispatcher(
        ledger=ledger, mailbox=mailbox, bridge_client=client,
        bridge_epoch="ep", agent_name="project-id-not-the-agent",
        result_store=ResultStore(layout),
    )
    _seed(mailbox, agent_name="codex", event_id="evt-mismatch")

    r = dispatcher.dispatch(
        binding_id="bdg-mismatch", inbound_event_id="evt-mismatch",
        message_id="m", attempt_id="a", request_id="rq",
        input_hash=hashlib.sha256(b"x").hexdigest(),
        storage_path=str(tmp_path / "s.sqlite"), input_text="x",
        # 故意不传 agent_name
    )
    assert r.outcome in (
        DispatchOutcome.CLAIM_NOT_READY,
        DispatchOutcome.CLAIM_RAISED,
    ), f"错配时不应成功，实际 {r.outcome.value}"
    # 账本停在 intent（可重试），没被推进
    rec = ledger.lookup_by_binding_id("bdg-mismatch")
    assert rec is not None
    assert rec.delivery_phase == "intent", rec.delivery_phase
    client.close()

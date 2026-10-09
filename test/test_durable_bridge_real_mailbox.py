"""durable-bridge + 真实 MailboxKernelService 集成测试。

这些测试覆盖 v4 步骤 4 决议："新增真实存储与 lease 生命周期的集成测试"，
保留 FakeMailbox 单元测试（不替代）。验证：
- 真实 MailboxKernelService.claim() 返回 InboundEventRecord
- 真实 MailboxKernelService.consume() 写 JSON 状态，dispatcher 正确读取
- 真实 lease store 的生命周期：claim 后 lease 存在、ack_reply/consume 后释放
- 真实 inbound store 的 JSONL 写入：事件 append、状态推进
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from durable_bridge.backend import InMemoryDurableBackend
from durable_bridge.binding_ledger import BindingLedger
from durable_bridge.dispatcher import (
    DispatchOutcome,
    DurableDispatcher,
)
from durable_bridge.endpoint import make_endpoint
from durable_bridge.result_store import ResultStore
from durable_bridge.tcp_client import DurableBridgeClient
from durable_bridge.tcp_server import TcpServer
from mailbox_kernel import (
    DeliveryLeaseStore,
    InboundEventStore,
    MailboxKernelService,
    MailboxStore,
)
from mailbox_kernel.models import InboundEventRecord
from mailbox_kernel.model_enums import (
    InboundEventStatus,
    InboundEventType,
    LeaseState,
    MailboxState,
)
from storage.paths import PathLayout


# ---- helpers ----


def _clock(start: str = "2026-10-09T08:00:00+00:00"):
    """可步进时钟，让 lease 过期测试可控。"""
    state = {'now': start}

    def _c(now: str | None = None) -> str:
        if now is not None:
            state['now'] = now
        return state['now']

    def _step(seconds: int) -> str:
        cur = datetime.fromisoformat(state['now'])
        new = cur.timestamp() + seconds
        state['now'] = datetime.fromtimestamp(new, tz=timezone.utc).isoformat(
            timespec='seconds'
        )
        return state['now']

    return _c, _step


def _make_event(
    *,
    event_id: str,
    agent: str = 'agent-A',
    status: InboundEventStatus = InboundEventStatus.QUEUED,
) -> InboundEventRecord:
    return InboundEventRecord(
        inbound_event_id=event_id,
        agent_name=agent,
        event_type=InboundEventType.TASK_REQUEST,
        message_id=f'msg-{event_id}',
        attempt_id='att-1',
        payload_ref=None,
        priority=0,
        status=status,
        created_at='2026-10-09T08:00:00+00:00',
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


def _build_with_real_mailbox(
    layout: PathLayout,
    *,
    bridge_epoch: str = 'epoch-real',
    lease_ttl_seconds: float | None = None,
):
    backend = InMemoryDurableBackend()
    server, ep = _spawn_bridge(backend)
    clock, step_clock = _clock()
    mailbox = MailboxKernelService(
        layout,
        clock=clock,
        lease_ttl_seconds=lease_ttl_seconds,
    )
    ledger = BindingLedger(layout)
    client = DurableBridgeClient(ep)
    dispatcher = DurableDispatcher(
        ledger=ledger,
        mailbox=mailbox,
        bridge_client=client,
        bridge_epoch=bridge_epoch,
        agent_name='agent-A',
    )
    store = ResultStore(layout)
    dispatcher._result_store = store
    return {
        'dispatcher': dispatcher,
        'server': server,
        'client': client,
        'ledger': ledger,
        'mailbox': mailbox,
        'store': store,
        'clock': clock,
        'step_clock': step_clock,
    }


def _params(**overrides) -> dict:
    base = dict(
        binding_id='b-1',
        inbound_event_id='evt-1',
        message_id='msg-1',
        attempt_id='att-1',
        request_id='req-1',
        input_hash=hashlib.sha256(b'hi').hexdigest(),
        storage_path='/tmp/x.sqlite',
        input_text='hi',
    )
    base.update(overrides)
    return base


@pytest.fixture
def layout(tmp_path: Path) -> PathLayout:
    return PathLayout(project_root=tmp_path)


# ============================================================
# 基础集成
# ============================================================


def test_dispatch_with_real_mailbox_happy_path(layout: PathLayout) -> None:
    """真实 MailboxKernelService 走通完整 dispatch。"""
    ctx = _build_with_real_mailbox(layout)
    mailbox = ctx['mailbox']
    # 预置一个 inbound event 让 claim 能拿到
    mailbox._inbound_store.append(_make_event(event_id='evt-1'))

    r = ctx['dispatcher'].dispatch(**_params())
    assert r.outcome is DispatchOutcome.SUBMITTED
    assert r.conversation_id
    assert r.submission_id

    # 真实 lease 已写
    lease = mailbox._lease_store.load('agent-A')
    assert lease is not None
    assert lease.lease_state is LeaseState.ACQUIRED
    assert lease.inbound_event_id == 'evt-1'

    # 真实 inbound event 已推进
    latest = mailbox._inbound_store.get_latest('agent-A', 'evt-1')
    assert latest is not None
    assert latest.status is InboundEventStatus.DELIVERING

    ctx['client'].close()
    ctx['server'].shutdown()


def test_dispatch_consume_advances_event_to_consumed(layout: PathLayout) -> None:
    """report_result → 真实 consume → 事件变 CONSUMED。"""
    ctx = _build_with_real_mailbox(layout)
    mailbox = ctx['mailbox']
    mailbox._inbound_store.append(_make_event(event_id='evt-1'))
    ctx['dispatcher'].dispatch(**_params())
    ctx['dispatcher'].report_result(
        binding_id='b-1',
        result_kind='final',
        result_payload={'answer': 42},
    )
    latest = mailbox._inbound_store.get_latest('agent-A', 'evt-1')
    assert latest is not None
    assert latest.status is InboundEventStatus.CONSUMED
    # lease 已释放
    assert mailbox._lease_store.load('agent-A') is None

    ctx['client'].close()
    ctx['server'].shutdown()


def test_dispatch_persists_full_result_via_real_store(layout: PathLayout) -> None:
    """result_payload 走 ResultStore 落盘，账本存 ref。"""
    ctx = _build_with_real_mailbox(layout)
    mailbox = ctx['mailbox']
    mailbox._inbound_store.append(_make_event(event_id='evt-1'))
    ctx['dispatcher'].dispatch(**_params())

    payload = {'answer': 42, 'sources': ['a', 'b']}
    r = ctx['dispatcher'].report_result(
        binding_id='b-1',
        result_kind='final',
        result_payload=payload,
    )
    assert r.outcome is DispatchOutcome.RESULT_DELIVERED
    # 账本 result_payload_ref 指向 results/<binding_id>.json
    rec = ctx['ledger'].lookup_by_binding_id('b-1')
    assert rec is not None
    assert rec.result_payload_ref is not None
    assert 'results/b-1.json' in rec.result_payload_ref
    # ResultStore 落盘
    assert ctx['store'].exists('b-1')
    recovered = ctx['store'].load('b-1')
    assert recovered is not None
    assert recovered.payload == payload

    ctx['client'].close()
    ctx['server'].shutdown()


# ============================================================
# 真实 enum 状态比较
# ============================================================


def test_reconcile_uses_real_inbound_event_status_lowercase(layout: PathLayout) -> None:
    """reconcile 读到的 mailbox_event_status 是真实 InboundEventStatus 枚举的
    小写值（'consumed' / 'abandoned' / 'superseded' / 'delivering' / 'queued' / 'created'）。"""
    ctx = _build_with_real_mailbox(layout)
    mailbox = ctx['mailbox']
    mailbox._inbound_store.append(_make_event(event_id='evt-1'))
    ctx['dispatcher'].dispatch(**_params())
    obs = ctx['dispatcher'].reconcile(binding_id='b-1')
    # claim 后是 delivering
    assert obs.mailbox_event_status == 'delivering'

    ctx['client'].close()
    ctx['server'].shutdown()


def test_reconcile_after_consume_shows_consumed(layout: PathLayout) -> None:
    ctx = _build_with_real_mailbox(layout)
    mailbox = ctx['mailbox']
    mailbox._inbound_store.append(_make_event(event_id='evt-1'))
    ctx['dispatcher'].dispatch(**_params())
    ctx['dispatcher'].report_result(
        binding_id='b-1',
        result_kind='final',
        result_payload={'x': 1},
    )
    obs = ctx['dispatcher'].reconcile(binding_id='b-1')
    assert obs.mailbox_event_status == 'consumed'
    assert obs.binding.delivery_phase == 'delivered'

    ctx['client'].close()
    ctx['server'].shutdown()


def test_lease_expiry_via_real_clock_blocks_delivery(layout: PathLayout) -> None:
    """lease 过期后 mailbox 端事件变 ABANDONED；dispatcher 拒绝 delivered。"""
    ctx = _build_with_real_mailbox(layout, lease_ttl_seconds=10)
    mailbox = ctx['mailbox']
    clock = ctx['clock']
    step_clock = ctx['step_clock']
    mailbox._inbound_store.append(_make_event(event_id='evt-1'))
    ctx['dispatcher'].dispatch(**_params())

    # 把时间推进 30s 让 lease 过期
    step_clock(30)
    # 触发一次 reconcile 强制 expire_lease 流程
    mailbox.expire_lease('agent-A', finished_at=clock())
    latest = mailbox._inbound_store.get_latest('agent-A', 'evt-1')
    assert latest is not None
    assert latest.status is InboundEventStatus.ABANDONED

    # 现在 report_result 应得 RESULT_CONFLICT
    r = ctx['dispatcher'].report_result(
        binding_id='b-1',
        result_kind='final',
        result_payload={'x': 1},
    )
    assert r.outcome is DispatchOutcome.RESULT_CONFLICT
    rec = ctx['ledger'].lookup_by_binding_id('b-1')
    # 关键不变量：lease 过期 ≠ delivered；账本保持 result_pending
    assert rec.delivery_phase == 'result_pending'

    ctx['client'].close()
    ctx['server'].shutdown()


# ============================================================
# claim 失败的真实路径
# ============================================================


def test_claim_returns_none_when_event_not_claimable(layout: PathLayout) -> None:
    """事件已终态（CONSUMED）时 claim 返回 None。"""
    ctx = _build_with_real_mailbox(layout)
    mailbox = ctx['mailbox']
    mailbox._inbound_store.append(
        _make_event(event_id='evt-1', status=InboundEventStatus.CONSUMED)
    )
    r = ctx['dispatcher'].dispatch(**_params())
    assert r.outcome is DispatchOutcome.CLAIM_NOT_READY
    # 账本仍 intent
    rec = ctx['ledger'].lookup_by_binding_id('b-1')
    assert rec.delivery_phase == 'intent'
    # 没有 lease
    assert mailbox._lease_store.load('agent-A') is None

    ctx['client'].close()
    ctx['server'].shutdown()


def test_claim_returns_none_when_event_missing(layout: PathLayout) -> None:
    """事件不存在 → claim 失败 → 不调 submit。"""
    ctx = _build_with_real_mailbox(layout)
    r = ctx['dispatcher'].dispatch(**_params())
    assert r.outcome is DispatchOutcome.CLAIM_NOT_READY
    rec = ctx['ledger'].lookup_by_binding_id('b-1')
    assert rec.delivery_phase == 'intent'
    assert rec.submission_id is None

    ctx['client'].close()
    ctx['server'].shutdown()


def test_claim_raises_propagates_as_claim_raised(layout: PathLayout) -> None:
    """claim 内部异常 → CLAIM_RAISED 路径，账本不动。"""
    ctx = _build_with_real_mailbox(layout)
    mailbox = ctx['mailbox']

    # 把 claim 直接 patch 成抛异常
    original_claim = mailbox.claim
    def boom(*args, **kwargs):
        raise OSError('disk full')
    mailbox.claim = boom  # type: ignore[method-assign]

    r = ctx['dispatcher'].dispatch(**_params())
    assert r.outcome is DispatchOutcome.CLAIM_RAISED
    rec = ctx['ledger'].lookup_by_binding_id('b-1')
    # 关键不变量：异常情况下账本仍是 intent
    assert rec.delivery_phase == 'intent'

    # 恢复
    mailbox.claim = original_claim  # type: ignore[method-assign]
    ctx['client'].close()
    ctx['server'].shutdown()

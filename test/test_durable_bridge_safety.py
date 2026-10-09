"""durable-bridge 取消安全 + 恢复对账 + 完整结果持久化（步骤 4 缺口补齐）。

覆盖：
- mark_abandoned 从 conversation_bound 拒绝（forward progress 检测）
- force_abandon 需要 confirmed_no_pending_submission / delivery 双确认
- reconcile 对 conversation_bound / result_pending 的建议
- 完整结果持久化：result_payload 全文落盘，hash 仅作摘要
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from durable_bridge.backend import InMemoryDurableBackend
from durable_bridge.binding_ledger import (
    BindingConflict,
    BindingLedger,
)
from durable_bridge.dispatcher import (
    DispatchOutcome,
    DurableDispatcher,
)
from durable_bridge.endpoint import make_endpoint
from durable_bridge.result_store import ResultStore
from durable_bridge.tcp_client import DurableBridgeClient
from durable_bridge.tcp_server import TcpServer
from storage.paths import PathLayout


# ---- fake mailbox（与 dispatcher 现有 FakeMailbox 行为一致）----


@dataclass
class _FakeEvent:
    inbound_event_id: str
    status: str  # lowercase
    event_type: str = 'TASK_DISPATCH'


@dataclass
class _FakeLease:
    inbound_event_id: str
    lease_state: str = 'ACQUIRED'


class _FakeLeaseStore:
    def __init__(self):
        self._by_agent: dict[str, _FakeLease] = {}

    def load(self, agent_name):
        return self._by_agent.get(agent_name)

    def save(self, lease, agent_name):
        self._by_agent[agent_name] = lease

    def remove(self, agent_name):
        self._by_agent.pop(agent_name, None)


class _FakeInboundStore:
    def __init__(self):
        self._by_agent: dict[str, list[_FakeEvent]] = {}

    def append(self, event, agent_name):
        self._by_agent.setdefault(agent_name, []).append(event)

    def get_latest(self, agent_name, event_id):
        for e in reversed(self._by_agent.get(agent_name, [])):
            if e.inbound_event_id == event_id:
                return e
        return None

    def set_status(self, agent_name, event_id, status):
        for e in reversed(self._by_agent.setdefault(agent_name, [])):
            if e.inbound_event_id == event_id:
                e.status = status
                return
        self._by_agent.setdefault(agent_name, []).append(
            _FakeEvent(inbound_event_id=event_id, status=status)
        )


class FakeMailbox:
    def __init__(self):
        self._lease_store = _FakeLeaseStore()
        self._inbound_store = _FakeInboundStore()
        self.consume_returns = None
        self.consume_raises = None
        self.consume_calls = 0

    def claim(self, agent_name, inbound_event_id):
        ev = _FakeEvent(inbound_event_id=inbound_event_id, status='delivering')
        self._inbound_store.append(ev, agent_name)
        self._lease_store.save(
            _FakeLease(inbound_event_id=inbound_event_id), agent_name
        )
        return ev

    def consume(self, agent_name, inbound_event_id):
        self.consume_calls += 1
        if self.consume_raises is not None:
            raise self.consume_raises
        if self.consume_returns is not None:
            return self.consume_returns
        existing = self._inbound_store.get_latest(agent_name, inbound_event_id)
        if existing is None:
            return None
        existing.status = 'consumed'
        self._lease_store.remove(agent_name)
        return existing


# ---- helpers ----


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


def _build(layout, backend, mailbox, *, bridge_epoch='epoch-test'):
    server, ep = _spawn_bridge(backend)
    ledger = BindingLedger(layout)
    client = DurableBridgeClient(ep)
    dispatcher = DurableDispatcher(
        ledger=ledger,
        mailbox=mailbox,
        bridge_client=client,
        bridge_epoch=bridge_epoch,
        agent_name='agent-A',
    )
    return dispatcher, server, client, ledger


def _params(**overrides):
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
# Gap 1: 取消安全
# ============================================================


def test_mark_abandoned_rejected_from_conversation_bound(layout: PathLayout) -> None:
    """关键安全网：conversation_bound 不能 mark_abandoned。

    理由：conversation_id 已落账本意味着 bridge 端 conversation 存在，
    submit 是否已接受（回包丢失）未知。盲目 abandon 意味着可能丢失
    已被 bridge 接受的任务。
    """
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build(layout, backend, mailbox)
    try:
        # 制造 conversation_bound 状态
        dispatcher.dispatch(**_params())
        # 把账本回退到 conversation_bound 状态（模拟 submit 回包丢失）
        rec = ledger.lookup_by_binding_id('b-1')
        assert rec is not None
        # 手工清掉 submission_id，回到 conversation_bound
        from durable_bridge.binding_ledger import BindingRecord
        from dataclasses import replace as _dc_replace
        new_rec = _dc_replace(
            rec,
            submission_id=None,
            delivery_phase='conversation_bound',
        )
        # 用 write path 落盘
        ledger._write_locked(new_rec)
        # 现在 mark_abandoned 应被拒
        with pytest.raises(BindingConflict) as exc:
            ledger.mark_abandoned('b-1', reason='oops', bridge_epoch='ep')
        assert 'conversation_bound' in str(exc.value)
        assert 'forward progress' in str(exc.value)
    finally:
        client.close()
        server.shutdown()


def test_force_abandon_requires_confirmation_from_conversation_bound(
    layout: PathLayout,
) -> None:
    """force_abandon 从 conversation_bound 需显式确认无未决 submission。"""
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build(layout, backend, mailbox)
    try:
        dispatcher.dispatch(**_params())
        # 强制回退到 conversation_bound
        rec = ledger.lookup_by_binding_id('b-1')
        from dataclasses import replace as _dc_replace
        new_rec = _dc_replace(
            rec, submission_id=None, delivery_phase='conversation_bound'
        )
        ledger._write_locked(new_rec)

        # 不带 confirmed → 拒
        with pytest.raises(BindingConflict) as exc:
            ledger.force_abandon('b-1', reason='cleanup', bridge_epoch='ep')
        assert 'confirmed_no_pending_submission' in str(exc.value)

        # 带 confirmed → 通过
        ledger.force_abandon(
            'b-1', reason='cleanup', bridge_epoch='ep',
            confirmed_no_pending_submission=True,
        )
        rec = ledger.lookup_by_binding_id('b-1')
        assert rec.delivery_phase == 'abandoned'
    finally:
        client.close()
        server.shutdown()


def test_force_abandon_requires_delivery_confirmation_from_result_pending(
    layout: PathLayout,
) -> None:
    """force_abandon 从 result_pending 需 confirmed_no_pending_delivery。"""
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build(layout, backend, mailbox)
    try:
        dispatcher.dispatch(**_params())
        ledger.record_result_pending(
            'b-1',
            result_id='r-1',
            result_kind='final',
            result_payload_hash='hp',
            bridge_epoch='epoch-test',
        )
        # 不带 confirmed → 拒
        with pytest.raises(BindingConflict) as exc:
            ledger.force_abandon('b-1', reason='cleanup', bridge_epoch='ep')
        assert 'confirmed_no_pending_delivery' in str(exc.value)

        # 带 confirmed → 通过
        ledger.force_abandon(
            'b-1', reason='cleanup', bridge_epoch='ep',
            confirmed_no_pending_delivery=True,
        )
        rec = ledger.lookup_by_binding_id('b-1')
        assert rec.delivery_phase == 'abandoned'
    finally:
        client.close()
        server.shutdown()


def test_force_abandon_never_allows_from_delivered(layout: PathLayout) -> None:
    """delivered 永远不能 force_abandon。"""
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build(layout, backend, mailbox)
    try:
        dispatcher.dispatch(**_params())
        dispatcher.report_result(
            binding_id='b-1', result_kind='final', result_payload_hash='hp'
        )
        with pytest.raises(BindingConflict):
            ledger.force_abandon(
                'b-1', reason='oops', bridge_epoch='ep',
                confirmed_no_pending_submission=True,
                confirmed_no_pending_delivery=True,
            )
    finally:
        client.close()
        server.shutdown()


# ============================================================
# Gap 2: Reconcile per-phase advice
# ============================================================


def test_reconcile_conversation_bound_advice_safe_to_query_bridge(
    layout: PathLayout,
) -> None:
    """conversation_bound 阶段：建议"查询原提交"。"""
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build(layout, backend, mailbox)
    try:
        dispatcher.dispatch(**_params())
        # 手工回退到 conversation_bound
        rec = ledger.lookup_by_binding_id('b-1')
        from dataclasses import replace as _dc_replace
        new_rec = _dc_replace(
            rec, submission_id=None, delivery_phase='conversation_bound'
        )
        ledger._write_locked(new_rec)

        obs = dispatcher.reconcile(binding_id='b-1')
        assert obs.binding.delivery_phase == 'conversation_bound'
        assert 'conversation_bound' in obs.advice.lower()
        assert 'query' in obs.advice.lower() or 'bridge' in obs.advice.lower()
    finally:
        client.close()
        server.shutdown()


def test_reconcile_result_pending_advice_safe_to_advance(layout: PathLayout) -> None:
    """result_pending 阶段：建议"补交结果"。"""
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build(layout, backend, mailbox)
    try:
        dispatcher.dispatch(**_params())
        ledger.record_result_pending(
            'b-1',
            result_id='r-1',
            result_kind='final',
            result_payload_hash='hp',
            bridge_epoch='epoch-test',
        )
        obs = dispatcher.reconcile(binding_id='b-1')
        assert obs.binding.delivery_phase == 'result_pending'
        assert 'result_pending' in obs.advice.lower()
        assert 'report_result' in obs.advice.lower() or 'delivered' in obs.advice.lower()
    finally:
        client.close()
        server.shutdown()


def test_reconcile_result_pending_advice_when_mailbox_already_consumed(
    layout: PathLayout,
) -> None:
    """result_pending 阶段：mailbox 已 consumed 时建议"调 report_result 完成最后一步"。

    这是关键恢复点：账本说 result_pending，mailbox 端已 consumed，
    只需再调一次 report_result 即可（consume 幂等 + record_delivery 写盘）。
    """
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build(layout, backend, mailbox)
    try:
        dispatcher.dispatch(**_params())
        ledger.record_result_pending(
            'b-1',
            result_id='r-1',
            result_kind='final',
            result_payload_hash='hp',
            bridge_epoch='epoch-test',
        )
        # mailbox 端已是 consumed
        mailbox._inbound_store.set_status('agent-A', 'evt-1', 'consumed')
        obs = dispatcher.reconcile(binding_id='b-1')
        assert 'already consumed' in obs.advice.lower() or 'report_result' in obs.advice.lower()
    finally:
        client.close()
        server.shutdown()


def test_reconcile_uses_lowercase_status(layout: PathLayout) -> None:
    """验证 reconcile 用的 mailbox_event_status 是真实枚举小写值。"""
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build(layout, backend, mailbox)
    try:
        dispatcher.dispatch(**_params())
        obs = dispatcher.reconcile(binding_id='b-1')
        # FakeMailbox 用 lowercase
        assert obs.mailbox_event_status == 'delivering'
    finally:
        client.close()
        server.shutdown()


# ============================================================
# Gap 3: 完整结果持久化（ResultStore）
# ============================================================


def test_result_store_persists_full_payload(layout: PathLayout) -> None:
    """ResultStore 落盘完整结果，hash 仅作摘要。"""
    store = ResultStore(layout)
    payload = {'reply': 'the answer', 'sources': ['a', 'b']}
    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()
    path = store.save(
        binding_id='b-1',
        payload=payload,
        payload_hash=payload_hash,
    )
    assert path.exists()
    # 重新读出：内容应能完整恢复
    recovered = store.load('b-1')
    assert recovered is not None
    assert recovered.payload == payload
    assert recovered.payload_hash == payload_hash


def test_result_store_save_idempotent(layout: PathLayout) -> None:
    """同 binding_id + 同 hash → 幂等（不重新写）。"""
    store = ResultStore(layout)
    payload = {'x': 1}
    h = hashlib.sha256(b'1').hexdigest()
    p1 = store.save('b-1', payload, h)
    p2 = store.save('b-1', payload, h)
    assert p1 == p2
    # 不同 payload 拒绝
    with pytest.raises(BindingConflict):
        store.save('b-1', {'x': 2}, hashlib.sha256(b'2').hexdigest())


def test_result_store_missing_returns_none(layout: PathLayout) -> None:
    store = ResultStore(layout)
    assert store.load('nonexistent') is None


def test_result_store_atomic_write_0600(layout: PathLayout) -> None:
    """POSIX 上结果文件 0600。"""
    import os
    import stat
    if os.name == 'nt':
        pytest.skip('POSIX-only')
    store = ResultStore(layout)
    p = store.save('b-1', {'k': 'v'}, hashlib.sha256(b'k').hexdigest())
    mode = stat.S_IMODE(p.stat().st_mode)
    assert mode == 0o600


def test_result_store_recovers_after_ledger_loss(layout: PathLayout) -> None:
    """关键安全网：账本丢了（用 fresh PathLayout）但结果文件还在，
    能从结果文件恢复 payload。"""
    store1 = ResultStore(layout)
    payload = {'answer': 42}
    h = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()
    store1.save('b-1', payload, h)
    # 新 PathLayout 实例
    layout2 = PathLayout(project_root=layout.project_root)
    store2 = ResultStore(layout2)
    recovered = store2.load('b-1')
    assert recovered is not None
    assert recovered.payload == payload


# ============================================================
# dispatch + report_result 走 ResultStore 路径
# ============================================================


def test_report_result_persists_full_payload_via_result_store(
    layout: PathLayout,
) -> None:
    """report_result 接受 payload（dict / str），落 ResultStore，账本仅存 ref。"""
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build(layout, backend, mailbox)
    store = ResultStore(layout)
    # 注入 store 到 dispatcher
    dispatcher._result_store = store
    try:
        dispatcher.dispatch(**_params())
        payload = {'reply': 'final answer', 'finish_reason': 'stop'}
        r = dispatcher.report_result(
            binding_id='b-1',
            result_kind='final',
            result_payload=payload,
        )
        assert r.outcome is DispatchOutcome.RESULT_DELIVERED
        # 账本存的是 ref
        rec = ledger.lookup_by_binding_id('b-1')
        assert rec.result_payload_ref is not None
        # 重新读出完整 payload
        restored = store.load('b-1')
        assert restored is not None
        assert restored.payload == payload
    finally:
        client.close()
        server.shutdown()

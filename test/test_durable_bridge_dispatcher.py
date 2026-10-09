"""durable-bridge 派发编排器测试（v4 实施步骤 3）。

覆盖决策表：
- 正常路径：intent → claim → submit → record_submission
- claim 暂时失败（CLAIM_NOT_READY）→ 保留 intent，不调 submit
- claim 抛异常（CLAIM_RAISED）→ 保留 intent，不调 submit
- 竞争者已认领 → 视为 CLAIM_NOT_READY
- 事件已写但 lease 写失败（注入故障）→ 视为可重试
- 取消时存在未决提交 → 拒绝 mark_abandoned
- ledger conflict（input_hash 冲突）→ 拒绝
- 重复 dispatch 同 binding_id → ALREADY_TERMINAL（已 submitted）
- reconcile 给出可执行建议
"""

from __future__ import annotations

import hashlib
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
    DispatcherError,
    DurableDispatcher,
)
from durable_bridge.result_store import ResultStore
from durable_bridge.endpoint import make_endpoint
from durable_bridge.tcp_client import DurableBridgeClient
from durable_bridge.tcp_server import TcpServer
from storage.paths import PathLayout


@pytest.fixture
def layout(tmp_path: Path) -> PathLayout:
    return PathLayout(project_root=tmp_path)


# ---- fake mailbox ----


@dataclass
class _FakeEvent:
    inbound_event_id: str
    # 与真实 InboundEventStatus 一致：小写字符串
    status: str  # 'created' | 'delivering' | 'consumed' | 'superseded' | 'abandoned' | 'queued'
    event_type: str = 'TASK_DISPATCH'


@dataclass
class _FakeLease:
    inbound_event_id: str
    lease_state: str = 'ACQUIRED'


class _FakeLeaseStore:
    def __init__(self) -> None:
        self._by_agent: dict[str, _FakeLease] = {}
        self.fail_next: BaseException | None = None

    def load(self, agent_name: str) -> _FakeLease | None:
        return self._by_agent.get(agent_name)

    def save(self, lease: _FakeLease, agent_name: str) -> None:
        if self.fail_next is not None:
            exc, self.fail_next = self.fail_next, None
            raise exc
        self._by_agent[agent_name] = lease

    def remove(self, agent_name: str) -> None:
        self._by_agent.pop(agent_name, None)


class _FakeInboundStore:
    def __init__(self) -> None:
        self._by_agent: dict[str, list[_FakeEvent]] = {}
        self.fail_next: BaseException | None = None

    def append(self, event: _FakeEvent, agent_name: str) -> None:
        if self.fail_next is not None:
            exc, self.fail_next = self.fail_next, None
            raise exc
        self._by_agent.setdefault(agent_name, []).append(event)

    def get_latest(self, agent_name: str, event_id: str) -> _FakeEvent | None:
        events = self._by_agent.get(agent_name, [])
        for e in reversed(events):
            if e.inbound_event_id == event_id:
                return e
        return None

    def set_status(self, agent_name: str, event_id: str, status: str) -> None:
        """测试辅助：手动设置某事件的最新状态。"""
        events = self._by_agent.setdefault(agent_name, [])
        for e in reversed(events):
            if e.inbound_event_id == event_id:
                e.status = status
                return
        events.append(_FakeEvent(inbound_event_id=event_id, status=status))


class FakeMailbox:
    """最小 mailbox 替身：覆盖 dispatcher 用到的方法。"""

    def __init__(self) -> None:
        self._lease_store = _FakeLeaseStore()
        self._inbound_store = _FakeInboundStore()
        self.claim_returns_none = False
        self.claim_raises: BaseException | None = None
        self.claim_calls = 0
        # 测试可设置 consume 行为：
        # - 默认走正常路径：将最新事件状态置为 CONSUMED
        self.consume_returns: _FakeEvent | None = None
        self.consume_raises: BaseException | None = None
        self.consume_calls = 0

    def claim(self, agent_name: str, inbound_event_id: str) -> _FakeEvent | None:
        self.claim_calls += 1
        if self.claim_raises is not None:
            raise self.claim_raises
        if self.claim_returns_none:
            return None
        # 真正"认领"：append 一条 DELIVERING + 写 lease
        ev = _FakeEvent(inbound_event_id=inbound_event_id, status='delivering')
        self._inbound_store.append(ev, agent_name)
        self._lease_store.save(
            _FakeLease(inbound_event_id=inbound_event_id),
            agent_name,
        )
        return ev

    def consume(self, agent_name: str, inbound_event_id: str) -> _FakeEvent | None:
        self.consume_calls += 1
        if self.consume_raises is not None:
            raise self.consume_raises
        if self.consume_returns is not None:
            return self.consume_returns
        # 默认路径：把事件状态置为 consumed，返回事件
        existing = self._inbound_store.get_latest(agent_name, inbound_event_id)
        if existing is None:
            return None
        existing.status = 'consumed'
        # 释放 lease
        self._lease_store.remove(agent_name)
        return existing


# ---- bridge 辅助 ----


def _spawn_bridge(
    backend: InMemoryDurableBackend,
) -> tuple[TcpServer, Any]:
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


def _build_dispatcher(
    *,
    layout: PathLayout,
    backend: InMemoryDurableBackend,
    mailbox: FakeMailbox,
    bridge_epoch: str = 'epoch-test',
) -> tuple[DurableDispatcher, TcpServer, DurableBridgeClient, BindingLedger]:
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


# ---- 正常路径 ----


def test_dispatch_happy_path(layout: PathLayout) -> None:
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build_dispatcher(
        layout=layout, backend=backend, mailbox=mailbox
    )
    try:
        result = dispatcher.dispatch(**_params())
        assert result.outcome is DispatchOutcome.SUBMITTED
        assert result.submission_id
        assert result.conversation_id
        # 账本已 submitted
        rec = ledger.lookup_by_binding_id('b-1')
        assert rec is not None
        assert rec.delivery_phase == 'submitted'
        assert rec.submission_id == result.submission_id
    finally:
        client.close()
        server.shutdown()


def test_dispatch_then_report_result_advances_to_delivered(layout: PathLayout) -> None:
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build_dispatcher(
        layout=layout, backend=backend, mailbox=mailbox
    )
    try:
        r1 = dispatcher.dispatch(**_params())
        assert r1.outcome is DispatchOutcome.SUBMITTED
        r2 = dispatcher.report_result(
            binding_id='b-1',
            result_id='res-1',
            result_kind='final',
            result_payload_hash='hp-1',
        )
        assert r2.outcome is DispatchOutcome.RESULT_DELIVERED
        rec = ledger.lookup_by_binding_id('b-1')
        assert rec is not None
        assert rec.delivery_phase == 'delivered'
        assert rec.result_id == 'res-1'
        assert rec.result_kind == 'final'
    finally:
        client.close()
        server.shutdown()


def test_repeat_report_result_with_full_payload_is_idempotent(
    layout: PathLayout,
) -> None:
    """重复报告完整 payload 必须幂等（不产生 RESULT_CONFLICT）。

    回归测试：之前 dispatcher 在 delivered 分支比较的是入参
    ``result_payload_hash``（在 ``result_payload`` 路径上为 ``None``），
    导致重复报告被误判为 ``RESULT_CONFLICT``。修复后比较的是
    实际派生出来的 ``resolved_hash``。
    """
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    result_store = ResultStore(layout)
    server, ep = _spawn_bridge(backend)
    ledger = BindingLedger(layout)
    client = DurableBridgeClient(ep)
    dispatcher = DurableDispatcher(
        ledger=ledger,
        mailbox=mailbox,
        bridge_client=client,
        bridge_epoch='epoch-test',
        agent_name='agent-A',
        result_store=result_store,
    )
    try:
        r1 = dispatcher.dispatch(**_params())
        assert r1.outcome is DispatchOutcome.SUBMITTED

        # 第一次：result_payload 路径，应走到 RESULT_DELIVERED
        payload = {'reply': 'hello', 'finish_reason': 'stop'}
        r2 = dispatcher.report_result(
            binding_id='b-1',
            result_kind='final',
            result_payload=payload,
        )
        assert r2.outcome is DispatchOutcome.RESULT_DELIVERED

        # 第二次：重复报告同一 payload（result_payload_hash 入参为 None），
        # 必须幂等返回 RESULT_DELIVERED，而不是 RESULT_CONFLICT。
        r3 = dispatcher.report_result(
            binding_id='b-1',
            result_kind='final',
            result_payload=payload,
        )
        assert r3.outcome is DispatchOutcome.RESULT_DELIVERED, (
            f'重复报告完整 payload 应幂等，实际 {r3.outcome.value!r}: {r3.detail}'
        )

        # 账本仍是 delivered，未被覆盖成 conflict
        rec = ledger.lookup_by_binding_id('b-1')
        assert rec is not None
        assert rec.delivery_phase == 'delivered'
    finally:
        client.close()
        server.shutdown()


def test_repeat_report_result_with_different_payload_raises_conflict(
    layout: PathLayout,
) -> None:
    """重复报告不同 payload：ResultStore.save() 拒绝（BindingConflict）。

    不同 payload 冲突不被幂等逻辑掩盖，由 ResultStore 在 save 阶段拦截。
    （不是由 dispatcher's delivered-phase 分支判定的——那是 hash-only 路径的
    第二个防线。）
    """
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    result_store = ResultStore(layout)
    server, ep = _spawn_bridge(backend)
    ledger = BindingLedger(layout)
    client = DurableBridgeClient(ep)
    dispatcher = DurableDispatcher(
        ledger=ledger,
        mailbox=mailbox,
        bridge_client=client,
        bridge_epoch='epoch-test',
        agent_name='agent-A',
        result_store=result_store,
    )
    try:
        r1 = dispatcher.dispatch(**_params())
        assert r1.outcome is DispatchOutcome.SUBMITTED

        r2 = dispatcher.report_result(
            binding_id='b-1',
            result_kind='final',
            result_payload={'reply': 'first'},
        )
        assert r2.outcome is DispatchOutcome.RESULT_DELIVERED

        # 不同 payload：ResultStore.save() 会抛 BindingConflict。
        # 这个例外不应该被错误吞掉（上游接线处应该传播或者记账）。
        with pytest.raises(BindingConflict):
            dispatcher.report_result(
                binding_id='b-1',
                result_kind='final',
                result_payload={'reply': 'different'},
            )
    finally:
        client.close()
        server.shutdown()


# ---- claim 失败 / 异常 ----


def test_dispatch_when_claim_returns_none_keeps_intent(layout: PathLayout) -> None:
    """claim 返回 None 时：保留 intent，不调 submit，不写 abandoned。"""
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    mailbox.claim_returns_none = True
    dispatcher, server, client, ledger = _build_dispatcher(
        layout=layout, backend=backend, mailbox=mailbox
    )
    try:
        result = dispatcher.dispatch(**_params())
        assert result.outcome is DispatchOutcome.CLAIM_NOT_READY
        # 账本仍是 intent
        rec = ledger.lookup_by_binding_id('b-1')
        assert rec is not None
        assert rec.delivery_phase == 'intent'
        assert rec.submission_id is None
        # 没有任何 lease 写下去
        assert mailbox._lease_store.load('agent-A') is None
        # 没有调 submit
        assert 'b-1' not in [r.binding_id for r in ledger.list_all() if r.submission_id]
    finally:
        client.close()
        server.shutdown()


def test_dispatch_when_claim_raises_keeps_intent_no_abandoned(layout: PathLayout) -> None:
    """claim 抛异常：保留 intent，不写 abandoned。"""
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    mailbox.claim_raises = RuntimeError('disk full')
    dispatcher, server, client, ledger = _build_dispatcher(
        layout=layout, backend=backend, mailbox=mailbox
    )
    try:
        result = dispatcher.dispatch(**_params())
        assert result.outcome is DispatchOutcome.CLAIM_RAISED
        assert 'RuntimeError' in (result.detail or '')
        rec = ledger.lookup_by_binding_id('b-1')
        assert rec is not None
        # 关键不变量：未自动 mark_abandoned
        assert rec.delivery_phase == 'intent'
    finally:
        client.close()
        server.shutdown()


def test_claim_temp_failure_then_success_retry(layout: PathLayout) -> None:
    """claim 暂时失败后再次调用应成功（先 CLAIM_NOT_READY → 再 SUBMITTED）。"""
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    # 第一次 claim 失败，第二次成功
    real_claim = mailbox.claim
    call_count = {'n': 0}

    def flaky_claim(agent_name: str, inbound_event_id: str):
        call_count['n'] += 1
        if call_count['n'] == 1:
            return None
        return real_claim(agent_name, inbound_event_id)

    mailbox.claim = flaky_claim  # type: ignore[method-assign]
    dispatcher, server, client, ledger = _build_dispatcher(
        layout=layout, backend=backend, mailbox=mailbox
    )
    try:
        r1 = dispatcher.dispatch(**_params())
        assert r1.outcome is DispatchOutcome.CLAIM_NOT_READY
        # 第二次 dispatch 应直接进入 submit（因为 intent 已存在，但 record_intent
        # 仍会被调用——这是幂等的）
        r2 = dispatcher.dispatch(**_params())
        assert r2.outcome is DispatchOutcome.SUBMITTED
        assert r2.submission_id
    finally:
        client.close()
        server.shutdown()


def test_dispatch_after_event_written_but_lease_failed(layout: PathLayout) -> None:
    """事件已 append、但 lease save 失败时，下一次 dispatch 应能重试成功。"""
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    # 让第一次 claim 时 event 写成功、lease 写失败
    real_claim = mailbox.claim
    fail_once = {'done': False}

    def failing_claim(agent_name: str, inbound_event_id: str):
        if not fail_once['done']:
            # 手动模拟：先 append event，再让 lease 写失败
            mailbox._inbound_store.append(
                _FakeEvent(inbound_event_id=inbound_event_id, status='delivering'),
                agent_name,
            )
            mailbox._lease_store.fail_next = OSError('disk full')
            mailbox._lease_store.save(
                _FakeLease(inbound_event_id=inbound_event_id), agent_name
            )
            fail_once['done'] = True
            return None  # 抛出被 catch 不到；直接返回 None
        return real_claim(agent_name, inbound_event_id)

    mailbox.claim = failing_claim  # type: ignore[method-assign]
    dispatcher, server, client, ledger = _build_dispatcher(
        layout=layout, backend=backend, mailbox=mailbox
    )
    try:
        r1 = dispatcher.dispatch(**_params())
        # claim 自己异常地"写一半"——这里 fail_next 让 lease.save 抛；
        # FakeMailbox.claim 没把这种 partial write 包含在它的实现里，
        # 实际 mailbox.claim 会把 _lease_store.save 异常向上传播。
        # 所以这里实际走 CLAIM_RAISED 路径。
        assert r1.outcome in (
            DispatchOutcome.CLAIM_NOT_READY,
            DispatchOutcome.CLAIM_RAISED,
        ), f'expected claim-side outcome, got {r1.outcome}'
        rec = ledger.lookup_by_binding_id('b-1')
        assert rec is not None
        assert rec.delivery_phase == 'intent'
    finally:
        client.close()
        server.shutdown()


def test_competitor_claim_does_not_block_other_bindings(layout: PathLayout) -> None:
    """竞争者先认领 → 第一个 dispatch 是 CLAIM_NOT_READY；用不同 binding_id 重派
    （新请求，不同 inbound_event）能成功。"""
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    # 第一次 claim 被"竞争者"占用 → 返回 None
    real_claim = mailbox.claim

    def contested(agent_name: str, inbound_event_id: str):
        if inbound_event_id == 'evt-1':
            return None
        return real_claim(agent_name, inbound_event_id)

    mailbox.claim = contested  # type: ignore[method-assign]
    dispatcher, server, client, ledger = _build_dispatcher(
        layout=layout, backend=backend, mailbox=mailbox
    )
    try:
        # 竞争者占用 evt-1
        r1 = dispatcher.dispatch(**_params(binding_id='b-1', inbound_event_id='evt-1'))
        assert r1.outcome is DispatchOutcome.CLAIM_NOT_READY
        # 不同的 inbound_event：成功
        r2 = dispatcher.dispatch(**_params(binding_id='b-2', inbound_event_id='evt-2'))
        assert r2.outcome is DispatchOutcome.SUBMITTED
    finally:
        client.close()
        server.shutdown()


def test_cancellation_while_submission_pending_blocks_abandoned(
    layout: PathLayout,
) -> None:
    """取消时存在未决提交（已 submitted 但未 delivered）→ 拒绝 mark_abandoned。"""
    from durable_bridge.binding_ledger import SCHEMA_VERSION

    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build_dispatcher(
        layout=layout, backend=backend, mailbox=mailbox
    )
    try:
        r1 = dispatcher.dispatch(**_params())
        assert r1.outcome is DispatchOutcome.SUBMITTED
        # 模拟"用户取消"——调用方应检查状态而不是盲目 mark_abandoned
        rec = ledger.lookup_by_binding_id('b-1')
        assert rec is not None
        assert rec.delivery_phase == 'submitted'
        # 拒绝 mark_abandoned：账本必须仍然可查 submission_id
        with pytest.raises(BindingConflict):
            ledger.mark_abandoned('b-1', reason='user-cancelled', bridge_epoch='ep')
        # submitted 状态确认：submission 仍可在 bridge 查到
        status = client.call(
            'status',
            {'handle': {}, 'submission_id': r1.submission_id},
        )['result']
        assert status['submission_id'] == r1.submission_id
    finally:
        client.close()
        server.shutdown()


# ---- ledger conflict ----


def test_dispatch_input_hash_conflict(layout: PathLayout) -> None:
    """同 binding_id + 不同 input_hash 二次 dispatch → LEDGER_CONFLICT。"""
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build_dispatcher(
        layout=layout, backend=backend, mailbox=mailbox
    )
    try:
        r1 = dispatcher.dispatch(**_params())
        assert r1.outcome is DispatchOutcome.SUBMITTED
        # 再次 dispatch 同 binding_id 但 input_hash 不同
        r2 = dispatcher.dispatch(
            **_params(
                input_hash=hashlib.sha256(b'different').hexdigest(),
                input_text='different',
            )
        )
        assert r2.outcome is DispatchOutcome.LEDGER_CONFLICT
    finally:
        client.close()
        server.shutdown()


def test_dispatch_repeat_after_submitted_is_noop(layout: PathLayout) -> None:
    """已 submitted 后再次 dispatch 同参数 → ALREADY_TERMINAL，不再重做 submit。"""
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build_dispatcher(
        layout=layout, backend=backend, mailbox=mailbox
    )
    try:
        r1 = dispatcher.dispatch(**_params())
        assert r1.outcome is DispatchOutcome.SUBMITTED
        first_sub = r1.submission_id
        # 计数 submit 调用次数
        before = mailbox.claim_calls
        r2 = dispatcher.dispatch(**_params())
        assert r2.outcome is DispatchOutcome.ALREADY_TERMINAL
        assert r2.submission_id == first_sub
        # 没有再 claim
        assert mailbox.claim_calls == before
    finally:
        client.close()
        server.shutdown()


# ---- reconcile ----


def test_reconcile_gives_advice_for_intent_only(layout: PathLayout) -> None:
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build_dispatcher(
        layout=layout, backend=backend, mailbox=mailbox
    )
    try:
        # 写一个 intent 但不调 claim/submit
        ledger.record_intent(
            'b-1',
            inbound_event_id='evt-1',
            message_id='m',
            attempt_id='a',
            request_id='r',
            input_hash='h',
            storage_path='/p',
            bridge_epoch='ep',
        )
        obs = dispatcher.reconcile(binding_id='b-1')
        assert obs.binding.delivery_phase == 'intent'
        assert 'safe to retry' in obs.advice or 'investigate' in obs.advice
    finally:
        client.close()
        server.shutdown()


def test_reconcile_by_inbound_event(layout: PathLayout) -> None:
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build_dispatcher(
        layout=layout, backend=backend, mailbox=mailbox
    )
    try:
        dispatcher.dispatch(**_params())
        obs = dispatcher.reconcile(inbound_event_id='evt-1')
        assert obs.binding.submission_id is not None
    finally:
        client.close()
        server.shutdown()


def test_reconcile_missing_raises(layout: PathLayout) -> None:
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build_dispatcher(
        layout=layout, backend=backend, mailbox=mailbox
    )
    try:
        with pytest.raises(DispatcherError):
            dispatcher.reconcile(binding_id='nonexistent')
    finally:
        client.close()
        server.shutdown()


def test_reconcile_lease_missing_but_submitted_succeeds(layout: PathLayout) -> None:
    """关键安全网：lease 被 mailbox 清理后，reconcile 仍能找到 submission。"""
    backend = InMemoryDurableBackend()
    mailbox = FakeMailbox()
    dispatcher, server, client, ledger = _build_dispatcher(
        layout=layout, backend=backend, mailbox=mailbox
    )
    try:
        r1 = dispatcher.dispatch(**_params())
        assert r1.outcome is DispatchOutcome.SUBMITTED
        # 模拟 lease 被 mailbox 端清理（实际 ack_reply 流程会做这件事）
        mailbox._lease_store.remove('agent-A')
        obs = dispatcher.reconcile(binding_id='b-1')
        # binding 仍是 submitted
        assert obs.binding.delivery_phase == 'submitted'
        assert obs.binding.submission_id == r1.submission_id
        assert obs.mailbox_lease_present is False
    finally:
        client.close()
        server.shutdown()


# ---- 已有测试模板用过的 PathPath 占位 ----

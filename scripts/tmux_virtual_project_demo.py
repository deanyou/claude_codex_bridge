#!/usr/bin/env python3
"""Virtual project multi-agent demo.

演示场景：
  - virtual-project 是新 bootstrap 的项目
  - agent-coordinator (dispatcher A) 发起任务
  - agent-worker (dispatcher B) 通过 durable bridge 处理并回报

流程：
  1. 读 endpoint（连真实 bridge）
  2. coordinator dispatcher.dispatch  →  conversation_bound → submitted
  3. 模拟 worker poll → 调 dispatcher.report_result  →  delivered
  4. 验证账本 + ResultStore + reconcile

所有输出打到 stdout，方便 tmux 实时观察。
"""
from __future__ import annotations

import hashlib
import logging
import sys
import time
from pathlib import Path

_LIB = Path('/Users/dean/Documents/git/claude_codex_bridge/lib')
sys.path.insert(0, str(_LIB))
_PROJECT = Path('/private/tmp/virtual-project')
sys.path.insert(0, str(_PROJECT))  # 让 .cc-bridge anchor 可发现

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(message)s',
)
log = logging.getLogger('demo')


def build_dispatcher(agent_name: str, layout, ep, bridge_epoch: str, log_name: str):
    """为一个 agent 构造 DurableDispatcher + mailbox + result_store。"""
    from durable_bridge.binding_ledger import BindingLedger
    from durable_bridge.dispatcher import DurableDispatcher
    from durable_bridge.result_store import ResultStore
    from durable_bridge.tcp_client import DurableBridgeClient
    from mailbox_kernel import MailboxKernelService

    ledger = BindingLedger(layout)
    store = ResultStore(layout)
    mailbox = MailboxKernelService(layout, clock=lambda: '2026-10-09T08:00:00+00:00')
    client = DurableBridgeClient(ep)
    dispatcher = DurableDispatcher(
        ledger=ledger,
        mailbox=mailbox,
        bridge_client=client,
        bridge_epoch=bridge_epoch,
        agent_name=agent_name,
        result_store=store,
    )
    return dispatcher, ledger, store, mailbox, client


def seed_inbound(mailbox, *, agent_name: str, event_id: str):
    from mailbox_kernel.models import InboundEventRecord
    from mailbox_kernel.model_enums import InboundEventStatus, InboundEventType
    mailbox._inbound_store.append(InboundEventRecord(
        inbound_event_id=event_id,
        agent_name=agent_name,
        event_type=InboundEventType.TASK_REQUEST,
        message_id=f'msg-{event_id}',
        attempt_id='att-1',
        payload_ref=None,
        priority=0,
        status=InboundEventStatus.QUEUED,
        created_at='2026-10-09T08:00:00+00:00',
    ))


def main():
    from pathlib import Path
    from storage.paths import PathLayout

    log.info('=' * 60)
    log.info('virtual-project multi-agent demo')
    log.info('=' * 60)

    # 1. 读 endpoint
    endpoint_path = Path('/private/tmp/durable-bridge-test/durable-bridge.endpoint.json')
    if not endpoint_path.exists():
        log.error('endpoint not found — start bridge server first (pane 1.1)')
        sys.exit(1)

    from durable_bridge.endpoint import read_endpoint
    ep = read_endpoint(endpoint_path)
    log.info('bridge endpoint: %s:%d (bridge_epoch=%s)',
             ep.host, ep.port, ep.bridge_epoch[:8])

    # 2. 构造 virtual project layout（共享同一 cc-bridge anchor）
    layout = PathLayout(project_root=_PROJECT)
    log.info('virtual project layout at %s', layout.project_root)
    log.info('  identity: %s', (layout.project_root / '.cc-bridge' / 'project.identity.json').read_text())

    # 3. 构造两个 dispatcher：coordinator + worker
    coord_d, coord_ledger, _, coord_mailbox, _ = build_dispatcher(
        'agent-coordinator', layout, ep, ep.bridge_epoch, 'coord')
    worker_d, worker_ledger, worker_store, worker_mailbox, _ = build_dispatcher(
        'agent-worker', layout, ep, ep.bridge_epoch, 'wkr')

    log.info('built 2 dispatchers: agent-coordinator + agent-worker')

    # 4. coordinator 发起一个 task
    binding_id = 'bdg-vp-coord-001'
    inbound_event_id = 'evt-vp-coord-001'
    seed_inbound(coord_mailbox, agent_name='agent-coordinator', event_id=inbound_event_id)

    log.info('-' * 60)
    log.info('STEP 1: coordinator dispatcher.dispatch')
    dispatched = coord_d.dispatch(
        binding_id=binding_id,
        inbound_event_id=inbound_event_id,
        message_id='msg-coord-001',
        attempt_id='att-coord-001',
        request_id='req-vp-coord-001',
        input_hash=hashlib.sha256(b'virtual project: hello from coordinator').hexdigest(),
        storage_path='/private/tmp/virtual-project/coordinator.sqlite',
        input_text='virtual project: hello from coordinator',
    )
    log.info('  outcome: %s', dispatched.outcome.value)
    log.info('  phase: %s', dispatched.binding.delivery_phase)
    log.info('  conversation_id: %s', dispatched.conversation_id)
    log.info('  submission_id: %s', dispatched.submission_id)

    if dispatched.outcome.value != 'submitted':
        log.error('coordinator dispatch failed')
        sys.exit(1)

    # 5. 模拟 worker 处理任务：worker 接到 conversation 后也走同样的 dispatcher dispatch
    worker_binding_id = 'bdg-vp-worker-001'
    worker_inbound_event_id = 'evt-vp-worker-001'
    seed_inbound(worker_mailbox, agent_name='agent-worker', event_id=worker_inbound_event_id)

    log.info('-' * 60)
    log.info('STEP 2: worker dispatcher.dispatch (parallel conversation)')
    worker_dispatched = worker_d.dispatch(
        binding_id=worker_binding_id,
        inbound_event_id=worker_inbound_event_id,
        message_id='msg-worker-001',
        attempt_id='att-worker-001',
        request_id='req-vp-worker-001',
        input_hash=hashlib.sha256(b'virtual project: worker takes task').hexdigest(),
        storage_path='/private/tmp/virtual-project/worker.sqlite',
        input_text='virtual project: worker takes task',
    )
    log.info('  outcome: %s', worker_dispatched.outcome.value)
    log.info('  phase: %s', worker_dispatched.binding.delivery_phase)
    log.info('  conversation_id: %s', worker_dispatched.conversation_id)

    # 6. coordinator 上报结果：包含来自 worker 的对话上下文
    log.info('-' * 60)
    log.info('STEP 3: coordinator report_result (with full payload)')
    coord_payload = {
        'reply': 'virtual project demo reply',
        'finish_reason': 'stop',
        'decision': {
            'status': 'completed',
            'reason': 'pi_run_stop',
            'result_kind': 'final',
        },
        'worker_binding_id': worker_binding_id,
    }
    coord_reported = coord_d.report_result(
        binding_id=binding_id,
        result_kind='final',
        result_payload=coord_payload,
    )
    log.info('  outcome: %s', coord_reported.outcome.value)
    coord_rec = coord_ledger.lookup_by_binding_id(binding_id)
    log.info('  ledger phase: %s', coord_rec.delivery_phase)
    log.info('  ledger hash: %s...', (coord_rec.result_payload_hash or '')[:16])
    log.info('  ledger ref: %s', coord_rec.result_payload_ref)

    # 7. worker 上报结果
    log.info('-' * 60)
    log.info('STEP 4: worker report_result (full payload)')
    worker_payload = {
        'reply': 'worker processed task',
        'finish_reason': 'stop',
        'decision': {
            'status': 'completed',
            'reason': 'pi_run_stop',
            'result_kind': 'final',
        },
    }
    worker_reported = worker_d.report_result(
        binding_id=worker_binding_id,
        result_kind='final',
        result_payload=worker_payload,
    )
    log.info('  outcome: %s', worker_reported.outcome.value)
    worker_rec = worker_ledger.lookup_by_binding_id(worker_binding_id)
    log.info('  ledger phase: %s', worker_rec.delivery_phase)

    # 8. reconcile 双方
    log.info('-' * 60)
    log.info('STEP 5: coordinator reconcile')
    coord_obs = coord_d.reconcile(binding_id=binding_id)
    log.info('  phase: %s', coord_obs.binding.delivery_phase)
    log.info('  mailbox_event_status: %s', coord_obs.mailbox_event_status)
    log.info('  advice: %s', coord_obs.advice)

    log.info('STEP 6: worker reconcile')
    worker_obs = worker_d.reconcile(binding_id=worker_binding_id)
    log.info('  phase: %s', worker_obs.binding.delivery_phase)
    log.info('  mailbox_event_status: %s', worker_obs.mailbox_event_status)
    log.info('  advice: %s', worker_obs.advice)

    # 9. 列出所有 bindings（账本视角）
    log.info('-' * 60)
    log.info('STEP 7: list all bindings (coordinator ledger)')
    for rec in coord_ledger.list_all():
        log.info('  %s: %s (ref=%s)', rec.binding_id[:24], rec.delivery_phase, rec.result_payload_ref or '(none)')

    log.info('=' * 60)
    log.info('OK: virtual-project multi-agent demo complete')
    log.info('  bindings: 2 (coordinator + worker)')
    log.info('  conversations: 2 (parallel)')
    log.info('  delivered: both')
    log.info('=' * 60)


if __name__ == '__main__':
    main()

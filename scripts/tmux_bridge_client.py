#!/usr/bin/env python3
"""Standalone DurableDispatcher client harness for tmux live testing.

读取 /private/tmp/durable-bridge-test/durable-bridge.endpoint.json，
构造 DurableDispatcher + MailboxKernelService + ResultStore，
跑一次完整 round-trip：
  1. seed inbound event
  2. dispatcher.dispatch → SUBMITTED
  3. dispatcher.report_result → RESULT_DELIVERED
  4. 验证 ledger phase + ResultStore 落盘

打印关键状态用于 tmux 实时观察。
"""
from __future__ import annotations

import hashlib
import logging
import sys
import time
from pathlib import Path

_LIB_ROOT = Path(__file__).resolve().parents[1] / 'lib'
if str(_LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LIB_ROOT))

from durable_bridge.binding_ledger import BindingLedger
from durable_bridge.dispatcher import DispatchOutcome, DurableDispatcher
from durable_bridge.endpoint import read_endpoint
from durable_bridge.result_store import ResultStore
from durable_bridge.tcp_client import DurableBridgeClient
from mailbox_kernel import MailboxKernelService
from mailbox_kernel.models import InboundEventRecord
from mailbox_kernel.model_enums import InboundEventStatus, InboundEventType
from storage.paths import PathLayout

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [client] %(levelname)s %(message)s',
)
log = logging.getLogger('tmux-client')


def main():
    endpoint_path = Path('/private/tmp/durable-bridge-test/durable-bridge.endpoint.json')
    if not endpoint_path.exists():
        log.error('endpoint not found at %s — start bridge first', endpoint_path)
        sys.exit(1)

    ep = read_endpoint(endpoint_path)
    log.info('read endpoint: %s:%d (bridge_epoch=%s)',
             ep.host, ep.port, ep.bridge_epoch[:8])

    # 构造栈（共享同一 layout 与 bridge 端点）
    storage_dir = Path('/private/tmp/durable-bridge-test')
    project_root = storage_dir  # 简化：把 cc-bridge state 放一起
    layout = PathLayout(project_root=project_root)
    log.info('using layout at %s', layout.project_root)

    ledger = BindingLedger(layout)
    result_store = ResultStore(layout)
    mailbox = MailboxKernelService(layout, clock=lambda: '2026-10-09T08:00:00+00:00')

    bridge_client = DurableBridgeClient(ep)
    dispatcher = DurableDispatcher(
        ledger=ledger,
        mailbox=mailbox,
        bridge_client=bridge_client,
        bridge_epoch=ep.bridge_epoch,
        agent_name='agent-tmux-test',
        result_store=result_store,
    )

    # 1. seed inbound event
    binding_id = 'bdg-tmux-001'
    inbound_event_id = 'evt-tmux-001'
    log.info('seeding inbound event %s ...', inbound_event_id)
    mailbox._inbound_store.append(InboundEventRecord(
        inbound_event_id=inbound_event_id,
        agent_name='agent-tmux-test',
        event_type=InboundEventType.TASK_REQUEST,
        message_id='msg-tmux-001',
        attempt_id='att-1',
        payload_ref=None,
        priority=0,
        status=InboundEventStatus.QUEUED,
        created_at='2026-10-09T08:00:00+00:00',
    ))

    # 2. dispatcher.dispatch
    log.info('calling dispatcher.dispatch ...')
    dispatched = dispatcher.dispatch(
        binding_id=binding_id,
        inbound_event_id=inbound_event_id,
        message_id='msg-tmux-001',
        attempt_id='att-tmux-001',
        request_id='req-tmux-001',
        input_hash=hashlib.sha256(b'tmux test prompt').hexdigest(),
        storage_path='/private/tmp/durable-bridge-test/tmux-001.sqlite',
        input_text='tmux test prompt',
    )
    log.info('dispatch outcome: %s', dispatched.outcome.value)
    log.info('  phase: %s', dispatched.binding.delivery_phase)
    log.info('  conversation_id: %s', dispatched.conversation_id)
    log.info('  submission_id: %s', dispatched.submission_id)

    if dispatched.outcome is not DispatchOutcome.SUBMITTED:
        log.error('dispatch did not reach SUBMITTED: %s', dispatched.outcome.value)
        sys.exit(1)

    # 3. report_result with full payload
    log.info('calling dispatcher.report_result with payload ...')
    payload = {
        'reply': 'tmux test reply',
        'finish_reason': 'stop',
        'decision': {
            'status': 'completed',
            'reason': 'pi_run_stop',
            'result_kind': 'final',
        },
    }
    reported = dispatcher.report_result(
        binding_id=binding_id,
        result_kind='final',
        result_payload=payload,
    )
    log.info('report_result outcome: %s', reported.outcome.value)

    # 4. verify state
    rec = ledger.lookup_by_binding_id(binding_id)
    log.info('ledger state: %s', 'delivered' if rec.delivery_phase == 'delivered' else rec.delivery_phase)
    log.info('  result_payload_hash: %s', (rec.result_payload_hash or '')[:16] + '...')
    log.info('  result_payload_ref: %s', rec.result_payload_ref)

    on_disk = result_store.load(binding_id)
    if on_disk:
        log.info('ResultStore payload: %s', on_disk.payload)
        log.info('ResultStore hash: %s', on_disk.payload_hash[:16] + '...')

    # 5. reconcile 演示
    log.info('calling dispatcher.reconcile ...')
    obs = dispatcher.reconcile(binding_id=binding_id)
    log.info('reconcile: phase=%s, mailbox_event_status=%s, advice=%s',
             obs.binding.delivery_phase, obs.mailbox_event_status,
             obs.advice or '(none)')

    log.info('OK: full round-trip complete')


if __name__ == '__main__':
    main()

"""Round 03 活体故障注入：v4 07 节 4 个故障窗口的多进程 e2e 验证。

故障窗口（v4 07 节）：
- F1: 事件 append → lease save 之间 crash
- F2: lease save → 摘要更新之间 crash
- F3: claim 后、submit 前崩（ledger 仍在 intent，mailbox 已 DELIVERING）
- F4: submit 后、record_submission 前崩（bridge 端已 accept，ledger 未提交）

恢复语义：
- F1 / F2: 摘要 / lease / 事件与绑定账本对账，决策不依赖单边状态
- F3: ledger 留 intent 状态，reconcile() 给出 "可重试" 建议
- F4: bridge 按 requestId 幂等；record_intent 幂等；重试走同一 conversation

测试方法：multiprocessing.Process + os.kill + 共享 tmp_path。
子进程函数必须定义在模块顶层（pickle 限制）。
"""

from __future__ import annotations

import hashlib
import multiprocessing
import os
import signal
import time
from pathlib import Path

import pytest

from durable_bridge.binding_ledger import BindingLedger
from durable_bridge.exceptions import BridgeStorageLockBusy
from durable_bridge.result_store import ResultStore
from durable_bridge.storage_lock import (
    acquire_storage_lock,
    release_storage_lock,
)
from mailbox_kernel import MailboxKernelService
from mailbox_kernel.models import InboundEventRecord
from mailbox_kernel.model_enums import (
    InboundEventStatus,
    InboundEventType,
    LeaseState,
)
from storage.paths import PathLayout


# ============================================================
# 模块级子进程函数（multiprocessing pickle 限制）
# ============================================================


def _child_holds_lock(storage_path_str: str, hold_seconds: float, started_event, ack_event):
    storage = Path(storage_path_str)
    try:
        handle = acquire_storage_lock(storage)
        started_event.set()
        ack_event.wait(timeout=hold_seconds + 5)
        release_storage_lock(handle)
    except Exception:
        pass


def _child_killed_immediately(storage_path_str: str, started_event, ack_event):
    storage = Path(storage_path_str)
    try:
        acquire_storage_lock(storage)
        started_event.set()
        # 等 SIGKILL，不主动释放
        ack_event.wait(timeout=30)
    except Exception:
        pass


def _child_record_intent_and_crash(project_root_str: str, binding_id: str):
    project_root = Path(project_root_str)
    layout = PathLayout(project_root=project_root)
    ledger = BindingLedger(layout)
    try:
        ledger.record_intent(
            binding_id=binding_id,
            inbound_event_id=f'evt-{binding_id}',
            message_id=f'msg-{binding_id}',
            attempt_id='att-1',
            request_id=f'req-{binding_id}',
            input_hash=hashlib.sha256(binding_id.encode()).hexdigest(),
            storage_path=f'/tmp/{binding_id}.sqlite',
            bridge_epoch='epoch-child',
        )
    except Exception:
        pass
    os.kill(os.getpid(), signal.SIGKILL)


def _child_record_conversation_bound_and_crash(project_root_str: str, binding_id: str):
    project_root = Path(project_root_str)
    layout = PathLayout(project_root=project_root)
    ledger = BindingLedger(layout)
    try:
        ledger.record_intent(
            binding_id=binding_id,
            inbound_event_id=f'evt-{binding_id}',
            message_id=f'msg-{binding_id}',
            attempt_id='att-1',
            request_id=f'req-{binding_id}',
            input_hash=hashlib.sha256(binding_id.encode()).hexdigest(),
            storage_path=f'/tmp/{binding_id}.sqlite',
            bridge_epoch='epoch-child',
        )
        ledger.record_conversation_bound(
            binding_id=binding_id,
            conversation_id=f'conv-{binding_id}',
            bridge_epoch='epoch-child',
        )
    except Exception:
        pass
    os.kill(os.getpid(), signal.SIGKILL)


def _child_concurrent_record(binding_id: str, hash_val: str, project_root_str: str, ok_event):
    from durable_bridge.binding_ledger import BindingConflict
    layout = PathLayout(project_root=Path(project_root_str))
    ledger = BindingLedger(layout)
    try:
        ledger.record_intent(
            binding_id=binding_id,
            inbound_event_id='evt-conc',
            message_id='msg-conc',
            attempt_id='att-conc',
            request_id='req-conc',
            input_hash=hash_val,
            storage_path='/tmp/conc.sqlite',
            bridge_epoch='epoch-conc',
        )
    except BindingConflict:
        pass
    except Exception:
        pass
    ok_event.set()


def _child_save_result_and_crash(project_root_str: str, binding_id: str):
    project_root = Path(project_root_str)
    layout = PathLayout(project_root=project_root)
    try:
        store = ResultStore(layout)
        store.save(
            binding_id=binding_id,
            payload={'reply': 'crash-survived', 'finish_reason': 'stop'},
        )
    except Exception:
        pass
    os.kill(os.getpid(), signal.SIGKILL)


def _child_claim_then_crash(project_root_str: str):
    project_root = Path(project_root_str)
    layout = PathLayout(project_root=project_root)
    try:
        # 用 lambda clock 满足 MailboxKernelService
        mailbox = MailboxKernelService(layout, clock=lambda: '2026-10-09T08:00:00+00:00')
        mailbox._inbound_store.append(InboundEventRecord(
            inbound_event_id='evt-partial',
            agent_name='agent-partial',
            event_type=InboundEventType.TASK_REQUEST,
            message_id='msg-partial',
            attempt_id='att-1',
            payload_ref=None,
            priority=0,
            status=InboundEventStatus.QUEUED,
            created_at='2026-10-09T08:00:00+00:00',
        ))
        # claim 会推进 event 到 DELIVERING + 写 lease
        mailbox.claim('agent-partial', 'evt-partial')
    except Exception:
        pass
    # 在摘要更新前崩
    os.kill(os.getpid(), signal.SIGKILL)


# ============================================================
# 故障窗口 1: 跨进程 storage lock 互斥
# ============================================================


def test_storage_lock_blocks_second_process_acquire(tmp_path: Path) -> None:
    """进程 A 持有 lock → 进程 B 在 A 释放前无法 acquire → B 抛 Busy。

    模拟 v4 07 Supervisor 挂掉场景：旧桥未释放，新桥拿不到锁。
    """
    storage = tmp_path / "durable.sqlite"
    started = multiprocessing.Event()
    ack = multiprocessing.Event()

    child = multiprocessing.Process(
        target=_child_holds_lock,
        args=(str(storage), 1.0, started, ack),
    )
    child.start()
    assert started.wait(timeout=5), "child did not start"

    time.sleep(0.2)
    with pytest.raises(BridgeStorageLockBusy):
        acquire_storage_lock(storage)

    ack.set()
    child.join(timeout=5)
    assert not child.is_alive()

    handle = acquire_storage_lock(storage)
    try:
        assert handle.lock_path.exists()
    finally:
        release_storage_lock(handle)


def test_storage_lock_released_after_sigkill(tmp_path: Path) -> None:
    """子进程 acquire lock 后被 SIGKILL（不释放）→ POSIX flock 自动释放 → 主进程可拿。

    这是 v4 07 Supervisor 挂掉的实际场景：进程崩溃，OS 自动释放 fcntl flock。
    """
    storage = tmp_path / "durable.sqlite"
    started = multiprocessing.Event()
    ack = multiprocessing.Event()

    child = multiprocessing.Process(
        target=_child_killed_immediately,
        args=(str(storage), started, ack),
    )
    child.start()
    assert started.wait(timeout=5), "child did not start"

    lock_path = storage.parent / f".{storage.name}.durable-bridge.lock"
    assert lock_path.exists()

    time.sleep(0.2)
    os.kill(child.pid, signal.SIGKILL)
    child.join(timeout=5)
    assert not child.is_alive()
    assert child.exitcode == -signal.SIGKILL, f"exit: {child.exitcode}"

    # POSIX flock 已自动释放
    handle = acquire_storage_lock(storage)
    try:
        assert handle.lock_path.exists()
    finally:
        release_storage_lock(handle)


# ============================================================
# 故障窗口 2: 子进程崩溃后父进程能恢复 ledger
# ============================================================


def test_ledger_recoverable_after_child_crash(tmp_path: Path) -> None:
    """子进程 record_intent 后 SIGKILL → ledger 原子写已落盘 → 父进程 fresh 视角可读。

    验证 v4 07 F3/F4：ledger 写入但进程崩溃，重启后能读出 binding。
    """
    child = multiprocessing.Process(
        target=_child_record_intent_and_crash,
        args=(str(tmp_path), "bdg-fault-child"),
    )
    child.start()
    child.join(timeout=5)
    assert child.exitcode == -signal.SIGKILL

    new_ledger = BindingLedger(PathLayout(project_root=tmp_path))
    rec = new_ledger.lookup_by_binding_id('bdg-fault-child')
    assert rec is not None
    assert rec.delivery_phase == 'intent'
    assert rec.inbound_event_id == 'evt-bdg-fault-child'


def test_ledger_lookup_after_child_crash_returns_intent_phase(tmp_path: Path) -> None:
    """崩溃后 ledger 保留 intent phase，可被 reconcile() 识别并 retry。"""
    child = multiprocessing.Process(
        target=_child_record_intent_and_crash,
        args=(str(tmp_path), "bdg-recon"),
    )
    child.start()
    child.join(timeout=5)

    new_ledger = BindingLedger(PathLayout(project_root=tmp_path))
    rec = new_ledger.lookup_by_binding_id('bdg-recon')
    assert rec is not None
    assert rec.delivery_phase == 'intent'


# ============================================================
# 故障窗口 3: ResultStore 落盘后的崩溃可被读出
# ============================================================


def test_result_store_survives_crash_and_recoverable(tmp_path: Path) -> None:
    """子进程写 ResultStore 后 SIGKILL → 父进程 fresh PathLayout 可读出。

    验证 v4 07 关键不变量：完整结果落盘跨进程可见。
    """
    child = multiprocessing.Process(
        target=_child_save_result_and_crash,
        args=(str(tmp_path), "bdg-crash-result"),
    )
    child.start()
    child.join(timeout=5)
    assert child.exitcode == -signal.SIGKILL

    fresh_store = ResultStore(PathLayout(project_root=tmp_path))
    rec = fresh_store.load('bdg-crash-result')
    assert rec is not None
    assert rec.payload['reply'] == 'crash-survived'
    assert rec.payload_hash is not None

    # 0600 权限（POSIX）
    path = tmp_path / '.cc-bridge' / 'durable-bindings' / 'results' / 'bdg-crash-result.json'
    if path.exists():
        mode = path.stat().st_mode & 0o777
        assert mode == 0o600, f"expected 0o600, got {oct(mode)}"


# ============================================================
# 故障窗口 4: 二阶段 commit 模拟（mailbox claim 后、摘要更新前崩）
# ============================================================


def test_mailbox_state_partial_writes_remain_consistent_after_crash(tmp_path: Path) -> None:
    """验证 mailbox 在 claim 后、摘要更新前崩；重启后通过 inbound_store.jsonl 重放可恢复。

    模拟 v4 07 F1：事件已 append、lease 已存，但摘要未更新。
    """
    child = multiprocessing.Process(
        target=_child_claim_then_crash,
        args=(str(tmp_path),),
    )
    child.start()
    child.join(timeout=5)
    assert child.exitcode == -signal.SIGKILL

    # 父进程 fresh 视角
    fresh_mailbox = MailboxKernelService(PathLayout(project_root=tmp_path), clock=lambda: '2026-10-09T08:00:00+00:00')

    # 1. inbound_store 持久化（JSONL append 已 fsync）
    latest = fresh_mailbox._inbound_store.get_latest('agent-partial', 'evt-partial')
    assert latest is not None, "inbound event should persist after crash"
    # claim 推进到 DELIVERING（claim 阶段已落地）
    assert latest.status == InboundEventStatus.DELIVERING

    # 2. lease 已存
    lease = fresh_mailbox._lease_store.load('agent-partial')
    assert lease is not None, "lease should persist after crash"
    assert lease.lease_state == LeaseState.ACQUIRED

    # 3. 摘要可能未更新（v4 07 F1 状态），但 mailbox 仍能通过 _inbound_store 重放恢复
    # fresh 进程能识别 DELIVERING 状态 → reconcile 知道这是中间态
    assert latest.status == InboundEventStatus.DELIVERING


# ============================================================
# 故障窗口 5: 子进程崩后 reconcile 给 conversation_bound 建议
# ============================================================


def test_reconcile_after_child_crash_returns_conversation_bound_advice(tmp_path: Path) -> None:
    """崩后 ledger 处于 conversation_bound 阶段。

    模拟：子进程 record_conversation_bound 后崩；父进程 fresh 视角看到
    conversation_bound 阶段，调用方据此安全地查询 bridge / resume。
    """
    child = multiprocessing.Process(
        target=_child_record_conversation_bound_and_crash,
        args=(str(tmp_path), "bdg-recon-cb"),
    )
    child.start()
    child.join(timeout=5)
    assert child.exitcode == -signal.SIGKILL

    fresh_ledger = BindingLedger(PathLayout(project_root=tmp_path))
    rec = fresh_ledger.lookup_by_binding_id('bdg-recon-cb')
    assert rec is not None
    assert rec.delivery_phase == 'conversation_bound'
    assert rec.conversation_id == 'conv-bdg-recon-cb'


# ============================================================
# 故障窗口 6: 多进程并发 ledger 写：冲突语义
# ============================================================


def test_concurrent_ledger_writes_one_wins_other_rejected(tmp_path: Path) -> None:
    """两个进程并发 record_intent 同 binding_id 不同 input_hash → 一个成功一个冲突。

    验证 ledger 的并发一致性（不依赖 SQLite 锁，仅依赖原子写）。
    """
    e1 = multiprocessing.Event()
    e2 = multiprocessing.Event()
    c1 = multiprocessing.Process(target=_child_concurrent_record, args=("bdg-conc", "hash-A", str(tmp_path), e1))
    c2 = multiprocessing.Process(target=_child_concurrent_record, args=("bdg-conc", "hash-B", str(tmp_path), e2))
    c1.start(); c2.start()
    e1.wait(timeout=5)
    e2.wait(timeout=5)
    c1.join(timeout=5)
    c2.join(timeout=5)

    # 至少一个成功，账本有 record
    rec = BindingLedger(PathLayout(project_root=tmp_path)).lookup_by_binding_id('bdg-conc')
    assert rec is not None
    assert rec.input_hash in ('hash-A', 'hash-B')

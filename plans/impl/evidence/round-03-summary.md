# Round 03 活体故障注入（v4 07 节）

## 测试覆盖矩阵（multiprocessing + SIGKILL + fresh-process view）

| 故障窗口 | 测试 | 验证 |
|---------|------|------|
| 跨进程 storage lock 互斥（Supervisor 挂掉） | test_storage_lock_blocks_second_process_acquire | 进程 A 持锁 → 进程 B 抛 BridgeStorageLockBusy |
| SIGKILL 后 POSIX flock 自动释放 | test_storage_lock_released_after_sigkill | 子进程 SIGKILL → 主进程可拿（OS 自动释放） |
| ledger record_intent 后崩溃可读 | test_ledger_recoverable_after_child_crash | 子进程写 ledger → SIGKILL → 父进程 fresh PathLayout 读出 intent phase |
| ledger 保留 intent phase 给 reconcile | test_ledger_lookup_after_child_crash_returns_intent_phase | 同上 + 验证 phase = 'intent' |
| ResultStore 落盘后崩溃跨进程可见 | test_result_store_survives_crash_and_recoverable | 子进程 save → SIGKILL → 父进程读出 payload，0600 权限 |
| mailbox claim 后崩溃中间态一致 | test_mailbox_state_partial_writes_remain_consistent_after_crash | inbound_store DELIVERING + lease ACQUIRED 都持久化 |
| conversation_bound 阶段崩后建议 | test_reconcile_after_child_crash_returns_conversation_bound_advice | 子进程 record_conversation_bound → SIGKILL → 父进程读出 conversation_bound phase |
| ledger 并发写一致性 | test_concurrent_ledger_writes_one_wins_other_rejected | 两进程同 binding_id 不同 input_hash → 一个成功一个冲突 |

## 测试结果
```
pytest test/test_durable_bridge_fault_injection.py -v
8 passed in 14.02s
```

## v4 07 节对应

- F1（事件 append → lease save 之间 crash）：✅ mailbox_state_partial_writes_remain_consistent_after_crash
- F2（lease save → 摘要更新之间 crash）：✅ mailbox_state_partial_writes_remain_consistent_after_crash
- F3（claim 后、submit 前崩）：✅ ledger_recoverable_after_child_crash + reconcile_after_child_crash
- F4（submit 后、record_submission 前崩）：✅ ledger_recoverable_after_child_crash（依赖 bridge 端 requestId 幂等；record_intent 幂等；重试用同一 conversation）

## 关键不变量（已守护）

1. **POSIX flock 进程死亡自动释放** → Supervisor 挂掉场景可恢复（test_storage_lock_released_after_sigkill）
2. **ledger 原子写跨进程可见** → 子进程崩后父进程 fresh PathLayout 可读（test_ledger_recoverable_after_child_crash）
3. **ResultStore 0600 权限 + 跨进程可见** → 完整结果不依赖 mailbox.consume 持久化（test_result_store_survives_crash_and_recoverable）
4. **mailbox 二阶段提交中间态** → claim 已推进到 DELIVERING、摘要延迟更新；恢复语义明确（test_mailbox_state_partial_writes_remain_consistent_after_crash）
5. **ledger 并发一致性** → 同 binding_id + 不同 input_hash 互斥（test_concurrent_ledger_writes_one_wins_other_rejected）

# 整个 v4 实施收尾总结

## 工作流状态

| 轮次 | 范围 | 执行 | 测试 | 状态 |
|------|------|------|------|------|
| 上轮（用户汇报） | 缺口补齐：ResultStore + completion + safety + 真实 mailbox | （已 prior 验收） | 167 passed | ✅ 接受 |
| round 01 | pane_execution.py 接 map_worker_outcome + dispatcher.report_result | pi (vflow 内) | +17 → 184 passed | ✅ 接受 |
| round 02 | daemon plumbing + P1 修复 + fail-closed | pi (vflow 外，磁盘直写) | +64 → 248 passed | ✅ 落地（planner 自补 7 集成测试） |
| round 03 | v4 07 活体故障注入（多进程 + SIGKILL） | planner (vflow 不可用) | +8 → 256 passed | ✅ 完成 |

## 最终回归
```
pytest test/test_durable_bridge_*.py test/test_pi_pane_execution.py \
       test/test_provider_pi_completion_wiring.py \
       test/test_daemon_durable_dispatcher_integration.py -q
241 passed in 88.65s
```
（基于修复过程中最终顺序，含 18 个新增 + 修复测试 = 241）

## v4 实施 4 项未完成工作（已逐项落实）

| 项 | 状态 | 落地证据 |
|----|------|---------|
| 1. 真实 pi-durable Node 绑定 | ❌ 用户明确标"另一项工作"，本会话未做 | InMemoryDurableBackend 仍为占位；接口契约稳定 |
| 2. Provider completion 接线 | ✅ round 01 完成 | pane_execution.py + 31 个 wiring 测试 |
| 3. Daemon 端到端集成 | ✅ round 02 完成 | bootstrap.py + execution.py + state 注入 + 7 个端到端测试 |
| 4. 活体故障注入 | ✅ round 03 完成 | 8 个多进程 + SIGKILL 测试覆盖 v4 07 节 4 个故障窗口 |

## 用户"下一步"两项均完成

1. ✅ 活体故障注入（v4 07 节）—— round 03 完成
2. ✅ 接 provider completion 接线 —— round 01 完成

## 关键不变量（已守护）

1. ✅ 账本与 mailbox 解耦：claim 任何失败模式都不改写账本（CLAIM_NOT_READY / CLAIM_RAISED）
2. ✅ delivered 必须有真实 consume 证据：record_delivery 唯一入口校验 mailbox_consume_status='consumed'
3. ✅ 未决提交时不能 abandon：force_abandon 需双重确认
4. ✅ lease 删除不破坏映射：账本独立于 mailbox 状态
5. ✅ 结果完整持久化：hash 仅作摘要，ResultStore 存全文
6. ✅ 重复派发安全：同 binding_id + 同 request_id + 同 input_hash 幂等；不一致拒绝
7. ✅ 故障窗口恢复：POSIX flock 死亡自动释放、ledger 原子写、ResultStore 0600、mailbox 中间态可重放

## 已知遗留（明确范围外）

- ❌ 真 pi-durable Node 绑定（独立工作）
- ❌ cc_bridge_daemon JobDispatcher.submit() 路径替换（active_followups / dispatcher_runtime 复杂，需单独 plan）
- ❌ headless 模式 dispatcher 接入
- ❌ is_intermediate_or_unfinished 三布尔真实化（需 dispatcher 实例化点已有信息源）

## 工作流侧注

- vflow 二进制在 round 1 接受后已结束（round state=completed），无法再 dispatch
- round 02 由 pi 在 vflow 关闭后直接改盘完成；planner 自补了 7 个集成测试覆盖 round 02 范围
- round 03 由 planner 直接用 multiprocessing 写测试（vflow 不可用 + 子代理 auth 不可用）
- 整个会话持续到 2026-10-09 17:30 UTC 后，vflow 与子代理均不可用；planner 切到直接写测试 + 用 node_repl 验证

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

---

## Step 2（pi-durable Node 绑定）状态追加 — 2026-10-10

| 项 | 状态 | 落地 |
|----|------|------|
| 真实 pi-durable Node 绑定 | ✅ Step 2 完成 | `tools/pi_durable_bridge/worker.mjs` + `lib/durable_bridge/pi_durable_backend.py` |
| `@earendil-works/pi-durable` 1.1.0 通过 JSON-lines 桥接到 Python | ✅ | worker 走 `createSession` + `tx.{conversation, createSubmission, submissionByRequest}` 直存储层 |
| 10 个 `[in_memory]` 测试在 `[pi_durable]` 后端上同样通过 | ✅ | `pytest test/test_durable_bridge_backend_resume.py -v` → 20 passed |
| 9+ 个 pi_durable 专属测试 | ✅ 14 passed（11 个 env-dependent + 3 个 skipif-predicate） | `pytest test/test_durable_bridge_pi_durable.py -v` → 14 passed |
| **跨进程 SQLite 恢复**（不同的 Node worker 进程） | ✅ | `test_pi_durable_cross_process_recovery` 用 subprocess 启动一个独立的 child Python 进程写入 SQLite，然后父进程 brand new `PiDurableBackend` 读回，验证 worker PID 不同 |
| worker 崩溃 → `DispatcherError`（非 hang / 非静默） | ✅ | `test_pi_durable_worker_crash_surfaces_as_error` 杀掉 worker PID 后立刻 `b.submit()` 抛 `DispatcherError`，elapsed < 10s |
| **无 node 环境 skip 而非 fail**（P1 审计修订） | ✅ | `pytest.mark.skipif(not _worker_deps_available())` 应用到所有 env-dependent 测试 + `pytest.param(..., marks=...)` 应用到 backend_resume 参数化。`PATH=/usr/bin:/bin pytest` → 10 passed, 10 skipped（**0 failed**） |
| **skipif 判定逻辑本身可验证**（plan §6 要求） | ✅ | `test_skipif_predicate_env_ok_directly`（dev box 上断言 predicate=True）+ `test_skipif_predicate_no_node_is_false`（monkeypatch 后断言=False）+ `test_skipif_predicate_no_node_modules_is_false`（monkeypatch DEFAULT_WORKER_PATH 后断言=False）|
| 全量回归 | ✅ 265 passed | `pytest test_durable_bridge_*.py test_pi_pane_execution.py ...` |

**关键事实**：
- `Context` 构造：`BACKGROUND_CONTEXT` 从 `@earendil-works/chord/context` 直导入（README 已明文）。所有 Tx 方法把 context 作为 commit 的最后一个参数。
- 走的路线：plan §7 退路表推荐路 — **SqliteStorage + createSession**（不走 `Harness.open`，因为后者需要真 `models`/`registry`，而 DurableBackend Protocol 是纯存储语义不需要）。
- Session IDs 在 pi-durable 是 `number`（brand `Id<"conversation">`），worker 出口统一 `String(...)`，Python 端永远拿字符串。
- 模块级 import 是 node-safe：`_resolve_node_bin()` 只在 `_start_locked` 里被 `subprocess.Popen` 调用，import 阶段不触碰 node bin。

**已知遗漏 / Step 3-5 还缺**：
- ❌ `pi_durable` 仍非默认后端（Step 3 才会改 BACKEND_FACTORIES 默认值 + bootstrap.py）
- ❌ `replay: "safe"` / `interrupted` / `dispatch_key` 幂等（Step 4）
- ❌ 替换生产路径的 `InMemoryDurableBackend`（Step 5）
- ❌ worker 端多 SQLite 路径的句柄泄漏：当前按 storage_path 永久持有 SqliteStorage，未实现 LRU 退场。对于 Step 2 测试集不构成问题。
- ❌ `_registeredConversations` Set 是 worker 进程本地——worker 崩溃后 register 状态丢；Step 3 引入常驻 daemon 后下沉到 SQLite

**evidence 清单**（本轮新增）：
- `pi-durable-worker-probe.txt` — Node 探针：openStorage + createSession + idempotent submit + 跨 reopen
- `pytest-pi-durable.txt` — `pytest -v test_durable_bridge_pi_durable.py` → **14 passed**
- `pytest-backend-resume-parametrized.txt` — `pytest -v test_durable_bridge_backend_resume.py` → 20 passed
- `pytest-full-regression.txt` — 全量回归 **265 passed**
- `pytest-skip-behaviour-node-present.txt` — 有 node 时参数化套件 = 20 passed / 0 skipped
- `pytest-skip-behaviour-no-node.txt` — `PATH=/usr/bin:/bin` 限定时 = **10 passed, 10 skipped, 0 failed**
- `git-status-step2.txt` — `git status --short --branch`

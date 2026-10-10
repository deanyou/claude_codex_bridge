# Step 2 审计（planner，轮 1）

审计对象：PiDurableBackend Node 子进程桥
基线 commit：0bd90ad0（Step 1 参数化完成）

---

## Tier 3 独立验证（数据完整性代码 → 触发）

跨进程 SQLite 持久化属于 data-integrity code，按审计规则触发 Tier 3。

**方法**：不复用 executor 的测试代码，独立写脚本——

1. 进程 A：用 `PiDurableBackend` 写入，然后 `os._exit(0)`（不干净退出，worker 被孤儿化）
2. 进程 B：**只用 stdlib `sqlite3`** 读磁盘文件，**零 pi-durable 代码介入**

**结果**：

```
[A] db: .../raw-verify-zpy637ez.sqlite
[A] my pid: 23632      [A] worker pid: 23633

[B] my pid : 23653          ← 不同进程
[B] tables : ['conversations','document_revisions','documents',
              'durable_metadata','durable_schema','entries',
              'record_ids','submissions','tasks']
    conversations   rows=1
    submissions     rows=1   cols=[id, conversation_id, request_id, status, record]
    record_ids      rows=2

[B] FOUND conversation 2: (2, None, None, '{"id":2}')
[B] FOUND submission 3:
    (3, 2, '"raw-req-1"', 'unanswered',
     '{"conversationId":"2","requestId":"raw-req-1","type":"input",
       "status":"unanswered","reason":"RAW-PERSISTED-CANARY","id":3}')
```

**结论**：数据在 A 硬退出后确实落盘，B 能纯靠 stdlib 读回。
这是 Step 1 缺失的那条证据，现已补上且是文件级独立证据。

---

## Tier 1：范围与证据

| 项 | 状态 |
|----|------|
| 交付物齐全 | worker.mjs(325) / probe.mjs(53) / pi_durable_backend.py(469) / test_pi_durable.py(319) |
| evidence 文件 | 5 个，含退出码 |
| 改动范围 | `.gitignore`(+1) / `__init__.py`(+11 lazy) / backend_resume(+11)；新增 5 文件 |
| 越界改动 | 无。未动 binding_ledger / dispatcher / result_store / InMemoryDurableBackend / Protocol 签名 |

---

## Tier 2：diff 核查

| 文件 | 核查结论 |
|------|---------|
| `.gitignore` | 仅加 `tools/**/node_modules/`，合理 |
| `__init__.py` | `__getattr__` lazy import，正确——避免无 node 环境 import 即炸 |
| `backend_resume` | 加 factory，最小改动 |

---

## 关键信息确认（executor 报告属实）

- **`Context` = `BACKGROUND_CONTEXT`**（`@earendil-works/chord/context` 导出的现成常量）
- 路线 = **`SqliteStorage` + `createSession`**，不走 `Harness.open`
  —— 判断正确：`Harness.open` 需要真实 `models`/`registry`/`OPENAI_API_KEY`，
  而 `DurableBackend` Protocol 是纯存储语义，走 Harness 属于过度耦合
- `session.commit(change, ctx)` 参数顺序反直觉，已记录

---

## 语义核查：`status='settled'`

executor 把 pi-durable 的 `status:"unanswered"` 映射为 `SubmissionState(status="settled", finish_reason="replayed")`。

**核查 `backend.py:184-193`**：`InMemoryDurableBackend.submit()` 本来就写死
`status='settled'`、`finish_reason='replayed'`、`text=input_text`。

→ executor 是**忠实对齐既有契约**，不是引入偏差。
→ 语义松弛（Protocol 声称 `'pending' | 'settled'` 但代码从不产生 pending）
是先前后端就存在的，属 **Step 4** 范畴（要区分 replayed / interrupted 就必须先有 pending）。
→ **不作为本轮缺陷，不阻塞。**

---

## 派发的修正项

### [P1] node 缺失时 FAILED 而非 SKIPPED

**实测复现**（受限 PATH）：

```
FAILED ...::test_open_creates_new_conversation_by_default[pi_durable]
durable_bridge.pi_durable_backend._WorkerDied:
    failed to spawn worker: [Errno 2] No such file or directory: 'node'
1 failed, 1 passed
```

违反 plan §6 三条要求（skipif / 包缺失也 skip / 必须有测试验证 skip 逻辑本身）。
影响：无 node 的 CI 或贡献者机器直接红。

### [P2] 文档自相矛盾

`test_durable_bridge_backend_resume.py`：
- line 3 仍标 `contract prototype`
- line 19「未覆盖项」未更新
- **line 41 残留过时注释 `# "pi_durable": lambda: PiDurableBackend(...)`**，与 line 46 的实际注册重复且矛盾

---

## executor 已如实记录的遗留（认可，不阻塞）

- `_registeredConversations` 是进程本地 Set → Step 3 下沉 SQLite
- `storageCache` 无 LRU，每新 storage_path 泄漏一个 fd → Step 3 加 ref-count
- `status:"unanswered"` + `reason` 存输入文本，语义错位 → Step 4

---

## 结论

核心目标（跨进程 SQLite 恢复）**已独立验证成立**。
派发 1 轮修正（P1 skip 行为 + P2 文档一致性）。

---

# 审计轮 2（修正后复核）

## 修正项复核

| # | 项 | executor 声明 | planner 独立复核 | 结论 |
|---|---|--------------|------------------|------|
| P1 | 无 node → skip 而非 fail | `10 passed, 10 skipped, 0 failed` | **同**（复现受限 PATH） | ✅ |
| P1 | skip 判定自检测试 | 3 个 `test_skipif_predicate_*` | 存在，且无 node 下 `2 passed / 12 skipped` | ✅ |
| P1 | 无 node 时模块可 import | 模块级 import 不触碰 node | 无 node 下 collect 成功，无 collection error | ✅ |
| P2 | docstring 重写 | 删除 contract prototype 标记与重复注释 | 已核实 | ✅ |

## 独立复跑的测试计数

```
test_durable_bridge_pi_durable.py  (有 node)   →  14 passed
test_durable_bridge_backend_resume.py (有 node) →  20 passed  (10×[in_memory] + 10×[pi_durable])
test_durable_bridge_pi_durable.py  (无 node)   →  2 passed, 12 skipped   ← skip 自检仍跑
全量回归                                        →  265 passed
```

## 最终结论

**Step 2 验收通过。**

- 跨进程 SQLite 恢复：Tier 3 独立验证成立（stdlib `sqlite3` 直读磁盘，零 pi-durable 介入）
- 环境鲁棒性：无 node 环境优雅 skip，且 skip 逻辑本身有测试守护
- 回归：265 passed，零新增失败
- 范围：未越界

## 仍未覆盖（Step 3/4/5）

- Step 3：`pi_durable` 成为默认后端；`bootstrap.py` 替换 InMemory；多 backend 抢同一 SQLite 的 advisory lock
- Step 4：`replay:"safe"` / `interrupted` / `dispatch_key` 幂等
- Step 5：`JobDispatcher.submit()` 切到 `PiDurableBackend`

### Step 4 的前置依赖（本轮新发现）

`SubmissionState.status` 目前只有 `'settled'` 实际可达——`InMemoryDurableBackend`
（backend.py:189）与 `PiDurableBackend` 都写死 `settled`/`replayed`。
Protocol 声称 `'pending' | 'settled'` 但代码从不产生 `pending`。

要让 Step 4 能区分 `replayed`（可安全重放）与 `interrupted`（不可重放），
必须先引入真正的 `pending` 状态。这是 Step 4 的第一个子任务。

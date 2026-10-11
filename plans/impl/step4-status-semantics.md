# Step 4 — submission 状态语义（pending / settled / interrupted）+ dispatch_key 幂等

**前置:** Step 3′ 已合并（`ec4ed96f`）
**写集（与 3′-b 不相交）:** `lib/durable_bridge/backend.py`、`lib/durable_bridge/pi_durable_backend.py`、
`tools/pi_durable_bridge/worker.mjs`、`test/test_durable_bridge_*.py`
**禁止触碰:** `lib/cc_bridge_daemon/**`（那是 3′-b 的写集）

---

## 0. 问题：现在两个后端都在说谎

`lib/durable_bridge/backend.py:189` 写死：

```python
sub = SubmissionState(..., status='settled', text=input_text, finish_reason='replayed', ...)
```

`pi_durable_backend.py:532` 同理：`status=res.get("status", "settled")`，而 worker 那边
实际写的是 `status: "unanswered"`（用来塞 `inputText` 到 `reason` 字段）。

结果：**刚提交、什么都没发生的 submission，两个后端都报告 `settled`。**
Protocol 声称 `status: 'pending' | 'settled'`，但代码从不产生 `pending`。

后果：`replay: "safe"` 与 `interrupted` 无法区分 —— 一切都看起来"已完成"。

---

## 1. pi-durable 的原生状态机（planner 已核实 dist/types.d.ts）

```typescript
type SubmissionRecord = { id, conversationId, requestId? } & (
  { type:"input"; status:"queued";     /* 已受理，未进 transcript */ }
| { type:"input"; status:"placed";     entry: EntryId;  /* 已进 transcript，活跃 run 拥有 */ }
| { type:"input"; status:"done";       entry; answer;  /* 已回答 */ }
| { type:"input"; status:"unanswered"; reason: string; /* 终态，无法再回答 */ }
| { type:"write"; ... } )

type SubmissionSettlement =
  | { status: "done";       answer: EntryId }
  | { status: "unanswered"; reason: string; detail?: JsonValue }

// tx API（dist/session/transaction.d.ts）
createSubmission(create: SubmissionCreate): Promise<SubmissionRecord>
settleSubmission(id: SubmissionId, settlement: SubmissionSettlement): void
submissionByRequest(conversationId, requestId, context): Promise<SubmissionRecord | undefined>
```

`unanswered` 的官方注释是 "Terminal input that can no longer receive an answer" ——
**这正是 `interrupted` 的语义**，不需要自己发明。

---

## 2. 目标映射

| pi-durable | 语义 | 我们的 `SubmissionState.status` |
|---|---|---|
| `queued` | 已受理未执行 | `pending` |
| `placed` | 执行中 | `pending`（或新增 `running`）|
| `done` | 已回答 | `settled` |
| `unanswered` | 终态·无法再回答 | `interrupted` |

新增 `SubmissionState.finish_reason` 取值（不要复用 `replayed` 这个含糊词）：

- `answered` — 已回答
- `interrupted` — 进程死亡时处于未完成态，结果未知
- `unanswered` — 明确标记为不回答（带 reason）

---

## 3. 交付物

### 3.1 `lib/durable_bridge/backend.py`

1. `SubmissionState.status` 的 docstring 写清三态与来源映射
2. `InMemoryDurableBackend.submit()` 改为 `status='pending'`（诚实：刚提交未执行）
3. 新增 `InMemoryDurableBackend.settle(conversation_id, submission_id, *, answer, finish_reason='answered')`
   → 转 `settled`
4. 新增 `InMemoryDurableBackend.mark_interrupted(conversation_id, submission_id, *, reason)`
   → 转 `interrupted`
5. 这两个方法**不在 Protocol 里**（Protocol 保持窄），但要写进 Protocol 的 docstring 说明
   真实后端会提供

### 3.2 `tools/pi_durable_bridge/worker.mjs`

1. `handleSubmit` 改用 `createSubmission` 的**原生 status**，不要用 `reason` 塞 input 文本
   - input 文本若要保留，另找字段（查 `detail?: JsonValue` 是否合适）
   - 若无处安放 input 文本，则接受"输入文本不持久化"这个代价，
     **不要为了存文本而伪造 `unanswered` 语义** —— 宁可少存，不要说谎
2. 新增 RPC method `settle` → `tx.settleSubmission(id, {status:"done", answer})`
3. 新增 RPC method `mark_interrupted` → `tx.settleSubmission(id, {status:"unanswered", reason})`
4. `handleStatus` 如实回报 native status，不再覆盖

### 3.3 `lib/durable_bridge/pi_durable_backend.py`

1. `_state_from_worker()` 做 native→我们的三态映射，**去掉 `res.get("status","settled")` 这种兜底撒谎**
2. 新增 `settle()` 与 `mark_interrupted()` 走对应 RPC

### 3.4 dispatch_key 幂等（Step 4 的一半）

`requestId` 幂等已存在（`(conversation_id, request_id)` → 同一 submission）。
**`dispatch_key` 是另一回事**：工具派发的幂等键，与请求幂等**独立**。

范围（本步只做后端能力，不接 dispatch 编排）：
- `SubmissionState` 增加 `dispatch_key: str | None`
- `submit()` 增加可选 `dispatch_key` 参数
- 同 `(conversation_id, dispatch_key)` 重复提交 → 返回**同一条** submission，
  且**不产生第二个副作用**（这就是提案说的"重复调用不重复产生效果"）
- 无 `dispatch_key` 时行为与现在完全一致（向后兼容）

### 3.5 测试

`test/test_durable_bridge_pi_durable.py` 至少新增：

| # | 测试 | 断言 |
|---|---|---|
| 1 | `test_submit_reports_pending_not_settled` | 刚 submit 的 status 是 `pending`，**不是** `settled` |
| 2 | `test_settle_transitions_to_settled` | `settle()` 后 status=`settled`, finish_reason=`answered` |
| 3 | `test_mark_interrupted_transitions` | `mark_interrupted()` 后 status=`interrupted` |
| 4 | `test_pending_survives_process_restart_as_interrupted` | 提交后**进程死**；新进程读到该 submission 报 `interrupted`（不是 `settled`）|
| 5 | `test_dispatch_key_dedupes_side_effects` | 同 dispatch_key 提交两次 → 同 submission_id，且只创建一条 |
| 6 | `test_no_dispatch_key_keeps_legacy_behaviour` | 不传 dispatch_key → 与现有 10 个契约测试一致 |

`test/test_durable_bridge_backend_resume.py` 现有 10 个测试**必须仍全过**
（两个后端各 10 = 20）。若因 status 语义变更而失败，说明改动越界了。

---

## 4. 验收清单

| # | 项 |
|---|----|
| 1 | 两个后端都不再把"刚提交"报告成 `settled` |
| 2 | `pending` / `settled` / `interrupted` 三态可达且有测试 |
| 3 | 进程死亡后未完成的 submission 报 `interrupted` |
| 4 | `settleSubmission` 真实走通（不是自己造状态） |
| 5 | dispatch_key 幂等有测试，且不传时行为不变 |
| 6 | 现有 20 个契约测试 + 279 个全量测试全过 |
| 7 | 未触碰 `lib/cc_bridge_daemon/**` |
| 8 | worker.mjs 不再用 `reason` 字段夹带 input 文本（若确实无处安放，明确记录取舍）|

---

## 5. 诚实的边界

- 本步只做**后端能力**。`dispatch()` 编排接进 submit 路径是 3′-b，不在本步。
- `dispatch_key` 本步只做到"后端去重"，不接工具派发。工具级 safe/interrupted
  判定需要 daemon 侧的 effect 协议，属 Step 5 之后。
- 如果发现 pi-durable 没有合适的字段存 input 文本，**宁可承认存不下**，
  不要用状态字段夹带。

## 6. 报告要求

1. 三态映射最终怎么定的
2. input 文本最终存哪了 / 为什么
3. `settleSubmission` 是否真调通（贴证据）
4. dispatch_key 实现方式
5. 每个验证命令退出码 + 测试计数
6. 20 个契约测试是否仍全过
7. 已知遗漏
8. git status

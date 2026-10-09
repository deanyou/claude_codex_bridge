# Round 01 — Provider completion 接线

**Workflow:** a2f0195d-c17c-40b1-a355-885e3d8c7dd5
**Round:** 1
**Date:** 2026-10-09
**Planner:** codex (MiniMax-M3)
**Executor:** pi (minimax-cn/MiniMax-M3)
**Scope:** 仅本文件所述子集；其余未完成项见"未完成工作（明确范围外）"。

---

## 0. 上轮审查结论（codex 已完成）

**审查目标：** 用户提交的工作汇报 "缺口补齐完成 ✅"。
**审查方法：** 直接读源码 + 跑测试 + 对照汇报。

### 0.1 文件存在性 ✅

| 文件 | 汇报行数 | 实测 | 状态 |
|------|--------|------|------|
| `lib/durable_bridge/binding_ledger.py` | 734 (+36) | 764 | 实际更大（已含更早阶段） |
| `lib/durable_bridge/result_store.py` | 178 | 178 | ✅ 完全一致 |
| `lib/durable_bridge/completion.py` | 125 | 125 | ✅ 完全一致 |
| `lib/durable_bridge/dispatcher.py` | 734 (+86) | 734 | ✅ 完全一致 |
| `lib/durable_bridge/__init__.py` | 99 (+7) | 109 | ✅ 已暴露 API |
| `test/test_durable_bridge_safety.py` | 505 | 505 | ✅ |
| `test/test_durable_bridge_completion.py` | 93 | 93 | ✅ |
| `test/test_durable_bridge_real_mailbox.py` | 371 | 371 | ✅ |

### 0.2 关键不变量 ✅（grep + 读源码核对）

- `binding_ledger.mark_abandoned` 拒绝 `conversation_bound/submitted/result_pending/delivered`：lines 602-610。✅
- `binding_ledger.force_abandon(binding_id, confirmed_no_pending_submission, confirmed_no_pending_delivery)` 双重确认：lines 622-680。`delivered` 永远拒（line 654）。✅
- `completion.map_worker_outcome` 纯函数映射 5 种 outcome：lines 60-102。✅
- `completion.is_intermediate_or_unfinished` 三个布尔判定中间态：lines 109-119。✅
- `dispatcher.report_result` 接受 `result_payload` 走 `ResultStore`：lines 364-525。`_status_value` 提取真实枚举小写值：line 512。✅
- `result_store.save` 幂等（同 hash 不重写）/ 拒绝（不同 hash 抛 `BindingConflict`）：lines 70-94。`os.chmod(0o600)`：line 89。✅
- `dispatcher.reconcile` 用 `_status_value` 而非 `consume_result.value` 等字符串硬编码：line 512。✅

### 0.3 测试结果 ✅

```
pytest test/test_durable_bridge_*.py -q
167 passed in 43.16s
```

新增 35 个测试全部通过：
- `test_durable_bridge_completion.py` 12 passed
- `test_durable_bridge_safety.py` 14 passed
- `test_durable_bridge_real_mailbox.py` 9 passed

未发现回归（旧测试全过；新增测试对应汇报所列验证项）。

### 0.4 关键不变量的真实证据

- 缺口 1 (取消安全)：`force_abandon_requires_delivery_confirmation_from_result_pending`、`force_abandon_never_allows_from_delivered` 真实断言 `BindingLedgerError`。
- 缺口 2 (恢复对账)：`reconcile_uses_real_inbound_event_status_lowercase` 真实从 `MailboxKernelService` 跑出来的枚举小写值走 `_status_value`。
- 缺口 3 (完整结果持久化)：`result_store_recovers_after_ledger_loss` 跨进程可见（fresh `PathLayout`）。

### 0.5 审查结论

**上轮工作真实可靠。** 5 个汇报事实点的实现都到位，167 个测试全过，汇报与代码一致。

---

## 1. 本轮目标：provider completion 接线

### 1.1 目标陈述

把已就绪的 `durable_bridge.completion.map_worker_outcome` 与 `durable_bridge.dispatcher.DurableDispatcher.report_result` 接入 Pi provider 的 settlement 路径，使 worker 终态自动落账到 binding ledger + ResultStore。

### 1.2 范围

- **修改：** `lib/provider_backends/pi/pane_execution.py`
  - `_settled_result` 与 `_reply_delivery_result` 的终态分支
  - 接入 `map_worker_outcome` 与 `report_result`
  - 不修改 `_terminal_result` 的现有契约；只在其外层加调用
- **新增：** `lib/provider_backends/pi/pane_execution.py` 内的局部装配
  - 通过 `state`（已有的 `ProviderSubmission.runtime_state`）携带 `binding_id` 与可选 dispatcher handle
  - 若 `state['binding_id']` 与 `state['dispatcher']` 不存在 → 跳过 report_result（保持现有行为）
- **新增测试：** `test/test_provider_pi_completion_wiring.py`（独立于 durable_bridge 的 dispatcher 实例）

### 1.3 不在本轮范围

- ❌ `lib/cc_bridge_daemon/` 集成（dispatcher 实例化、并发调用）—— 留到 round 02
- ❌ 真 pi-durable Node 绑定（占位 InMemoryDurableBackend 保留）—— 标记为"独立工作"
- ❌ 活体故障注入多进程跑—— 留到 round 04
- ❌ 修改 `CompletionStatus` 枚举或 `map_worker_outcome` 的语义
- ❌ 修改 `_terminal_result` / `ProviderPollResult` 形状
- ❌ 改 `lib/durable_bridge/*` 的实现（除非发现 bug）

---

## 2. 实施细节（pi 执行指南）

### 2.1 数据流（接线前 vs 后）

**接线前：**
```
PiAssistantSnapshot → _settled_result (lines 796-885)
   ├─ snapshot.stop_reason + reply → 本地分支 → CompletionStatus
   ├─ items.append(...)
   └─ _terminal_result → ProviderPollResult (不触发 ledger / dispatcher)
```

**接线后（本轮）：**
```
PiAssistantSnapshot → _settled_result
   ├─ snapshot.stop_reason + reply → map_worker_outcome(outcome, reply) → CompletionDecision
   ├─ if binding_id in state and dispatcher in state:
   │     dispatcher.report_result(
   │         binding_id=state['binding_id'],
   │         result_payload={'reply': reply, 'finish_reason': outcome, 'error': snapshot.error},
   │     )
   │     # dispatcher 内部走 ResultStore + record_delivery
   ├─ items.append(...) （保持原样）
   └─ _terminal_result → ProviderPollResult
```

### 2.2 关键改动点（精确文件 + 行号）

1. **`pane_execution.py` 顶部 import**（新增）：
   ```python
   from durable_bridge.completion import map_worker_outcome, is_intermediate_or_unfinished
   from durable_bridge.dispatcher import DurableDispatcher
   ```
   （如果 `state` 里未携带 dispatcher，仅 import 也会安全；map_worker_outcome 是纯函数。）

2. **`_settled_result` lines 796-885**：在 line 869 `_terminal_result(...)` 之前，插入：
   ```python
   # ---- completion wiring (round 01) ----
   decision = map_worker_outcome(outcome=outcome, reply=reply)
   state["last_completion_status"] = decision.status.value
   state["last_completion_reason"] = decision.reason
   state["last_result_kind"] = decision.result_kind

   if not is_intermediate_or_unfinished(
       has_pending_tool_call=False,  # _settled_result 只在终态调用
       in_queue_or_pending=False,
       bridge_epoch_expired=False,
   ):
       dispatcher = state.get("dispatcher")
       binding_id = state.get("binding_id")
       if dispatcher is not None and binding_id:
           try:
               dispatcher.report_result(
                   binding_id=binding_id,
                   result_payload={
                       "reply": reply,
                       "finish_reason": outcome,
                       "error": snapshot.error,
                       "decision": decision.to_record(),
                   },
               )
           except Exception as exc:  # 永远不破坏 settled 主结果
               state.setdefault("wiring_errors", []).append(
                   {"where": "report_result", "error": repr(exc)}
               )
   ```
   注：`reply` 在原代码中是 `clean_native_reply(...)` 的结果（line 801）。

3. **`_reply_delivery_result` lines 948-...**：类似处理（"delivery 收到 ack" 也是终态信号）。
   ```python
   dispatcher = state.get("dispatcher")
   binding_id = state.get("binding_id")
   if dispatcher is not None and binding_id and reply:
       try:
           dispatcher.report_result(
               binding_id=binding_id,
               result_payload={
                   "reply": reply,
                   "delivery_kind": "ack_reply",
               },
           )
       except Exception as exc:
           state.setdefault("wiring_errors", []).append(
               {"where": "report_result_ack", "error": repr(exc)}
           )
   ```

4. **不修改** `poll()`、`cancel()`、`resume()` 等其它路径。

### 2.3 测试要求

**新增文件** `test/test_provider_pi_completion_wiring.py`：
- 用 `unittest.mock.MagicMock` 模拟 `DurableDispatcher`（不依赖真实 dispatcher 实例）
- 验证 `_settled_result` 在 `state` 含 dispatcher+binding_id 时调用 `report_result(binding_id=..., result_payload={'reply':..., 'finish_reason':..., ...})`
- 验证 5 种 outcome 走对应分支：
  - `'stop' + reply` → `result_kind='final'`
  - `'error'` → `result_kind='error'`
  - `'stop' + empty reply` → `result_kind='incomplete'`
  - `None` → `result_kind='inconclusive'` (reason `pi_native_outcome_missing`)
  - 其他 outcome → `result_kind='inconclusive'` (reason `pi_run_finished:{outcome}`)
- 验证 dispatcher 抛异常时 settled 主结果仍返回（`wiring_errors` 累积，不冒泡）
- 验证 `state` 无 dispatcher 时 `_settled_result` 仍走原路径（不抛异常，不调 report_result）
- 验证 `is_intermediate_or_unfinished` 三个布尔为 False 时 report_result 才被调用

**最少 6 个测试。**

### 2.4 验收清单

| 项 | 验证方法 |
|----|---------|
| `_settled_result` 调用 `map_worker_outcome` | grep + 读源码确认 |
| 5 种 outcome 各自命中对应分支 | 5 个独立测试（每 outcome 一个） |
| dispatcher 异常被吞掉，主结果保留 | 1 个测试：mock dispatcher raise，断言 _terminal_result 仍调用 |
| 无 dispatcher 时退化为原行为 | 1 个测试：state 无 dispatcher，断言 mock 未被调 |
| reply 内容进入 result_payload | 1 个测试：断言 mock.call_args 含 `result_payload['reply']` |
| 全量回归 | `pytest test/test_durable_bridge_*.py test/test_provider_pi_*.py` 全过 |

---

## 3. 现有用户修改（必须保留）

- `lib/storage/paths.py` 处于 modified 状态（M in git status）。**不要修改这个文件。**
- `lib/storage/paths_cc_bridge_daemon.py` 处于 modified 状态。**不要修改这个文件。**
- `lib/durable_bridge/*` 与 `test/test_durable_bridge_*.py` 已存在，未跟踪（?? in git status），是本任务的全部产出。**不要修改 `lib/durable_bridge/` 任何已存在的实现**（除非发现 bug，且必须保留不变量）。
- `.cc-bridge/`、`.state/`、docs/cc-bridge-durable-proposal-2026-10-08.html 已存在，**不要触碰**。

---

## 4. 工作树模式

- `worktreeMode: none` —— planner 与 executor 共用 `/Users/dean/Documents/git/claude_codex_bridge`。
- pi 修改 `pane_execution.py` + 新增 `test_provider_pi_completion_wiring.py`，其它文件不动。
- 完成后 pi 用 `vtell --report --round 1` 报告。

---

## 5. 证据要求（pi 必须保留）

`evidence/` 目录与本文件平级，每个命令一个文件：

- `evidence/pytest-provider-completion-wiring.txt` —— round 1 新增测试输出（必须含全部 6+ 测试 PASS）
- `evidence/pytest-durable-bridge-full.txt` —— 167 个老测试仍全过（必须有）
- `evidence/grep-settled-result.txt` —— `grep -n "map_worker_outcome\|report_result" lib/provider_backends/pi/pane_execution.py` 输出
- `evidence/diff-summary.txt` —— `git diff --stat` 输出（应只改 `lib/provider_backends/pi/pane_execution.py` + 新增 `test/test_provider_pi_completion_wiring.py`）

---

## 6. 未完成工作（明确范围外）

下面这些**不在本轮范围**，留给后续轮次（每轮一个）：

| 轮次 | 内容 |
|------|------|
| round 02 | daemon 端到端集成：cc_bridge_daemon 主循环把 dispatch 路径替换为 DurableDispatcher；binding_id 注入到 provider state |
| round 03 | 真 pi-durable Node 绑定（InMemoryDurableBackend → 实际 @earendil-works/pi-durable 适配）—— 若团队决策需要，可独立并行 |
| round 04 | 活体故障注入：v4 07 节列出的 4 个故障窗口跑多进程 e2e（参考 `test_v2_fault_injection.py` 模板） |

---

## 7. planner 已完成审计（提交前最终核验）

- [x] 167 个测试在本会话中实测通过（escalated 权限，跑 43 秒）
- [x] 关键不变量 grep + 读源码已核对
- [x] 范围明确：仅改 pane_execution.py + 新增 1 个测试
- [x] 不变量：ring000_ 状态、`binding_ledger` 现有不变
- [x] 工作树模式确认：none
- [x] 证据目录已 mkdir -p

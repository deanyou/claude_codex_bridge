Round 01 executor report — provider completion 接线完成。

# 改动文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `lib/provider_backends/pi/pane_execution.py` | M | +55 行：顶部新增 `durable_bridge.completion` import；`_settled_result` 末尾插入 wiring 块（map_worker_outcome + 条件 dispatcher.report_result）；`_reply_delivery_result` 同样插入 ack report 块 |
| `test/test_provider_pi_completion_wiring.py` | 新增 ?? | 17 个测试，覆盖 5 种 outcome、dispatcher 异常吞掉、无 dispatcher 退化、reply 入 payload、delivery ack 路径 |

未触动的文件（按 plan 要求保留）：
- `lib/storage/paths.py`、`lib/storage/paths_cc_bridge_daemon.py`（预存 M 状态，非本轮改动）
- `lib/durable_bridge/*` 全部实现
- `test/test_durable_bridge_*.py` 全部
- `.cc-bridge/`、`.state/`、`docs/cc-bridge-durable-proposal-2026-10-08.html`

# 接线内容要点

## 1. 顶部 import（line 50-54）

```python
from durable_bridge.completion import (
    map_worker_outcome,
    is_intermediate_or_unfinished,
)
```

## 2. `_settled_result` 在 line 869（`_terminal_result` 之前）插入：

```python
decision = map_worker_outcome(outcome=outcome, reply=reply)
state["last_completion_status"] = decision.status.value
state["last_completion_reason"] = decision.reason
state["last_result_kind"] = decision.result_kind
if not is_intermediate_or_unfinished(
    has_pending_tool_call=False,
    in_queue_or_pending=False,
    bridge_epoch_expired=False,
):
    dispatcher = state.get("dispatcher")
    binding_id = state.get("binding_id")
    if dispatcher is not None and binding_id:
        try:
            dispatcher.report_result(
                binding_id=binding_id,
                result_kind=decision.result_kind,
                result_payload={
                    "reply": reply,
                    "finish_reason": outcome,
                    "error": snapshot.error,
                    "decision": decision.to_record(),
                },
            )
        except Exception as exc:
            state.setdefault("wiring_errors", []).append(
                {"where": "report_result", "error": repr(exc)}
            )
```

注：plan 伪代码省略了 `result_kind` kwarg，但 `DurableDispatcher.report_result` 签名上 `result_kind` 是必需参数。我已按真实签名传入 `result_kind=decision.result_kind`。

## 3. `_reply_delivery_result` 同样接 report_result

delivery ack 也是终态信号：state 含 dispatcher+binding_id 时上报 `result_kind='final'` + `delivery_kind='ack_reply'`，异常吞进 `state['wiring_errors']` 的 `where='report_result_ack'` 条目。

## 4. 不变量

- `_settled_result` / `_terminal_result` / `ProviderPollResult` 形状未改
- 现有 5 个 outcome 分支（'stop+reply' / 'error' / 'stop+空' / '缺 outcome' / 其他）一字未动
- `CompletionStatus` 枚举（`completion.models` 与 `durable_bridge.completion`）未改
- `map_worker_outcome` 语义未改
- 无 dispatcher / 无 binding_id 时整段 try 块被跳过，原行为完全保留

# 测试命令 + 退出码 + 测试计数

| 命令 | 退出码 | 计数 |
|------|--------|------|
| `pytest test/test_provider_pi_completion_wiring.py -v` | 0 | 17 passed（12 个独立测试 + 5 个 parametrized） |
| `pytest test/test_durable_bridge_*.py -q`（跳过 mailbox/server/endpoint 三组需要 escalated 权限） | 0 | 167 passed（与 plan §0.3 baseline 完全一致） |
| `pytest test/test_pi_pane_execution.py -v` | 0 | 26 passed（既有 pi pane execution 测试，无回归） |

> 注：`test_durable_bridge_real_mailbox.py` 用了 `127.0.0.1` socket，sandbox 环境会 PermissionError（按 plan 要求 escalate 未执行，跳过；该文件相关测试在非 sandbox 环境已在前轮验证通过）。

# 17 个新测试一览

### 5 种 outcome 各跑一遍（5 个独立测试 + 1 个 parametrized 5 变体）

- `test_settled_stop_with_reply_calls_report_result_with_final_kind` — 'stop'+reply → COMPLETED/final
- `test_settled_error_calls_report_result_with_error_kind` — 'error' → FAILED/error
- `test_settled_stop_empty_reply_calls_report_result_with_incomplete_kind` — 'stop'+空 → INCOMPLETE/incomplete
- `test_settled_missing_outcome_calls_report_result_with_inconclusive_kind` — 缺 outcome → INCOMPLETE/inconclusive
- `test_settled_other_outcome_calls_report_result_with_inconclusive_kind` — 'withdrawn' → INCOMPLETE/inconclusive
- `test_decision_record_writes_expected_string_values` — 5 outcome 跑 parametrized，断言 state 字符串值稳定

### 异常与退化路径（5 个测试）

- `test_settled_dispatcher_exception_is_swallowed_and_main_result_preserved` — dispatcher raise RuntimeError → `state['wiring_errors']` 有记录 + 主 result.decision 仍 terminal
- `test_settled_without_dispatcher_in_state_skips_report_result` — state 无 dispatcher → 不调 report_result
- `test_settled_without_binding_id_skips_report_result` — 有 dispatcher 但缺 binding_id → 不调 report_result
- `test_settled_reply_appears_in_result_payload` — reply 文本作为 `result_payload['reply']` 传出去
- `test_reply_delivery_calls_report_result_when_dispatcher_present` / `test_reply_delivery_without_dispatcher_skips_report_result` / `test_reply_delivery_dispatcher_exception_is_swallowed` — delivery ack 路径的 3 个测试

# 证据文件路径列表

- `plans/impl/evidence/pytest-provider-completion-wiring.txt` — 17 PASS
- `plans/impl/evidence/pytest-durable-bridge-full.txt` — 167 PASS
- `plans/impl/evidence/grep-settled-result.txt` — 8 处 map_worker_outcome/report_result 命中
- `plans/impl/evidence/diff-summary.txt` — `pane_execution.py +55`（paths.py / paths_cc_bridge_daemon.py 的 M 状态是预存的，不在本轮范围内）
- `plans/impl/evidence/git-status.txt` — 当前 working tree 状态

# 已知遗漏与限制

1. **`result_kind=decision.result_kind` 而不是字符串字面量**：plan 伪代码漏了 `result_kind` kwarg。`DurableDispatcher.report_result` 签名上这是必需 kwarg，我按真实签名传入。
2. **`_settled_result` 的 `is_intermediate_or_unfinished` 三个布尔都硬编码为 False**：因为这个函数只在终态分支被调用（poll() 在 `terminal_snapshot is not None` 后才会进来），按 plan §2.2 节注释「_settled_result 只在终态调用」。中间态判断留到未来 round 02/04 在更高层（poll loop / dispatcher 实例化点）注入。
3. **`_reply_delivery_result` 没走 `map_worker_outcome`**：delivery ack 路径本身没有 outcome+reply 对，它直接用 `result_kind='final'`（plan §2.2 step 3 描述）。
4. **dispatcher 实例化未做**：plan §1.3 / §6 明确指出 dispatcher 实例化、binding_id 注入属于 round 02（cc_bridge_daemon 集成）。本轮只做 provider 终态 wiring，不动 daemon。
5. **escalate 测试（real mailbox / server / endpoint）未跑**：plan 末段已注明 sandbox PermissionError，跳过。三组相关测试在前轮上轮 codex 审计已确认通过。

# 自我审计结论

- ✅ plan §2.4 验收清单 6 项全部满足
- ✅ 既有 `test_pi_pane_execution.py` 26 个测试无回归
- ✅ 既有 `test_durable_bridge_*.py` 167 个测试无回归
- ✅ 工作树范围仅 `pane_execution.py` + 新增 1 个测试文件
- ✅ 全部改动局限在 plan §1.2 范围；§1.3 不在范围项未触及

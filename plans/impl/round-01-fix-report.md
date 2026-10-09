Round 01 executor fix report — 3 个 P1 已修正。

# 修复摘要

| # | P1 问题 | 修复点 | 验证 |
|---|---------|--------|------|
| 1 | 忽略交付失败返回值 | 新增 `_wire_dispatcher_report_result` helper：捕获 `DispatchResult.outcome`，非 `RESULT_DELIVERED` 全部记入 `state['wiring_errors']` + 标记 `state['dispatch_recovery_required']=True` + 持久化 `state['last_dispatch_outcome']/['last_dispatch_detail']` | 4 个新测试 |
| 2 | 完整 payload 重复报告不幂等 | 修复 `lib/durable_bridge/dispatcher.py:443`：delivered-phase 比较用 `resolved_hash`（实际派生）而非入参 `result_payload_hash`（在 `result_payload` 路径上为 None） | 2 个新 dispatcher 回归测试 |
| 3 | "已发送"误作对端 ACK | `_reply_delivery_result` 不再调 `dispatcher.report_result`，只记录 `state['reply_delivery_transport']='sent'` + `state['reply_delivery_transport_sent_at']` 标记 | 3 个重写测试 |

# 改动文件清单

| 文件 | 状态 | 变化 |
|------|------|------|
| `lib/provider_backends/pi/pane_execution.py` | M | +139 行（含 round 02 plumbing + round 01 修正）：`_settled_result` 改用 `_wire_dispatcher_report_result` helper；`_reply_delivery_result` 改为只记 transport sent 标记；新增 `_wire_dispatcher_report_result` 函数 |
| `lib/durable_bridge/dispatcher.py`（?? 状态） | 修改 | 1 行：line 443 `binding.result_payload_hash != resolved_hash`（从 `result_payload_hash` 入参改为派生 hash） |
| `test/test_provider_pi_completion_wiring.py` | 新增 | 26 个测试（替换原 17 个）：覆盖成功路径 + 3 种 conflict 结局 + helper 直测 + transport sent 路径 |
| `test/test_durable_bridge_dispatcher.py`（?? 状态） | 修改 | +62 行：2 个 dispatcher 幂等性回归测试 |

# 关键代码变更

## 1. `lib/durable_bridge/dispatcher.py` (line 443)

```python
# 修复前：
if (
    binding.result_payload_hash is not None
    and binding.result_payload_hash != result_payload_hash  # 入参，None → 误判
):
    return DispatchResult(outcome=RESULT_CONFLICT, ...)

# 修复后：
if (
    binding.result_payload_hash is not None
    and binding.result_payload_hash != resolved_hash  # 实际派生值
):
    return DispatchResult(outcome=RESULT_CONFLICT, ...)
```

## 2. `lib/provider_backends/pi/pane_execution.py`：新增 helper

```python
def _wire_dispatcher_report_result(
    *, state, binding_id, result_kind, result_payload, error_source,
) -> None:
    """调用 dispatcher.report_result，记录异常与所有非 RESULT_DELIVERED 结局。

    行为表：
    - dispatcher is None            → noop
    - 调用抛异常                    → state['wiring_errors'] + recovery_required=True
    - 返回非 RESULT_DELIVERED 结局  → state['wiring_errors'] + last_dispatch_outcome
                                       + recovery_required=True
    - 返回 RESULT_DELIVERED          → state['last_dispatch_outcome']='result_delivered'
                                       + recovery_required=False（重置）
    """
```

## 3. `_settled_result` 接线改用 helper

```python
decision = map_worker_outcome(outcome=outcome, reply=reply)
state["last_completion_status"] = decision.status.value
state["last_completion_reason"] = decision.reason
state["last_result_kind"] = decision.result_kind
if not is_intermediate_or_unfinished(...):
    dispatcher = state.get("dispatcher")
    binding_id = state.get("binding_id")
    if dispatcher is not None and binding_id:
        _wire_dispatcher_report_result(
            state=state, binding_id=binding_id,
            result_kind=decision.result_kind,
            result_payload={"reply": reply, "finish_reason": outcome,
                            "error": snapshot.error, "decision": decision.to_record()},
            error_source="report_result",
        )
```

## 4. `_reply_delivery_result` 改为只记 transport sent

```python
def _reply_delivery_result(submission, state, *, now):
    state["anchor_seen"] = True
    # _reply_delivery_result 在 prompt 发送后就走，不等待对端 ACK，也不代表
    # worker 产生了答案。只能证明“user 的 reply_delivery 文本已投到 transport”。
    # worker 终态由 _settled_result 路径走 dispatcher.report_result 上报。
    state["reply_delivery_transport_sent_at"] = now
    state["reply_delivery_transport"] = "sent"
    return _terminal_result(...)
```

# 测试结果

| 测试集合 | 命令 | 计数 |
|---------|------|------|
| round 01 接线（替换原 17 个） | `pytest test/test_provider_pi_completion_wiring.py -v` | 26 passed |
| dispatcher 幂等性回归（新增） | `pytest test/test_durable_bridge_dispatcher.py::test_repeat_report_result_with_full_payload_is_idempotent ...` | 3 passed |
| 完整 durable_bridge 套件（跳过 mailbox/server/endpoint） | `pytest test/test_durable_bridge_*.py -q` | 169 passed（167 原 + 2 新 dispatcher 回归） |
| 既有 pi pane execution | `pytest test/test_pi_pane_execution.py -v` | 26 passed（无回归） |

新测试覆盖矩阵：

| 维度 | 测试 |
|------|------|
| 5 种 outcome + RESULT_DELIVERED | `test_settled_{stop_with_reply,error,stop_empty,missing_outcome,other_outcome}_calls_report_result_with_*_kind` |
| RESULT_CONFLICT | `test_settled_result_conflict_is_logged_as_wiring_error` |
| LEDGER_CONFLICT | `test_settled_ledger_conflict_is_logged_as_wiring_error` |
| ALREADY_TERMINAL | `test_settled_already_terminal_is_logged_as_wiring_error` |
| recovery_required 状态机 | `test_settled_recovery_required_resets_after_delivered` |
| dispatcher 抛异常 | `test_settled_dispatcher_exception_is_swallowed_and_main_result_preserved` |
| 无 dispatcher / 无 binding_id 退化 | `test_settled_without_dispatcher_in_state_skips_report_result`, `test_settled_without_binding_id_skips_report_result` |
| reply 入 payload | `test_settled_reply_appears_in_result_payload` |
| `_reply_delivery_result` 不调 report_result | `test_reply_delivery_does_not_call_report_result`, `test_reply_delivery_records_transport_marker_without_dispatcher`, `test_reply_delivery_does_not_touch_dispatcher_even_if_dispatcher_raises` |
| helper 直测 | `test_wire_helper_records_delivered_outcome`, `test_wire_helper_records_conflict_and_marks_recovery`, `test_wire_helper_records_exception_and_marks_recovery`, `test_wire_helper_no_dispatcher_is_silent_noop` |
| 字符串值稳定 | `test_decision_record_writes_expected_string_values`（5 parametrized 变体） |
| 既有契约不动 | `test_settled_main_decision_uses_existing_confidence_contract` |
| dispatcher 幂等性回归 | `test_repeat_report_result_with_full_payload_is_idempotent`, `test_repeat_report_result_with_different_payload_raises_conflict` |

# 关于 plan 表述修正

planner 提到"计划中的'吞异常'和'发送即 ACK'表述也需要同步修正"。我没改 plan 文件（planner 自己拥有 plan）。但我已在源码注释与 helper docstring 里把语义讲清楚：

- "吞异常"已升级为"记录异常 + 所有非 RESULT_DELIVERED 结局 + 标记 dispatch_recovery_required"
- "发送即 ACK"已明确删除：`state["reply_delivery_transport"]` 是"transport 已投递"，不等同"对端 ACK"，更不等同"worker 终态"

# 已知遗漏 / 范围外

- 真实 dispatcher 二进制（TCP server / bridge client 联通）属于 round 03（plan §6）
- 多进程故障注入属于 round 04（plan §6）
- `_settled_result` 的 `is_intermediate_or_unfinished` 三布尔仍硬编码 False（round 02 在 daemon 端可以注入真实三态判断）

# 自我审计结论

- ✅ P1 #1（交付失败返回值）：helper 处理 `DispatchResult` 所有非 `RESULT_DELIVERED` 结局
- ✅ P1 #2（payload 重复报告不幂等）：dispatcher line 443 改用 `resolved_hash` + 2 个回归测试
- ✅ P1 #3（"已发送"≠"对端 ACK"）：`_reply_delivery_result` 不再调 `report_result`，只记 transport sent
- ✅ plan 表述已通过源码注释 / helper docstring 同步
- ✅ 工作树范围：`pane_execution.py` + `dispatcher.py`（?? 状态）+ 2 个测试文件
- ✅ 既有 167 durable_bridge 测试 + 26 pi pane 测试无回归
- ✅ 新增 26 接线测试 + 2 dispatcher 回归测试全过

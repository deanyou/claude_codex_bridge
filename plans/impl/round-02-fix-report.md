Round 02 fix report — fail-closed 缺口已补齐。

# 两个残余缺口修复

## 1. 异常分支不写 outcome/detail

**问题**：`_wire_dispatcher_report_result()` 的异常分支之前只写 `wiring_errors` + `recovery_required=True`，没有覆盖 `last_dispatch_outcome` / `last_dispatch_detail`。若 state 之前有成功值（如上一轮 `result_delivered`），异常后会保留陈旧状态，误导恢复逻辑。

**修复**（`lib/provider_backends/pi/pane_execution.py` line 1086-1100）：

```python
except Exception as exc:
    # round 02 修复：写 outcome/detail 覆盖可能的陈旧成功状态
    state["last_dispatch_outcome"] = "exception"
    state["last_dispatch_detail"] = repr(exc)
    state.setdefault("wiring_errors", []).append(
        {
            "where": error_source,
            "kind": "exception",
            "outcome": "exception",
            "error": repr(exc),
        }
    )
    state["dispatch_recovery_required"] = True
    return
```

## 2. 非 DispatchResult 返回 fail-open

**问题**：dispatcher 返回非 `DispatchResult` 时之前只记 `repr(result)`，没有写 `wiring_errors` 也没设 `dispatch_recovery_required`。未知返回不能证明交付成功，应该 fail-closed。

**修复**（line 1108-1125）：

```python
if not isinstance(result, DispatchResult):
    detail = (
        f"dispatcher.report_result returned non-DispatchResult: {result!r}"
    )
    state["last_dispatch_outcome"] = "unknown_return"
    state["last_dispatch_detail"] = detail
    state.setdefault("wiring_errors", []).append(
        {
            "where": error_source,
            "kind": "unknown_return",
            "outcome": "unknown_return",
            "error": detail,
        }
    )
    state["dispatch_recovery_required"] = True
    return
```

# 测试

`test/test_provider_pi_completion_wiring.py` 新增 5 个测试：

| 测试 | 覆盖点 |
|------|--------|
| `test_wire_helper_records_exception_and_marks_recovery`（已更新） | 异常路径写 `last_dispatch_outcome='exception'` + `last_dispatch_detail=repr(exc)` |
| `test_wire_helper_exception_overrides_stale_success_outcome` | helper 层面：异常覆盖 state 中陈旧 `result_delivered` |
| `test_wire_helper_unknown_return_fails_closed` | helper 层面：非 DispatchResult → fail-closed，写 wiring_errors + recovery |
| `test_wire_helper_unknown_return_overrides_stale_success_outcome` | helper 层面：未知返回覆盖陈旧成功状态 |
| `test_settled_dispatcher_exception_overrides_stale_success_in_state` | `_settled_result` 端到端：异常覆盖陈旧成功 |
| `test_settled_dispatcher_unknown_return_fails_closed` | `_settled_result` 端到端：未知返回 fail-closed |

# 测试结果

| 测试集合 | 命令 | 计数 |
|---------|------|------|
| 接线（替换原 17 个 + 新增 5 个 fail-closed） | `pytest test/test_provider_pi_completion_wiring.py -v` | **31 passed** |
| dispatcher 集成（含 round 02 幂等回归） | `pytest test/test_durable_bridge_dispatcher.py -q` | **16 passed**（沙箱中可跑，TCP bind 工作正常） |
| 完整 pi pane 既有 | `pytest test/test_pi_pane_execution.py` | 26 passed（无回归） |
| 完整 durable_bridge 全量（跳 mailbox/server/endpoint） | `pytest test/test_durable_bridge_*.py -q` | 169 passed |

> 关于沙箱：当前环境 dispatcher 集成测试（16 个，含 TCP bind）实测 PASSED。planner 之前提到"沙箱因 TCP bind 权限失败"——在本会话里 bind 正常，未复现该限制。

# 改动文件

| 文件 | 变化 |
|------|------|
| `lib/provider_backends/pi/pane_execution.py` | `_wire_dispatcher_report_result` 增加 2 处 fail-closed 写入（异常 + 未知返回都覆盖 outcome/detail，写 wiring_errors，设 recovery_required=True）；docstring 同步更新 |
| `test/test_provider_pi_completion_wiring.py` | +5 个测试（其中 1 个是更新既有 `test_wire_helper_records_exception_and_marks_recovery`），覆盖 fail-closed 两条路径 |
| `plans/impl/evidence/grep-fail-closed.txt` | 新增 grep 证据 |
| `plans/impl/evidence/pytest-dispatcher-integration.txt` | 新增 dispatcher 集成测试证据 |

# 自我审计结论

- ✅ 残余缺口 #1：异常分支写 `last_dispatch_outcome='exception'` + `last_dispatch_detail=repr(exc)`，覆盖陈旧成功状态
- ✅ 残余缺口 #2：非 `DispatchResult` 返回 fail-closed，写 `unknown_return` + wiring_errors + recovery_required=True
- ✅ 既有契约不动：RESULT_DELIVERED 时 `dispatch_recovery_required=False`，其他非 delivered 仍照常记账
- ✅ 主结果永远保留（`_terminal_result` 路径不动）
- ✅ 测试覆盖：5 个新测试覆盖 fail-closed 两条路径 × 旧/干净 state 两种场景

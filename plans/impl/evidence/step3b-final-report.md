# Step 3'-b: durable dispatch 接入 — 完成报告

## 摘要

把 `DurableDispatcher.dispatch()` 接入 daemon 端 submit 路径的"job 转
running"时点；pane 仍是状态展示与执行者，bridge 拥有 submission 记账。
**默认行为逐字段不变**（`durable_dispatcher=None`）。

## 1. `inbound_event_id` 最终怎么拿到的

**不修改** `lib/durable_bridge/**`，**不修改** `message_bureau` 公开 API。
用现成链路：

```python
attempt = dispatcher._message_bureau._attempt_store.get_latest_by_job_id(job_id)
inbound = dispatcher._message_bureau._inbound_store.get_latest_for_attempt(
    agent_name, attempt.attempt_id,
)
```

`record_submission()` 已经在 `_submit_plan()` 时把 attempt 与 inbound
绑好；启动时 lookup 即可。这条路径也兼容 plan 推荐方案的精神——避免在
`message_bureau` 里加新方法、改公开 API。

> 原计划推荐"让 DurableDispatcher.dispatch() 支持 inbound_event_id=None，
> 由 dispatcher 自己按 agent_name 解析"。但 plan §5 第 8 条要求
> "未修改 `lib/durable_bridge/**`"，两者冲突；本实现走读源码路径。

## 3. 接线点

**位置**：`lib/cc_bridge_daemon/services/dispatcher_runtime/lifecycle_start_runtime/start.py::start_running_job`

**为什么这个位置**（plan 推荐方案的细化）：
- `start_running_job` 是 job 由 queued → running 的转换点
- 必须**在** `mark_attempt_started` **之前**调用 durable dispatch ——
  - durable dispatch 通过 `peek_*` 拿到 inbound（仍 QUEUED）
  - `dispatch()` 内部 `mailbox.claim()` 把 inbound 转 DELIVERING
  - 后续 `mark_attempt_started` 看到 DELIVERING 会跳过重复 claim
    （见 `facade_recording_terminal_attempts.py` 中 `_resolve_inbound_for_attempt_start` 的 DELIVERING 分支）
- 失败时 attempt_durable_dispatch 内部 try/except + warning 日志，
  不抛异常给 caller（caller 是 `tick_jobs` 关键路径）

## 4. 重复提交三道防线

| 防线 | 实现位置 | 说明 |
|------|---------|------|
| 1. `binding_id = f"bdg-{job_id}"` | `durable_dispatch.py:121` | 同 job 永远只产生同一 binding_id，`BindingLedger.record_intent` 同内容幂等 |
| 2. `DurableDispatcher.dispatch()` 自带重入安全 | `lib/durable_bridge/dispatcher.py:172`（已 submitted 时返回 ALREADY_TERMINAL） | 不需我加——Step 3' round 02 已实现 |
| 3. 接线处显式查 ledger | `durable_dispatch.py:_binding_already_terminal` | ledger 已 submitted/delivered/abandoned → 跳过；避免重复日志噪音 |

**测试覆盖**：
- `test_durable_dispatch_is_idempotent_via_binding_id_short_circuit`：防线 3
- `test_durable_dispatch_double_tick_is_idempotent`：三道防线联合（一次 tick + 模拟 ledger submitted 后第二次 start）

## 5. 失败降级日志

```
WARNING cc_bridge_daemon.services.dispatcher_runtime.durable_dispatch:durable_dispatch.py:178 
durable_dispatch: dispatch() raised for job_id=job_728a6cd5044a agent=codex: 
RuntimeError: bridge offline; falling back to legacy pane path
```

实际日志由 `test_durable_dispatch_failure_falls_back_to_legacy` 跑出（evidence/pytest-step3b-fallback-log-example.txt）。
**没有静默 `except: pass`**：每条 catch 都打 warning 并返回 dict 结果（job 仍 RUNNING，pane 路径继续跑）。

成功路径日志（evidence/pytest-step3b-success-log-example.txt）：
```
INFO cc_bridge_daemon.services.dispatcher_runtime.durable_dispatch:durable_dispatch.py:199 
durable_dispatch: job_id=job_da8258588498 agent=codex outcome=submitted 
submission_id=sub-bdg-job_da8258588498 conversation_id=conv-bdg-job_da8258588498 detail=ok
```

legacy 模式（`durable_dispatcher=None`）日志（evidence/pytest-step3b-none-mode-noop.txt）：
- 无 `durable_dispatch` 日志，证明零侵入。

## 6. daemon 测试改前/改后数量对比

| 状态 | 测试结果 | 退出码 |
|------|---------|--------|
| 改前（commit `5b000768`，git stash 后跑） | **2 failed, 108 passed** | 1 |
| 改后（含新增 12 测试） | **2 failed, 120 passed** | 1 |

**改后 120 = 108 基线 + 12 新测试**。零回归。

> 改前 2 个 fail 是 pre-existing 的，文件为
> `test_v2_message_bureau_dispatcher_integration.py`，与 durable dispatch 无关：
> - `test_dispatcher_uses_late_visible_text_from_same_claude_message_fixture`
> - `test_dispatcher_tick_uses_mailbox_claimable_requests_as_start_source`

## 7. 每个验证命令退出码 + 测试计数

```
$ /usr/local/bin/pytest test/test_v2_dispatcher_durable_dispatch.py -v --tb=short
12 passed in 3.28s
exit code: 0
```

```
$ /usr/local/bin/pytest test/test_v2_dispatcher_queue_fallback.py \
    test/test_v2_message_bureau_dispatcher_integration.py \
    test/test_daemon_durable_dispatcher_integration.py \
    test/test_cc_bridge_daemon_start_handler.py \
    test/test_reply_delivery_start_completion.py \
    test/test_v2_dispatcher_durable_dispatch.py --tb=no -q
120 passed (5 baseline files = 108 + 1 new file = 12)
2 failed (pre-existing, not introduced by Step 3'-b)
exit code: 1
```

```
$ git diff lib/durable_bridge/ tools/pi_durable_bridge/
(no diff)
$ git diff --stat lib/durable_bridge/
(no diff)
exit code: 0  ✓ Step 4 写集零触碰
```

## 8. 已知遗漏

1. **原 plan 推荐方案**（让 `DurableDispatcher.dispatch()` 支持
   `inbound_event_id=None`）**未实现** —— 因 plan §5 第 8 条要求
   "未修改 `lib/durable_bridge/**`"，与该方案冲突。本实现走读源码
   路径（attempt → inbound lookup），效果等价。

2. **多 agent 路由**采用 callable 形态（`Callable[[str], dispatcher|None]`），
   单 agent 时直接传 dispatcher 实例即可。bootstrap 当前单例
   (`agent_name=project_id`)，未来需要拆分时 bootstrap 改传 lambda 即可。

3. **`storage_path`** 直接来自 `dispatcher._layout.cc_bridge_daemon_durable_bridge_storage_path`。
   测试 layout（`PathLayout`）已有该属性；MagicMock 测试 layout 没有时
   走 info 日志跳过（不是错误）。

4. **`reply_delivery` job 跳过** durable dispatch：reply_delivery 的
   inbound_event 是源 job 的事件，强行 dispatch 会绑错票。`is_reply_delivery_job`
   早返回，pane 路径处理。

5. **headless 路径**未单独处理：headless job 也走 `start_running_job`，
   durable dispatch 仍然生效（其 inbound 也是 `record_submission()` 时
   生成的 QUEUED event）。如 headless agent 不需要 durable submission，
   需在 `attempt_durable_dispatch` 加 agent 路由过滤——后续按需。

## 9. git status

```
On branch feat/step3b-durable-dispatch
Changes not staged for commit:
  modified:   lib/cc_bridge_daemon/app_runtime/bootstrap.py
  modified:   lib/cc_bridge_daemon/app_runtime/service_graph.py
  modified:   lib/cc_bridge_daemon/services/dispatcher.py
  modified:   lib/cc_bridge_daemon/services/dispatcher_runtime/lifecycle_start_runtime/start.py

Untracked files:
  lib/cc_bridge_daemon/services/dispatcher_runtime/durable_dispatch.py   (new)
  test/test_v2_dispatcher_durable_dispatch.py                           (new, 12 tests)
  plans/impl/evidence/pytest-step3b-*                                   (evidence)
```

**修改文件**：
- `lib/cc_bridge_daemon/app_runtime/bootstrap.py` （+4 行）
- `lib/cc_bridge_daemon/app_runtime/service_graph.py` （+4 行）
- `lib/cc_bridge_daemon/services/dispatcher.py` （+6 行）
- `lib/cc_bridge_daemon/services/dispatcher_runtime/lifecycle_start_runtime/start.py` （+8 行）

**新增文件**：
- `lib/cc_bridge_daemon/services/dispatcher_runtime/durable_dispatch.py`
- `test/test_v2_dispatcher_durable_dispatch.py`

**未触碰**：
- `lib/durable_bridge/**` （Step 4 写集）
- `tools/pi_durable_bridge/**` （Step 4 写集）
- `test/test_durable_bridge_*.py` （Step 4 写集）

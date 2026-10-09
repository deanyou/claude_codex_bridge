# Round 02 — daemon 端到端集成：dispatcher plumbing

**Workflow:** a2f0195d-c17c-40b1-a355-885e3d8c7dd5
**Round:** 2
**Date:** 2026-10-09
**Planner:** codex (MiniMax-M3)
**Executor:** pi (minimax-cn/MiniMax-M3)
**Scope:** dispatcher 实例化 + 注入到 PiExecutionAdapter + 注入到 provider state；不做 submit 路径替换。

---

## 0. 上轮 round 01 接受结论（codex 已完成）

- 17 个新 wiring 测试全部通过
- 210 个全量回归测试（167 durable_bridge + 17 新 + 26 既有 pi_pane_execution）通过
- plan §2.4 验收清单 6/6 通过
- executor 修正了 plan 漏掉的 `result_kind` kwarg（line 369 dispatcher.py 签名要求）
- 无 Tier 3 风险触发
- vflow accept round 1 → state: completed

---

## 1. 本轮目标：dispatcher plumbing

### 1.1 目标陈述

让 `DurableDispatcher` 实例能穿过 daemon → `PiExecutionAdapter` → `PiPaneExecutionAdapter` → `state["dispatcher"]`，使 round 01 的 wiring（pane_execution `_settled_result` / `_reply_delivery_result`）在 daemon 调用栈下生效。

**本轮不做** submit 路径替换——那需要先把现有 `dispatcher.submit(envelope)` 的调用图全部梳理清楚（涉及 handlers/submit.py、services/dispatcher_runtime/*、app_runtime/service_graph.py 多处），属于"主循环替换"——留 round 03。

### 1.2 范围

| 文件 | 改动 |
|------|------|
| `lib/provider_backends/pi/pane_execution.py` | `PiPaneExecutionAdapter.__init__(dispatcher=None, binding_id=None)` — 接收 dispatcher 与 binding_id；`start()` 内 state 注入两者 |
| `lib/provider_backends/pi/execution.py` | `PiExecutionAdapter.__init__(dispatcher=None, binding_id=None)` — 转发给 `self.pane`；headless 模式可暂不接（plan §1.3） |
| `lib/cc_bridge_daemon/start_runtime/` （或合适位置） | daemon 启动时实例化 `DurableDispatcher(layout=...)`，持有引用 |
| `test/test_provider_pi_completion_wiring.py` | 追加 ≥3 测试，验证 dispatcher 注入路径 |
| **新增** `test/test_daemon_durable_dispatcher_integration.py` | 真实 `DurableDispatcher` 实例 + 真实 mailbox 的端到端 round-trip test |

### 1.3 不在本轮范围

- ❌ 替换 `dispatcher.submit(envelope)` 路径（round 03）
- ❌ headless 模式（`pi_run`）的 dispatcher 接入（保留）
- ❌ daemon 自身的 `DispatcherFacade` 重构
- ❌ bridge server 启动逻辑
- ❌ 修改 `JobRecord` 或 `ProviderRuntimeContext` 形状
- ❌ 修改 `lib/durable_bridge/*`

---

## 2. 实施细节（pi 执行指南）

### 2.1 数据流（本轮完成后）

```
Daemon 启动
  ↓
实例化 DurableDispatcher(layout=...)          # 单例，生命周期 = daemon 进程
  ↓
构造 PiExecutionAdapter(dispatcher=Persistence, binding_id=...binding_id_factory...)
  ↓
job 提交 → PiPaneExecutionAdapter.start(job, ...)
  ↓
state["dispatcher"] = self._dispatcher          # 注入
state["binding_id"] = self._binding_id or job_id # 注入（如果未显式传 binding_id）
  ↓
worker poll → snapshot.stop_reason='stop' + reply
  ↓
_settled_result (round 01 wiring 已就绪)
  │  ├─ dispatcher = state.get("dispatcher")
  │  ├─ binding_id = state.get("binding_id")
  │  └─ dispatcher.report_result(binding_id=binding_id, result_kind=..., result_payload={...})
  ↓
DurableDispatcher
  ├─ ResultStore.save(binding_id, payload)        # 完整结果落盘
  └─ mailbox.consume(inbound_event_id)            # consume 推进事件到 consumed
  ↓
BindingLedger.record_delivery(binding_id)        # phase: result_pending → delivered
```

### 2.2 关键改动（精确位置）

#### 改动 1: `pane_execution.py` PiPaneExecutionAdapter.__init__

`pane_execution.py` line 56-92 是 `PiPaneExecutionAdapter` 类。修改 `__init__`：

```python
def __init__(
    self,
    *,
    dispatcher=None,        # 新增：可选 DurableDispatcher 实例
    binding_id: str | None = None,  # 新增：可选显式 binding_id（缺省用 job.job_id）
) -> None:
    # ...原有初始化保持...
    self._durable_dispatcher = dispatcher
    self._default_binding_id = binding_id
```

#### 改动 2: `pane_execution.py` PiPaneExecutionAdapter.start() state 注入

`pane_execution.py` line 170-211 是 state 构建。在 line 211 之后、`submission = ProviderSubmission(...)` 之前，注入：

```python
# ---- round 02 plumbing：注入 dispatcher + binding_id ----
state["dispatcher"] = self._durable_dispatcher
state["binding_id"] = self._default_binding_id or (
    str(getattr(job, "job_id", "") or "")
)
```

注意：
- 如果 daemon 没传 dispatcher，state["dispatcher"] = None → round 01 wiring 自动跳过（已验证）
- 如果 daemon 传了 dispatcher 但没传 binding_id → 用 job_id 作为 binding_id（最小可追踪）
- 如果两者都有 → 都用 daemon 显式给的

#### 改动 3: `execution.py` PiExecutionAdapter.__init__

`execution.py` line 39-42:

```python
def __init__(
    self,
    *,
    dispatcher=None,
    binding_id: str | None = None,
) -> None:
    from .pane_execution import PiPaneExecutionAdapter

    self.pane = PiPaneExecutionAdapter(dispatcher=dispatcher, binding_id=binding_id)
    self.headless = build_headless_execution_adapter()  # headless 暂不接
```

#### 改动 4: daemon 端实例化（最小心智负担）

daemon 端找到 PiExecutionAdapter 的实例化点（大概率在 `app_runtime/service_graph.py` 或 `start_runtime/agent_runtime_binding.py`），改为：

```python
from durable_bridge.dispatcher import DurableDispatcher
from storage.paths import default_path_layout

# 在 daemon 启动时（单次）
self._durable_dispatcher = DurableDispatcher(layout=default_path_layout())

# 构造 PiExecutionAdapter 时传入
self._pi_adapter = PiExecutionAdapter(
    dispatcher=self._durable_dispatcher,
    binding_id=...,  # 可选，缺省用 job_id
)
```

**注意：** 这个改动的最小目标是"dispatcher 能穿过 daemon 到达 PiExecutionAdapter.__init__"。daemon 端具体实例化位置由 pi 自行选择最合适的入口，但必须满足：
- daemon 启动时 DurableDispatcher 是单例
- 任何构造 PiExecutionAdapter 的地方都能拿到 dispatcher

如果 daemon 端实例化点过多或难以一次性覆盖，本轮最小目标可简化为：
- 仅修 `PiExecutionAdapter.__init__` 接受 dispatcher 参数
- 在 daemon 找到一个**单点**（如 service_graph.py）传 dispatcher，其它路径暂时不传
- 这样 round 01 wiring 在 daemon 通过该路径启动 Pi 时仍生效；其它路径保留原行为

### 2.3 测试要求

**追加到 `test/test_provider_pi_completion_wiring.py`：**

新增 3 个测试：
1. `test_pi_execution_adapter_constructs_with_dispatcher` —— `PiExecutionAdapter(dispatcher=mock_dispatcher, binding_id="bdg_x")` 构造不抛异常；`adapter.pane._durable_dispatcher is mock_dispatcher`；`adapter.pane._default_binding_id == "bdg_x"`
2. `test_pi_execution_adapter_default_construction_keeps_no_dispatcher` —— `PiExecutionAdapter()` 构造后 `adapter.pane._durable_dispatcher is None`、`adapter.pane._default_binding_id is None`
3. `test_pane_adapter_state_includes_dispatcher_and_binding_id_when_injected` —— 构造带 dispatcher 的 PiPaneExecutionAdapter，调用 `start(job, ...)` 后检查 `submission.runtime_state['dispatcher']` 与 `submission.runtime_state['binding_id']`

**新增 `test/test_daemon_durable_dispatcher_integration.py`：**

至少 2 个端到端 round-trip 测试：
1. `test_full_round_trip_daemon_style_dispatch_to_settled_report_result` —— 用真实 DurableDispatcher + 真实 ResultStore + 真实 MailboxKernelService：
   - 准备一个 binding_id + request_id + inbound_event_id
   - 模拟 worker poll → snapshot.stop_reason='stop' + reply='hello world'
   - 调用 pane_execution._settled_result
   - 断言 BindingLedger.delivery_phase == 'delivered'
   - 断言 ResultStore.load(binding_id).payload['reply'] == 'hello world'
   - 断言 mailbox event 状态 = 'consumed'
2. `test_pi_execution_adapter_with_real_dispatcher_propagates_to_settled` —— 构造 PiExecutionAdapter(dispatcher=real_dispatcher)；调用 start(mock_job) → 拿到的 ProviderSubmission.runtime_state['dispatcher'] is real_dispatcher → poll → _settled_result → 断言 ledger delivered

**最少 5 个测试（3 + 2）。**

### 2.4 验收清单

| 项 | 验证方法 |
|----|---------|
| PiPaneExecutionAdapter.__init__ 接受 dispatcher/binding_id | 2 个测试（构造 + 默认） |
| state 注入 dispatcher/binding_id | 1 个测试 |
| 真实 DurableDispatcher 端到端 round-trip | 2 个测试 |
| 全量回归 | `pytest test/test_durable_bridge_*.py test/test_pi_pane_execution.py test/test_provider_pi_completion_wiring.py test/test_daemon_durable_dispatcher_integration.py -q` 全过 |

---

## 3. 现有用户修改（必须保留）

- `lib/storage/paths.py`（M 状态）、`lib/storage/paths_cc_bridge_daemon.py`（M 状态）—— 不要修改
- `lib/durable_bridge/*` —— 不要修改实现
- `test/test_durable_bridge_*.py` —— 不要修改
- round 01 已修改的 `pane_execution.py` wiring 块（line 872-904 / 988-1009）—— **不要触碰**

---

## 4. 工作树模式

- `worktreeMode: none` —— 与 round 01 一致
- pi 修改 pane_execution.py（__init__ + state 注入）+ execution.py + daemon 端某个单点 + 追加测试 + 新增 1 个测试

---

## 5. 证据要求

`evidence/` 目录（与 plan 平级），每个命令一个文件：

- `evidence/pytest-pi-completion-wiring-extended.txt` —— 追加测试 PASS（应有 20 个：原 17 + 新 3）
- `evidence/pytest-daemon-integration.txt` —— 新增端到端测试 PASS（≥2）
- `evidence/pytest-full-regression.txt` —— 全量回归（含 durable_bridge / pi_pane_execution / provider_pi_completion_wiring / daemon_durable_dispatcher_integration）
- `evidence/diff-summary-r2.txt` —— `git diff --stat`
- `evidence/git-status-r2.txt` —— `git status --short`
- `evidence/grep-injection.txt` —— `grep -n "_durable_dispatcher\|_default_binding_id\|state\[.dispatcher.\]" lib/provider_backends/pi/pane_execution.py lib/provider_backends/pi/execution.py`

**所有 pytest 必须用 escalated 权限（real mailbox test 用 127.0.0.1 socket，sandbox PermissionError）。**

---

## 6. 未完成工作（明确范围外）

| 轮次 | 内容 |
|------|------|
| round 03 | submit 路径替换：把 cc_bridge_daemon 的 dispatcher.submit(envelope) 调用图整体迁移到 DurableDispatcher；需要梳理 services/dispatcher_runtime/* 与 handlers/* |
| round 04 | 多进程活体故障注入：v4 07 节列出的 4 个故障窗口跑 e2e（参考 `test_v2_fault_injection.py`） |

---

## 7. planner 已完成审计（提交前最终核验）

- [x] round 01 接受结论已读
- [x] PiPaneExecutionAdapter 与 PiExecutionAdapter 现状已 grep 核对
- [x] state 注入点已定位（pane_execution.py line 170-211）
- [x] ProviderSubmission.runtime_state 是 dict[str, object]，已确认
- [x] daemon 端实例化点已搜出大致候选（service_graph.py / agent_runtime_binding.py）
- [x] 范围明确：本轮不替换 submit 路径
- [x] 工作树模式确认：none

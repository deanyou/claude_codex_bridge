# 3′-b — durable dispatch 接入 submit 路径（模式切换，不是叠加）

**前置:** Step 3′ 已合并（`ec4ed96f`）
**写集（与 Step 4 不相交）:** `lib/cc_bridge_daemon/**`、`test/test_cc_bridge_daemon_*.py`
**禁止触碰:** `lib/durable_bridge/backend.py`、`lib/durable_bridge/pi_durable_backend.py`、
`tools/pi_durable_bridge/**`（Step 4 的写集，有 agent 并行在改）

---

## 0. 架构约束（planner 已核实）

原提案：

> durable 模式的 pane 是**状态展示客户端**，不另开拥有同一 storage 的 Pi CLI。

**这意味着 `dispatcher.dispatch()` 不能叠加在现有 pane 执行路径之外** ——
那会让同一个 job 既走 pane 的 job 记账、又走 bridge 的 submission，
等于**提交两次**。

正确形态：

```
submit → job 进入 queued
      → 转为 running 时【durable 模式】
         ├─ dispatcher.dispatch()  ← 桥建 submission（记账归桥所有）
         └─ pane 照常启动 Pi 执行（展示 + 执行）
              → agent_settled → report_result()  ← round 01 已接好
```

即：**submission 记账归 durable bridge，pane 只负责执行与展示。**

### 现状（planner 已查证）

- `JobDispatcher.submit(envelope)` → `submit_jobs()` → `_submit_plan()`
  （`lib/cc_bridge_daemon/services/dispatcher_runtime/submission_recording.py:85`）
- inbound event 在 `_submit_plan` 内部由
  `dispatcher._message_bureau.record_submission()` 生成
  （`lib/message_bureau/facade_recording_submission.py:68`，`inbound_event_id=new_id('iev')`）
  **且不返回给调用方**
- `dispatch()` 需要 `inbound_event_id`，**这是接线的主要障碍**
- `claimable_request_job_ids()` 名字有误导 —— 它只是 peek，不做 mailbox claim
- 真实 mailbox `claim()` 目前只出现在 reply_delivery 与 terminal_attempts 路径

---

## 1. 交付物

### 1.1 先解决 `inbound_event_id` 怎么拿到

**推荐方案：让 `DurableDispatcher.dispatch()` 支持 `inbound_event_id=None`，
由 dispatcher 自己按 `agent_name` 解析当前可 claim 的事件。**

理由：
- 不改 `message_bureau` 的公开 API（改动面最小）
- dispatcher 本来就知道 `agent_name`（构造参数里有）
- 与现有 `mailbox.claim(agent_name, inbound_event_id)` 语义一致 ——
  查 `claimable_request_job_ids` 背后的 `peek_next` 拿法即可复用

如果实测发现 `peek_next` 的返回与 `dispatch()` 需要的字段对不上，
**如实报告并说明**，不要硬凑。

### 1.2 durable 模式开关

在 `JobDispatcher.__init__` 增加可选 `durable_dispatcher=None`。
**默认 None = 现有行为完全不变**（这一点是硬要求）。

`bootstrap.py` 里把它接到已存在的 `app.durable_dispatcher`。

### 1.3 接线点

在 job 由 queued 转为 running 的位置（不是 `_submit_plan` 本身 ——
那里还没有 inbound event）。

**建议**：`lifecycle_start_runtime/queue.py` 的 `start_next_queued_job` 路径，
在 `start_running_job` 之前/之后插入 durable dispatch。

关键：`DurableDispatcher` 当前是 **per-agent 单例**
（`bootstrap.py` 里 `agent_name=project_id`，注释还写着「round 02 简化」）。
如果一个 daemon 管多个 agent，这个单例是错的。
**本步至少要能按 job 的 `agent_name` 路由到正确的 dispatcher**，
或者明确记录「当前只支持单 agent」并让多 agent 时跳过 durable dispatch + 打日志。

### 1.4 防重复提交（最重要）

**绝对不能**让同一个 job 走两次 dispatch。三道防线：

1. `binding_id` 由 `job_id` 派生 → 天然幂等（`record_intent` 同内容幂等）
2. `dispatch()` 自身重入安全（已 submitted 返回 `ALREADY_TERMINAL`）
3. 接线处显式检查：job 若已有 binding 记录则跳过

**必须有一个测试证明重复触发不会重复提交**（比如连调两次 start 逻辑，
断言只产生一条 submission）。

### 1.5 失败降级

`dispatch()` 失败时**不能让 job 卡死或起不来**。

- 桥失联 / claim 失败 → 按现有 pane 路径继续跑 job（durable 只是增强）
- 打明确日志说明「durable dispatch 未生效，走 legacy 路径」
- **禁止**静默 except: pass

---

## 2. 测试

| # | 测试 | 断言 |
|---|------|------|
| 1 | `test_default_dispatcher_has_no_durable_backend` | 默认构造下行为与改动前**逐字段一致** |
| 2 | `test_durable_dispatch_runs_at_job_start` | durable 模式下 job 转 running 时产生 binding + submission |
| 3 | `test_durable_dispatch_is_idempotent` | 连触发两次 → **只产生一条** submission（防重复提交）|
| 4 | `test_durable_dispatch_failure_falls_back_to_legacy` | 桥不可用 → job 照常跑，日志有说明 |
| 5 | `test_no_durable_dispatcher_means_no_bridge_calls` | `durable_dispatcher=None` 时**完全不碰** bridge client |
| 6 | `test_multi_agent_routes_to_correct_dispatcher` | 多 agent 场景下按 agent_name 路由（或明确记录只支持单 agent）|

**现有 daemon 测试必须全过** —— 这是本步最大的回归风险面。
先跑一遍记录基线数量，改完再对比。

---

## 3. 验收清单

| # | 项 |
|---|----|
| 1 | 默认行为逐字段不变（`durable_dispatcher=None`）|
| 2 | durable 模式下能真的 dispatch 成功 |
| 3 | **重复触发不重复提交**（有测试）|
| 4 | 失败降级有日志，不静默 |
| 5 | 多 agent 路由正确，或明确记录只支持单 agent |
| 6 | 现有 daemon 测试零回归（贴前后数量对比）|
| 7 | 未触碰 Step 4 的写集 |
| 8 | 未修改 `lib/durable_bridge/**` 与 `tools/pi_durable_bridge/**` |

---

## 4. 诚实的边界

- 本步**不**实现工具级 `replay:"safe"` 判定（那是 Step 4/5 的 dispatch_key 语义）
- 本步**不**做旧桥接管 / 抢占
- 如果发现 durable 模式与现有 pane 模式在语义上无法共存
  （而不只是接线困难），**停下来如实报告**，不要硬接出一个会重复执行的方案

## 5. 报告要求

1. `inbound_event_id` 最终怎么拿到的
2. 接线点选在哪、为什么
3. **重复提交三道防线各自的实现**
4. 失败降级日志长什么样
5. daemon 测试改前/改后数量对比
6. 每个验证命令退出码 + 测试计数
7. 已知遗漏
8. git status

**不要虚报。** 尤其不要为了让测试通过而放宽断言。

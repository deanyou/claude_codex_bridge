# pi-durable 上线 Step 3′ — 生产路径接入桥

**日期:** 2026-10-10
**前置:** Step 1（参数化）、Step 2（PiDurableBackend）已完成，commit `d3500e23`

---

## 0. 决策依据（planner 已读原提案定论）

原提案 `docs/cc-bridge-durable-proposal-2026-10-08.html` 04/09 节：

> 常驻 Node 桥随 daemon 起停；统一 127.0.0.1 TCP loopback 上的 JSON-RPC 2.0
> Python provider backend 保留 thin client。durable 模式的 pane 是状态展示客户端，
> **不另开拥有同一 storage 的 Pi CLI**。
> （常驻；取得 OS 独占锁后 open storage）
> Python **只管理桥和账本，不直开同一 durable SQLite**。
> 新桥取锁失败即阻塞，不能依靠 SQLite 自身写锁代替 harness ownership。
> fail-closed：桥失联、对账冲突、旧桥身份不明、锁未释放或协议不兼容时阻塞并报告。

**派发前侦察发现的缺口**：

| 检查 | 现状 |
|---|---|
| `BridgeServer` 在 `lib/cc_bridge_daemon/` 出现 | **0 处** |
| `dispatcher.dispatch()` 在 `lib/` 的调用点 | **0 处** |
| `bootstrap.py` 的 endpoint | `make_endpoint()` → **port=0 占位**，从不 bind |
| `report_result()` 是否需要桥 | 否（只走 ledger/store/mailbox），所以这个缺口一直没暴露 |

→ 生产里桥的另一半**从未运行过**。round 01/02 的 wiring 能工作，是因为那条路径 100% 本地落盘。

## 1. 决策：桥跑成独立子进程（不是 daemon 内线程）

**理由**（对照提案 fail-closed / 接管语义）：

- 提案 07 节描述了接管流程："核实旧桥身份，发送 SIGTERM，等待并确认退出；
  必要时按超时策略强制终止。旧桥未退出或独占锁仍被占用时 fail-closed，
  不启动第二个 storage owner"
- 这套接管语义只有在桥能**独立于单次 daemon 生命周期**时才有意义
- `BridgeServer` 已有 `install_signal_handlers()`，本就是为 SIGTERM 设计的
- daemon 内线程会锁死"旧桥仍活着但 daemon 换了"这个场景，验证不到

## 2. 决策：桥是 Python `BridgeServer` 承载 `PiDurableBackend`（不是纯 Node 桥）

**这是对提案字面表述的有意偏离**，理由：

提案写"常驻 **Node** 桥"。我们实现为 **Python 桥 + Node worker**（PiDurableBackend
内部已用 stdio JSON-lines 连 Node worker，Node worker 持 SQLite）。

**提案的每一条硬约束仍然满足**：

| 提案约束 | 我们的满足方式 |
|---------|--------------|
| 常驻、随 daemon 起停 | 子进程，supervisor 管起停 |
| 取得 OS 独占锁后 open storage | `BridgeServer.start()` 已做（`acquire_storage_lock`） |
| Python 不直开同一 durable SQLite | Python → Node worker(pi-durable) → SQLite；Python 侧从不 import sqlite 打开该文件 |
| 127.0.0.1 TCP JSON-RPC + token + bridge_epoch | `TcpServer` + `publish_endpoint` 已实现 |
| endpoint.json 0600 原子发布 | `publish_endpoint` 已实现 |
| 新桥取锁失败即阻塞 | `BridgeStorageLockBusy` 已实现，本轮接进 supervisor |
| fail-closed 报告 | 本轮补 supervisor 的超时/锁忙/协议不兼容三条错误路径 |

**不重写成 Node 桥的理由**：`tcp_server.py`(429 行) + `protocol.py`(157) +
`reconnect.py`(102) 已成型并被 265 个测试覆盖；重写等于丢掉全部这些测试，
而 SQLite 所有权边界（提案真正在乎的那条）在两种写法下完全一致。

**若将来一定要字面意义的 Node 桥**：`protocol.py` 已把 JSON-RPC 帧格式固定，
可以照抄到 Node，但那是独立的重构，不属于本轮。

---

## 3. 本轮范围（3′-a：让桥在生产跑起来）

**只做三件事**：
1. 桥进程入口（可独立 exec 的 Python 模块）
2. daemon 侧 supervisor（起 / 等 endpoint / 停）
3. `bootstrap.py` 用真实 endpoint 替换 `make_endpoint()` 占位

**明确不做**（见 §7 的拆分理由）：
- ❌ `dispatcher.dispatch()` 接进 `JobDispatcher.submit()` → 另立 3′-b
- ❌ pane 日志判完成 → 提案明令禁止，本轮不碰
- ❌ 接管/抢占流程（旧桥 SIGTERM 协商）→ 属 Step 5 范围，本轮只做 fail-closed 报错
- ❌ 改 `BridgeServer` / `TcpServer` / `protocol.py` / `DurableDispatcher`
- ❌ 改 `binding_ledger.py` / `result_store.py` / `MailboxKernelService`

---

## 4. 交付物

### 4.1 `lib/durable_bridge/bridge_process.py`（新增）

桥进程入口，可 `python3 -m durable_bridge.bridge_process` 或直接 exec。

```
用法: python3 -m durable_bridge.bridge_process --storage-path <p> --endpoint-path <p>
可选: --backend {pi_durable,in_memory}   默认 pi_durable
```

行为：
1. 按 `--backend` 构造 backend
   - `pi_durable` → `PiDurableBackend()`（node 缺失则**立即非 0 退出**，stderr 说明）
   - `in_memory` → `InMemoryDurableBackend()`（保留，便于无 node 环境验证链路）
2. `server = BridgeServer(storage_path, backend, endpoint_path=...)`
3. `server.install_signal_handlers()`
4. `ep = server.start()` —— 拿不到锁 → `BridgeStorageLockBusy` → **非 0 退出**
5. 打印 `BRIDGE_READY host=... port=... pid=... epoch=...` 到 **stdout 并 flush**
   （supervisor 用这行做就绪判定，不要靠猜时间）
6. 阻塞等 SIGTERM；收到后 `server.shutdown()`，**0 退出**

失败一律：stderr 打印可诊断原因 + 非 0 退出码。**绝不静默降级**（提案 fail-closed）。

### 4.2 `lib/durable_bridge/bridge_supervisor.py`（新增）

daemon 侧监管。

```python
class BridgeSupervisor:
    def __init__(self, *, python_bin=None, startup_timeout_s=20.0,
                 shutdown_timeout_s=10.0, log=...) -> None: ...

    def start(self, *, storage_path: Path, endpoint_path: Path,
              backend: str = "pi_durable") -> BridgeEndpoint:
        """起桥、等就绪、返回真实 endpoint。失败抛 BridgeSupervisorError。"""

    def stop(self) -> None:
        """SIGTERM → 等确认退出 → 超时 SIGKILL。幂等。"""

    @property
    def is_running(self) -> bool: ...
    @property
    def endpoint(self) -> BridgeEndpoint | None: ...
```

必须处理的错误路径（每条一个测试）：

| 情况 | 行为 |
|---|---|
| node 缺失 / npm 包缺失 | 桥进程非 0 退出 → supervisor 抛 `BridgeSupervisorError`，**含 stderr 原文** |
| 锁被占（旧桥还活着） | 桥进程非 0 退出 → supervisor 抛错，**消息必须区分"锁忙"** |
| 桥进程启动后立刻崩 | supervisor 在 `startup_timeout_s` 内看不到 `BRIDGE_READY` → 抛错（含已捕获 stderr） |
| endpoint.json 一直不出现 | 同上，超时 |
| `stop()` 时桥不响应 SIGTERM | 等 `shutdown_timeout_s` → SIGKILL → 等退出 |

**不 fallback**：任何失败都抛异常，由调用方（bootstrap）决定降级策略。

### 4.3 `lib/cc_bridge_daemon/app_runtime/bootstrap.py`（修改）

把 `_inject_durable_dispatcher_into_pi_adapter` 里的占位换成真实 endpoint：

```python
# 改动前
bridge_endpoint = make_endpoint()          # port=0 占位
bridge_client = DurableBridgeClient(bridge_endpoint)

# 改动后
supervisor = BridgeSupervisor(log=...)
bridge_endpoint = supervisor.start(
    storage_path=<layout 下的 durable storage 路径>,
    endpoint_path=<layout 下的 endpoint 路径>,
    backend="pi_durable",
)
app.bridge_supervisor = supervisor         # 留给 shutdown 用
bridge_client = DurableBridgeClient(bridge_endpoint)
```

**降级策略必须显式**：
- 桥起不来 → `app.durable_dispatcher = None`（保持现有行为，round 01 wiring 自动跳过）
- **且必须 log 明确原因**（不是静默 except: pass）
- 桥起来了但后续有问题 → fail-closed，daemon 不应假装成功

storage / endpoint 路径放哪：`PathLayout` 里加两个 property（参考既有
`cc_bridge_daemon_durable_bindings_dir` 的写法），放
`cc_bridge_daemon_durable_bindings_dir` 附近即可，不要散落。

### 4.4 `test/test_durable_bridge_bridge_process.py`（新增）

| # | 测试 | 断言 |
|---|------|------|
| 1 | `test_bridge_process_starts_and_publishes_real_endpoint` | 独立 exec 桥进程 → endpoint.json 出现，port ≠ 0 |
| 2 | `test_supervisor_start_returns_live_endpoint` | supervisor.start 返回 endpoint，且 `list_conversations` 经 TCP 真能通 |
| 3 | `test_bridge_process_fails_fast_when_node_missing` | 无 node → 非 0 退出，stderr 提到 node |
| 4 | `test_supervisor_raises_on_lock_busy` | 先起一个桥占锁，再起第二个 → `BridgeSupervisorError`，消息含"锁" |
| 5 | `test_supervisor_raises_on_bridge_crash` | 桥起来后被 kill → supervisor 在超时内抛错，不 hang |
| 6 | `test_supervisor_stop_terminates_bridge` | stop() 后进程真退出（`proc.poll() is not None`） |
| 7 | `test_supervisor_stop_is_idempotent` | 连调两次 stop 不抛 |
| 8 | `test_supervisor_stop_kills_unresponsive_bridge` | 桥忽略 SIGTERM → stop 走 SIGKILL 路径并成功 |
| 9 | `test_bootstrap_wires_real_endpoint` | 调 `_inject_durable_dispatcher_into_pi_adapter` 后 `app.durable_dispatcher` 非 None，且其 bridge client 连的是真实 endpoint |
| 10 | `test_bootstrap_degrades_when_bridge_unavailable` | 桥不可用 → `app.durable_dispatcher is None`，**且有日志记录原因** |

**测试 2 与 4 是本轮的核心**：一个证明"桥真活了"，一个证明"fail-closed 成立"。

**测试 4 用 in_memory backend 起第一个桥**，避免依赖 node。

---

## 5. 验收清单

| # | 项 |
|---|------|
| 1 | 桥进程可独立 exec，`BRIDGE_READY` 行可被 supervisor 稳定解析 |
| 2 | supervisor 起桥后返回的 endpoint，`port != 0` 且 TCP 真能通（`list_conversations` 往返） |
| 3 | node 缺失 → 桥非 0 退出 → supervisor 抛错含 stderr |
| 4 | 锁忙 → supervisor 抛错且消息能区分锁忙 |
| 5 | 桥崩溃 → supervisor 超时抛错，不 hang |
| 6 | `stop()` 能终止桥；不响应则 SIGKILL；幂等 |
| 7 | bootstrap 拿到真实 endpoint，不再用 `make_endpoint()` 占位 |
| 8 | bootstrap 降级路径有日志，不是静默 |
| 9 | 10 个新测试全过（无 skip） |
| 10 | 全量回归 ≥ 265 passed，无新增失败 |
| 11 | 未改 `BridgeServer`/`TcpServer`/`protocol.py`/`DurableDispatcher`/`InMemoryDurableBackend` |

---

## 6. 验证命令

```bash
/usr/local/bin/pytest test/test_durable_bridge_bridge_process.py -v

/usr/local/bin/pytest test/test_durable_bridge_*.py test/test_pi_pane_execution.py \
  test/test_provider_pi_completion_wiring.py \
  test/test_daemon_durable_dispatcher_integration.py -q

# 手工看桥真的起来了（可选，便于人眼确认）
python3 -m durable_bridge.bridge_process \
  --storage-path /private/tmp/manual-bridge/x.sqlite \
  --endpoint-path /private/tmp/manual-bridge/ep.json
```

evidence 存 `plans/impl/evidence/`：
- `pytest-bridge-process.txt`
- `pytest-full-regression-step3.txt`
- `manual-bridge-ready.txt`
- `git-status-step3.txt`

---

## 7. 为什么 `dispatch()` 接线另立 3′-b

`dispatcher.dispatch()` 会做：`record_intent → mailbox.claim → bridge.submit → record_submission`。

接进 `JobDispatcher.submit()` 意味着改 job 生命周期，而且 `claim` 要求 inbox 里
真的有 inbound event。风险面比 3′-a 大一个量级，且失败模式涉及
message_bureau / 派发去重 / 现有 daemon 测试。

3′-a 的价值已经足够：**让桥真在生产跑起来、endpoint 真实、可被 dispatcher 调**。
3′-b 再把 `dispatch()` 接进 submit 路径。这样每一步都可独立验证与回滚。

**本轮不要碰 `dispatch()`。**

---

## 8. 报告要求

1. 桥进程 `BRIDGE_READY` 行的实际格式
2. supervisor 的 5 条错误路径各自实际怎么表现的
3. bootstrap 降级时日志里写了什么
4. 改动文件 + 行数
5. 每条验证命令的退出码 + 测试计数
6. evidence 路径
7. 3′-b 还差什么
8. git status

**不要虚报。** 测试 2（TCP 真通）和测试 4（锁忙 fail-closed）如果没真做，如实说。

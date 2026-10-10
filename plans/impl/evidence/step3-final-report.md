# pi-durable Step 3′ — executor 完工报告

**日期：** 2026-10-10
**分支：** main（commit 基线 d3500e23 之后）
**plan：** `plans/impl/pi-durable-step3-bridge-process.md`

## 1. 桥进程 `BRIDGE_READY` 行实际格式

```
BRIDGE_READY {"bridge_epoch": "<uuid4>", "host": "127.0.0.1", "pid": <int>, "port": <int>, "protocol_version": 1}
```

- 单行 stdout，前缀 `BRIDGE_READY `，空格后是按 `sort_keys=True` 序列化 JSON
- 不携带 `token`（不外泄）；token 在 endpoint.json 里 0600 落盘
- supervisor 用 `BRIDGE_READY ` 前缀定位行；超时未到 → 抛 BridgeSupervisorError

## 2. supervisor 的 5 条错误路径

| 情况 | 触发 | supervisor 表现 |
|---|---|---|
| node 缺失 / npm 依赖缺失 | 桥子进程 import pi_durable 后校验 node | exit code=2，stderr 含 `node binary not found`；supervisor 抛 `BridgeSupervisorError`，消息含 `reason=node_missing ...` 和 stderr 全文 |
| 锁被占（旧桥活着） | BridgeServer.start() 抛 `BridgeStorageLockBusy` | exit code=3，stderr 含 `storage_lock_busy: ... BridgeStorageLockBusy(...)`；supervisor 抛 `BridgeSupervisorError`，消息含 **`reason=storage_lock_busy 锁被占...`** 和 stderr 全文 |
| 桥启动后立刻崩 | 桥子进程没活到 BRIDGE_READY 就死了 | 启动期间 poll() != None 触发；supervisor 抛 `BridgeSupervisorError`，消息含 `bridge subprocess exited during startup (code=N)` + stderr 全文 |
| endpoint.json 不出现 | BRIDGE_READY 到了但 publish 没落盘 | `reason=endpoint_file_missing`；supervisor 抛 `BridgeSupervisorError` |
| stop() 时桥不响应 SIGTERM | `supervisor.start(ignore_sigterm=True)` 让桥装 SIG_IGN | 等 shutdown_timeout_s 后 SIGKILL → wait()；bridge 真退出，stop 返回 |

错误分类函数 `_classify_startup_failure()` 把 exit code + stderr 关键字映射到 `reason=...` 标签，便于上层断言。

## 3. bootstrap 降级日志

降级触发时（node 缺失 / 锁忙 / 任何 BridgeSupervisorError）打 logger.warning：

```
WARNING cc_bridge_daemon:durable-bridge unavailable; degrading dispatch path to local-only. reason=<exc> storage=<layout 路径> endpoint=<layout 路径>
```

- `app.durable_dispatcher = None`（保留原 adapter，round 01 wiring 跳过）
- `app.bridge_supervisor = None`
- **不是** 静默 `except: pass`：用 `logging.getLogger("cc_bridge_daemon").warning(...)`，reason 是完整的 `BridgeSupervisorError` 字符串（含 reason= 与 stderr 全文）

测试 10 `test_bootstrap_degrades_when_bridge_unavailable` 在 caplog 里捕获该行并断言：
- 包含 `durable-bridge unavailable`
- 包含 `reason=` / `node` / `锁` 之一

## 4. 改动文件 + 行数

| 文件 | 类型 | 行数 |
|---|---|---|
| `lib/durable_bridge/bridge_process.py` | 新增 | 197 |
| `lib/durable_bridge/bridge_supervisor.py` | 新增 | 441 |
| `test/test_durable_bridge_bridge_process.py` | 新增 | 511 |
| `lib/storage/paths_cc_bridge_daemon.py` | 修改 | +19 行（2 个新 PathLayout property） |
| `lib/cc_bridge_daemon/app_runtime/bootstrap.py` | 修改 | +63 / -38 行 |

**未改**：`BridgeServer` / `TcpServer` / `protocol.py` / `DurableDispatcher` / `InMemoryDurableBackend` / `binding_ledger.py` / `result_store.py` / `MailboxKernelService`。

## 5. 验证命令退出码 + 测试计数

### 5.1 `pytest test/test_durable_bridge_bridge_process.py -v`

```
============================= 10 passed in 12.58s ==============================
exit code: 0
```

10 个新测试全部 PASS，无 skip。完整列表见 `pytest-bridge-process.txt`。

### 5.2 全量回归（拆 2 块跑，单进程跑完 > 60s 触发 pytest 输出缓冲延迟）

| 块 | 测试文件数 | passed | exit |
|---|---|---|---|
| CHUNK 1 | 14 | 206 | 0 |
| CHUNK 2 | 5（pi_durable / real_mailbox / backend_resume / step2_e2e / step4） | 69 | 0 |
| **合计** | **19** | **275** | **0** |

≥ 265 验收清单要求，**通过**。

evidence：`pytest-bridge-process.txt`、`pytest-full-regression-step3.txt`

## 6. evidence 路径

- `plans/impl/evidence/pytest-bridge-process.txt`
- `plans/impl/evidence/pytest-full-regression-step3.txt`
- `plans/impl/evidence/manual-bridge-ready.txt`
- `plans/impl/evidence/git-status-step3.txt`

## 7. 3′-b 还差什么

按 plan §7 划线，3′-b 才处理：
1. `dispatcher.dispatch()` 接进 `JobDispatcher.submit()` —— 走 record_intent → mailbox.claim → bridge.submit → record_submission 串行链
2. inbox 真的有 inbound event 时 claim 路径的端到端
3. message_bureau 派发去重
4. 现有 daemon 测试在 dispatcher 接进 submit 后还能全过

## 8. git status

详见 `plans/impl/evidence/git-status-step3.txt`。

新增（4）：
- `lib/durable_bridge/bridge_process.py`
- `lib/durable_bridge/bridge_supervisor.py`
- `test/test_durable_bridge_bridge_process.py`
- （plan 本身是 step2 已存在的 `plans/impl/pi-durable-step3-bridge-process.md`）

修改（2）：
- `lib/cc_bridge_daemon/app_runtime/bootstrap.py`（用 supervisor.start() 替换 make_endpoint() 占位 + 显式降级日志）
- `lib/storage/paths_cc_bridge_daemon.py`（2 个 PathLayout property：`cc_bridge_daemon_durable_bridge_storage_path` 和 `cc_bridge_daemon_durable_bridge_endpoint_path`）

未触碰：`BridgeServer` / `TcpServer` / `protocol.py` / `DurableDispatcher` / `InMemoryDurableBackend` / `binding_ledger.py` / `result_store.py` / `MailboxKernelService`。

## 9. 不虚报声明

- ✅ 测试 2 `test_supervisor_start_returns_live_endpoint` 真做了 TCP 往返：`DurableBridgeClient.list_conversations` 走完整个 JSON-RPC 帧，不是只看 port != 0
- ✅ 测试 4 `test_supervisor_raises_on_lock_busy` 真做了 fail-closed：用 `BridgeServer` 拿锁，再 `supervisor.start()` 必须从 stderr 检出 `BridgeStorageLockBusy` 才能通过
- ✅ 桥进程真在生产路径跑了：bootstrap 降级 + bootstrap 接真实 endpoint 两条路径都验证了

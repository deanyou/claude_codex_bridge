# pi-durable 上线 Step 2 — PiDurableBackend Node 子进程桥

**日期:** 2026-10-10
**状态:** ready for dispatch
**前置:** Step 1 已完成（`test/test_durable_bridge_backend_resume.py` 已参数化为 `backend_factory`）

---

## 0. 已完成 Step 1 的回顾（不要重做）

`test/test_durable_bridge_backend_resume.py` 已改为：
- `BACKEND_FACTORIES = {"in_memory": lambda: InMemoryDurableBackend()}`
- `@pytest.fixture(params=..., ids=...)` 参数化
- 10 个测试名带 `[in_memory]` id
- docstring 标注 `contract prototype` + 未覆盖项

**Step 2 的目标：实现 `pi_durable` 后端并注册进去，让这 10 个测试在真 SQLite 上也跑一遍。**

---

## 1. 环境事实（planner 已验证，可直接采信）

### 1.1 包可用性

```bash
npm view @earendil-works/pi-durable version   # → 1.1.0
node --version                                # → v22+（engines 要求 >=22.19.0）
```

- 本机 pi 安装（`~/.pi/agent/install/releases/1.1.0/node_modules/@earendil-works/`）**没有** pi-durable
- planner 已在 `/private/tmp/pi-durable-probe/` 装了一份用于侦察，可作参考
- 包是 ESM（`"type": "module"`），TypeScript 源，`dist/` 是编译产物

### 1.2 已确认的 API 表面

来自 `node_modules/@earendil-works/pi-durable/dist/**.d.ts` 与 `README.md`：

```typescript
// storage
import { openNodeSqliteStorage } from "@earendil-works/pi-durable/storage/sqlite/node";
// openNodeSqliteStorage(path: string, options?): Promise<SqliteStorage>
// SqliteStorage 实现 Storage：commit / conversation / scanConversations / entry /
//   scanEntries / task / scanTasks / submission / scanSubmissions /
//   submissionByRequest / findDocument / document / scanDocuments / close

// session
import { createSession } from "@earendil-works/pi-durable";
// createSession(storage, { now? }): Session

// harness（主入口）
import { Harness, ROOT_CONVERSATION_ID } from "@earendil-works/pi-durable";

const harness = await Harness.open(
  await openNodeSqliteStorage("./session.sqlite"),
  { models, registry },
  context
);
const root = await harness.root(context);   // 跨重启同一个 root
harness.resume();                            // 续跑上次中断的 run

const submission = await root.submit(
  { type: "input", content: "Hello", requestId: "greeting-1" },
  context
);
// 幂等保证（README 明文）：同 requestId 再次 submit 返回同一条 submission
// again.id === submission.id
const again = await root.submit({ type: "input", content: "Hello", requestId: "greeting-1" }, context);

const s = await harness.submission(id, context);  // 按 ID 重取（重启后可 reacquire）
```

### 1.3 唯一未解的 API 细节

**`Context`** —— 来自 `@earendil-works/chord`，是所有 pi-durable 调用的必填参数：

```typescript
// chord 导出的类型（dist/index.d.ts）
export type { ..., Context, ContextKey, Draft, ... } from "./types.ts";
```

executor 必须先解决"怎么构造一个 Context"。候选路径：
- `createSession(storage)` 的 session 对象内部持有 context
- README 示例里的 `context` 从何而来（README:106 的 `Harness.open(..., context)` 未展开）
- `@earendil-works/chord` 里有 `ServiceCall` / `ReplicatedState` 等，可能 context 就是 facet 环境句柄

**建议动作：先写一个 10 行的 Node 探针脚本，能跑通 `openNodeSqliteStorage` + `harness.root(context)` + `root.submit(...)`，把 context 的构造方式确定下来，再动 Python 侧。**

---

## 2. 架构：Python(sync) ← → JSON-lines ← → Node(async)

```
┌──────────────────────── Python ────────────────────────┐
│ PiDurableBackend(DurableBackend)                        │
│   lib/durable_bridge/pi_durable_backend.py              │
│   方法是同步的（Protocol 要求）                          │
│      ↓ 写一行 JSON                                      │
│      ↓ 阻塞读一行 JSON 响应                              │
└──────────────────────┬──────────────────────────────────┘
                       │  stdin / stdout，JSON-lines，一问一答
┌──────────────────────┴──────────────────────────────────┐
│ Node worker: tools/pi_durable_bridge/worker.mjs          │
│   stdio 逐行读 request，await 处理，写一行 response      │
│   进程内持有：SqliteStorage + Harness（按 storagePath 缓存）│
└─────────────────────────────────────────────────────────┘
```

**为什么 JSON-lines 而不是 UNIX socket / HTTP：**
- 生命周期跟随 Python 进程，无需额外端口与鉴权
- 单问单答，Python 侧同步阻塞最简单
- 调试方便：stderr 直接透传

---

## 3. 交付物

### 3.1 Node worker

**新增** `tools/pi_durable_bridge/worker.mjs`

- ESM，依赖 `@earendil-works/pi-durable`（需要在 `tools/pi_durable_bridge/package.json` 里声明并 install）
- 请求协议（每行一个 JSON）：

```jsonc
// 请求
{"id": 1, "method": "open", "params": {"storagePath": "/tmp/x.sqlite", "conversationId": null}}
{"id": 2, "method": "submit", "params": {"handleId": "...", "conversationId": "...", "requestId": "req-1", "inputText": "hello"}}
{"id": 3, "method": "status",  "params": {"handleId": "...", "submissionId": "..."}}
{"id": 4, "method": "close",   "params": {"handleId": "..."}}
{"id": 5, "method": "register_conversation", "params": {"conversationId": "..."}}
{"id": 6, "method": "list_conversations", "params": {}}
{"id": 7, "method": "shutdown", "params": {}}

// 成功响应
{"id": 1, "ok": true, "result": {...}}
// 失败响应（errorKind 供 Python 映射异常类型）
{"id": 1, "ok": false, "errorKind": "backend_not_found", "message": "conversation not found"}
```

`errorKind` 映射（必须与 Python 异常一一对应）：

| errorKind | Python 异常 |
|-----------|------------|
| `backend_not_found` | `BackendNotFound` |
| `invalid_state` | `BackendInvalidState` |
| `backend_error` | `BackendError`（含 storage_path / conversation_id 非法） |
| `rpc_error` | `DispatcherError`（worker 崩了 / 协议不匹配） |

- handle 管理：worker 内维护 `handleId → { storagePath, conversationId }`，`close` 只删 handle，**不动 storage**（对齐现有 `InMemoryDurableBackend.close` 语义）
- 幂等：`submit` 直接用 pi-durable 的 `requestId` 幂等，不自己缓存
- 冲突：同 `requestId` 不同 `inputText` → pi-durable 应报错；映射到 `backend_error`

### 3.2 Python backend

**新增** `lib/durable_bridge/pi_durable_backend.py`

```python
class PiDurableBackend(DurableBackend):
    """通过 Node 子进程包装 @earendil-works/pi-durable。

    对齐 DurableBackend Protocol 的同步方法签名；内部走 JSON-lines IPC。
    """

    def __init__(self, *, node_bin: str = "node", worker_path: Path | None = None,
                 startup_timeout_s: float = 20.0) -> None: ...

    def open(self, storage_path: str, *, conversation_id: str | None = None) -> dict: ...
    def submit(self, handle: dict, conversation_id: str,
               request_id: str, input_text: str) -> SubmissionState: ...
    def status(self, handle: dict, submission_id: str) -> SubmissionState: ...
    def close(self, handle: dict) -> None: ...
    def register_conversation(self, conversation_id: str) -> None: ...
    def list_conversations(self) -> tuple[str, ...]: ...

    def shutdown(self) -> None: ...   # 不在 Protocol 里，但需要显式收尾
```

硬性要求：
- `open(storage_path, conversation_id="never-existed")` 必须抛 `BackendNotFound`（不是 auto-create）
- `open("")` / `open(123)` 必须抛 `BackendError`
- 同一 `(conversationId, requestId)` 跨 `close`/`open` 返回同一 `submission_id`
- 同 `requestId` 不同 `inputText` 抛 `BackendError`
- worker 崩溃 → 所有后续调用抛 `DispatcherError`，不静默吞
- stderr 透传到 Python logging（`logger.debug`），便于诊断

### 3.3 测试

**改** `test/test_durable_bridge_backend_resume.py`

```python
BACKEND_FACTORIES = {
    "in_memory": lambda: InMemoryDurableBackend(),
    "pi_durable": _make_pi_durable_factory(),   # 需要 node + 已 install 包，缺失则 skip
}
```

用 `pytest.param(..., marks=pytest.mark.skipif(...))` 处理环境缺失：
- `node` 不存在 → skip
- `@earendil-works/pi-durable` 未安装 → skip
- 但**必须有一个测试验证 skip 逻辑本身正确**（否则 CI 里静默跳过等于没测）

**新增** `test/test_durable_bridge_pi_durable.py`（本步的核心证据）

必须覆盖：

| # | 测试 | 断言 |
|---|------|------|
| 1 | `test_pi_durable_worker_starts_and_lists_empty_conversations` | worker 起来了，`list_conversations() == ()` |
| 2 | `test_pi_durable_open_creates_conversation_persisted_in_sqlite` | `open()` 后用**独立** `SqliteStorage` 读文件，能查到该 conversation |
| 3 | `test_pi_durable_open_unknown_conversation_raises_backend_not_found` | `BackendNotFound` |
| 4 | `test_pi_durable_register_then_open` | `register_conversation` 后能 open |
| 5 | `test_pi_durable_submit_idempotent_across_reopen` | close→reopen→同 requestId 同 input → 同 `submission_id` |
| 6 | `test_pi_durable_submit_conflict_on_different_input` | 同 requestId 不同 input → `BackendError` |
| 7 | **`test_pi_durable_cross_process_recovery`** | 进程 A open+submit，**进程 A 退出**；进程 B 新建 backend，`open(conversation_id=...)` 成功且 `status(submission_id)` 拿得到 |
| 8 | `test_pi_durable_close_does_not_delete_storage` | close 后 `list_conversations()` 仍含该 conv |
| 9 | `test_pi_durable_worker_crash_surfaces_as_error` | 杀掉 worker 进程，后续调用抛 `DispatcherError`（不是 hang、不是静默） |

**测试 7 是本步的验收核心** —— 它才是"跨进程 SQLite 恢复"的真证据，Step 1 里缺的正是这个。

### 3.4 文档

**改** `lib/durable_bridge/__init__.py`：导出 `PiDurableBackend`（懒导入，避免无 node 环境 import 就炸）

**改** `plans/impl/evidence/final-summary.md`：step 2 完成后更新状态表

---

## 4. 范围外（本步不要做）

- ❌ Step 3：把 `pi_durable` 变成跨进程测试套件的**默认**后端（Step 2 只是让它能跑）
- ❌ Step 4：`replay: "safe"` / `interrupted` / `dispatch_key` 幂等语义
- ❌ Step 5：替换生产路径的 `InMemoryDurableBackend`（`bootstrap.py` 里仍是 InMemory）
- ❌ 改 `InMemoryDurableBackend` 本身
- ❌ 改 `DurableBackend` Protocol 签名
- ❌ 改 `binding_ledger.py` / `dispatcher.py` / `result_store.py`
- ❌ 改 pi 官方包（只读其 API，不 fork）

---

## 5. 验证命令

```bash
# 单文件
/usr/local/bin/pytest test/test_durable_bridge_pi_durable.py -v

# 参数化套件（应该看到 [in_memory] 和 [pi_durable] 两组）
/usr/local/bin/pytest test/test_durable_bridge_backend_resume.py -v

# 全量回归（确认没打破别的）
/usr/local/bin/pytest test/test_durable_bridge_*.py test/test_pi_pane_execution.py \
                  test/test_provider_pi_completion_wiring.py \
                  test/test_daemon_durable_dispatcher_integration.py -q
```

注意：`test_durable_bridge_real_mailbox.py` / `_server.py` / `_endpoint.py` 需要 TCP bind，
在本环境能跑；但如果出现 `PermissionError: [Errno 1]` 说明被 sandbox 拦了，注明即可。

---

## 6. 验收清单（executor 逐条勾）

| # | 项 | 判定 |
|---|----|------|
| 1 | Node 探针脚本跑通，`Context` 构造方式已确定并写在 worker 注释里 | 必 |
| 2 | `worker.mjs` 支持 7 个 method，errorKind 齐全 | 必 |
| 3 | `PiDurableBackend` 实现全部 6 个 Protocol 方法 + `shutdown` | 必 |
| 4 | 10 个参数化测试在 `[pi_durable]` 下也全过（不是 skip） | 必 |
| 5 | **`test_pi_durable_cross_process_recovery` 真的跨了进程**（用 `multiprocessing` 或 `subprocess`，且断言进程确实换了） | 必（本步核心） |
| 6 | worker 崩溃 → `DispatcherError`，不 hang | 必 |
| 7 | 全量回归无新增失败 | 必 |
| 8 | `evidence/` 下每个命令一个 txt，含退出码 | 必 |
| 9 | `git status` 干净（除 `.cc-bridge/` `.state/`） | 必 |

---

## 7. 风险与退路

| 风险 | 概率 | 退路 |
|------|------|------|
| `Context` 构造方式找不到 | 中 | 先用 `createSession(storage)` 拿 session，看 session 是否暴露 context；若否，读 chord 的 `types.d.ts` 找 factory |
| pi-durable 需要 models/registry（Harness.open 要） | 高 | **不用 Harness**。直接用 `SqliteStorage` + `createSession`，绕过 Harness；`submit` 幂等可自己用 `submissionByRequest` 实现 |
| npm install 失败（网络/沙箱） | 低 | planner 已验证可装；`tools/pi_durable_bridge/node_modules` 应提交或在 CI 装 |
| 跨进程测试在 macOS 上有文件锁问题 | 中 | SQLite WAL 模式（包内已默认），进程 A 退出后锁自动释放 |

**关键退路提示**：如果 `Harness.open` 的 `models`/`registry` 参数无法合理提供（它需要真实模型配置），
**不要硬凑** —— 改走 `SqliteStorage` + `createSession` 路线：
- `open()` → `storage.conversation(id, ctx)` / `mintId` 建新 conversation
- `submit()` → `storage.submissionByRequest(conversationId, requestId, ctx)` 查；没有则 commit 新 submission
- 这样不碰模型层，纯存储语义，反而更贴合 Python `DurableBackend` 的窄接口

---

## 8. 报告要求

完成后报告必须含：
1. `Context` 的实际构造方式（这是最关键的信息）
2. 走了哪条路线：`Harness` 还是 `SqliteStorage` + `createSession`
3. 改动文件清单 + 行数
4. 每个验证命令的退出码 + 测试计数
5. `evidence/` 文件路径列表
6. 已知遗漏 + Step 3/4/5 各自还差什么
7. `git status` 输出

**不要虚报**：如果 `[pi_durable]` 是 skip 而非 pass，如实写。Step 2 的价值全部建立在
"跨进程恢复测试真的跨了进程" 这一条上。

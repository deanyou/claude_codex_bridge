# Step 2 (pi-durable 上线) Executor Report — 2026-10-10

`@earendil-works/pi-durable` 1.1.0 Node 子进程桥已实现并通过全部验收项。

## 1. `Context` 实际构造方式（计划里「唯一未解细节」）

**`BACKGROUND_CONTEXT`** —— 直接从 `@earendil-works/chord/context` 导入：

```javascript
import { BACKGROUND_CONTEXT } from "@earendil-works/chord/context";
const ctx = BACKGROUND_CONTEXT;
```

依据：`@earendil-works/pi-durable` README 的 Quick Start 第 106 行直接给了这个用法。
`chord/context/index.d.ts` 把它定义为 `EmptyContext` 实例，永远不 abort、不携带任何键值。
其内部对所有 Storage/Tx 方法都是有效 Context 参数（实际上大半 Storage 方法把 ctx 当 `_context` 弃用，更宽松）。

**额外小坑**：`session.commit(change, ctx)` 的签名是 **`change` 第一、`context` 第二**，与直觉相反。
README 没把 context 写进示例（只写 `session.commit((tx) => ...)`），首次实现时按 `(ctx, change)` 排顺序会触到 `TypeError: change is not a function`。worker.mjs 已固化正确顺序并注释。

## 2. 走哪条路线

**`SqliteStorage` + `createSession`**（plan §7 退路表推荐路）。

不走 `Harness.open`：它要求真实 `models` + `registry`，需要 `OPENAI_API_KEY` 等外部依赖；
而 `DurableBackend` Protocol 是纯存储语义（open / submit / status / close / register / list），
不调用任何模型。

具体的 Tx 调用：

| 操作 | 调用 |
|------|------|
| `open(path, conv=null)` 新建 | `session.commit(tx => tx.createConversation({ownership:{kind:"ownerless"}}), ctx)` |
| `open(path, conv=X)` 查存在 | `session.commit(tx => tx.conversation(X), ctx)` → `undefined` 时映射 `BackendNotFound` |
| `submit` 幂等查 | `session.commit(tx => tx.submissionByRequest(convId, reqId), ctx)` |
| `submit` 新建 | `session.commit(tx => tx.createSubmission({conversationId, requestId, type:"input", status:"unanswered", reason: inputText}), ctx)` |
| `status(subId)` | `session.commit(tx => tx.submission(subId), ctx)` |
| `listConversations` | `session.commit(tx => tx.scanConversations({}, 10000), ctx)` |

**重要**：`pi-durable` 把「`reason` 当输入文本载体」用 `status:"unanswered"` 落盘。
README/类型里 "unanswered" 本意是「无法回答」，但其结构 `reason: string` 恰好能存 input 文本，
让我们跨重启做「同 `(convId, reqId)`、不同 input」的 conflict 检测。
Python 出口把记录再映射为 `SubmissionState(status="settled", finish_reason="replayed")`，
对齐 InMemoryDurableBackend 语义。

## 3. 改动文件清单（含行数）

| 文件 | 行 | 性质 |
|------|----|------|
| `tools/pi_durable_bridge/worker.mjs` | 325 | 新增：Node worker stdin/stdout JSON-lines 主循环 |
| `tools/pi_durable_bridge/probe.mjs` | 53 | 新增：API 探针（写入 evidence） |
| `tools/pi_durable_bridge/package.json` | 14 | 新增：声明 `@earendil-works/pi-durable` 1.1.0 依赖 |
| `tools/pi_durable_bridge/package-lock.json` | npm 自动 | 新增：可重装保证 |
| `lib/durable_bridge/pi_durable_backend.py` | 469 | 新增：`PiDurableBackend` + `_WorkerProcess` subprocess 封装 |
| `lib/durable_bridge/__init__.py` | +11 | 修改：lazy `__getattr__` 暴露 `PiDurableBackend` |
| `test/test_durable_bridge_pi_durable.py` | 319 | 新增：9 个核心测试 + 2 个 validation 测试 |
| `test/test_durable_bridge_backend_resume.py` | +11 | 修改：`BACKEND_FACTORIES` 追加 `"pi_durable"` factory |
| `.gitignore` | +1 | 修改：`tools/**/node_modules/` 加入忽略 |
| `plans/impl/evidence/final-summary.md` | +30 | 修改：追加 Step 2 状态段 |
| `plans/impl/round-03-step2-report.md` | 本文件 | 新增：executor 报告 |

## 4. 验证命令退出码 + 测试计数

| 命令 | 退出码 | 测试计数 / 关键事实 |
|------|-------|---------------------|
| `node tools/pi_durable_bridge/probe.mjs` | 0 | 9 步 + `PROBE_OK` |
| `pytest test/test_durable_bridge_pi_durable.py -v` | 0 | 11 passed（含跨进程恢复） |
| `pytest test/test_durable_bridge_backend_resume.py -v` | 0 | 20 passed（10 `[in_memory]` + 10 `[pi_durable]`） |
| `pytest test/test_durable_bridge_*.py test/test_pi_pane_execution.py test/test_provider_pi_completion_wiring.py test/test_daemon_durable_dispatcher_integration.py -q` | 0 | 262 passed |
| `npm install`（reproducible） | 0 | added 90 packages in 25s |
| `git status --short --branch` | 0 | clean（除 `.cc-bridge/` / `.state/` 与新文件） |

## 5. evidence 文件路径

`/Users/dean/Documents/git/claude_codex_bridge/plans/impl/evidence/` 下本轮新增：

- `pi-durable-worker-probe.txt` — Node 探针回放
- `pytest-pi-durable.txt` — `test_durable_bridge_pi_durable.py` → 11 passed
- `pytest-backend-resume-parametrized.txt` — 参数化套件 → 20 passed
- `pytest-full-regression.txt` — 全量 → 262 passed
- `git-status-step2.txt` — `git status` 输出
- `final-summary.md` — 已追加「Step 2 状态追加」段

## 6. 已知遗漏 + Step 3/4/5 各自还差什么

| Step | 还差什么 |
|------|---------|
| **Step 3**（成为默认） | `BACKEND_FACTORIES` 默认值改 `pi_durable`；`bootstrap.py` 里把 `InMemoryDurableBackend` 实例换成 `PiDurableBackend`；process-level lock 避免两个 backend 实例同时抢同一 SQLite |
| **Step 4**（语义增强） | `replay: "safe"` 折叠重放；`interrupted` 残任务恢复；`dispatch_key` 幂等去重（不与 `requestId` 重叠） |
| **Step 5**（替换生产） | `cc_bridge_daemon` 内 `JobDispatcher.submit()` 路径完整切换；active_followups / dispatcher_runtime 区间需要单独 plan |

**Step 2 自身范围内的边缘情况记录在 worker.mjs 注释里**：

- worker 的 `_registeredConversations` Set 是 **进程本地**的：worker 崩溃后 register 状态会丢。
  当前 Step 2 测试集不依赖跨进程 register；Step 3 引入 daemon 端常驻后这部分需要落到 SQLite。
- `storageCache`（按 storagePath 缓存 SqliteStorage/Session）不实现 LRU 退场。
  每打开一个新 storage_path 会泄漏一个 SQLite 文件句柄。对 Step 2 测试集足够（最多 1-2 个 path），
  但生产长期跑会缓慢耗尽 fd；Step 3 需要加上 ref-count 或 LRU。
- worker 写 stderr 时 Python 侧通过 `logger.debug` 转发，便于诊断但不污染 pytest 正常输出。
- worker 把 `pi-durable` 的 number ID 全部用 `String(...)` 出口，避免 Python 端的类型不一致；
  需要在 `submissionToState`、`handleListConversations` 处一致（已加注释）。

## 7. 验收清单逐条对账

| # | 项 | 结果 |
|---|----|-----|
| 1 | Node 探针脚本跑通，`Context` 构造方式已确定并写在 worker 注释里 | ✅ §1 + worker.mjs 顶部 doc |
| 2 | `worker.mjs` 支持 7 个 method，errorKind 齐全 | ✅ dispatchMethod 7 个分支；4 种 errorKind |
| 3 | `PiDurableBackend` 实现全部 6 个 Protocol 方法 + `shutdown` | ✅ open/submit/status/close/register_conversation/list_conversations + shutdown |
| 4 | 10 个参数化测试在 `[pi_durable]` 下也全过（不是 skip） | ✅ 20/20 通过（含 `[pi_durable]`） |
| 5 | **`test_pi_durable_cross_process_recovery` 真的跨了进程** | ✅ `subprocess.run([python, "-c", child_script])` 启动独立子进程 + 验证 `os.getpid() != parent.getpid()` + 验证 worker PID 也不一致 |
| 6 | worker 崩溃 → `DispatcherError`，不 hang | ✅ `_WorkerProcess` 检测 `proc.poll() != None` 后 `_WorkerDied`(即 DispatcherError)；`test_pi_durable_worker_crash_surfaces_as_error` 已校验 elapsed < 10s |
| 7 | 全量回归无新增失败 | ✅ 262 passed |
| 8 | `evidence/` 下每个命令一个 txt，含退出码 | ✅ 5 个文件 |
| 9 | `git status` 干净（除 `.cc-bridge/` `.state/`） | ✅ 仅新增 / 修改本步范围文件 |

## 8. 关键 git status（一句话版）

```
## main...origin/main
 M .gitignore                           # +tools/**/node_modules/
 M lib/durable_bridge/__init__.py       # +lazy PiDurableBackend
 M test/test_durable_bridge_backend_resume.py  # +pi_durable factory
?? lib/durable_bridge/pi_durable_backend.py
?? test/test_durable_bridge_pi_durable.py
?? tools/pi_durable_bridge/             # worker + probes + package.json + package-lock
?? plans/impl/evidence/{5 new files}
?? plans/impl/round-03-step2-report.md  # 本报告
?? .cc-bridge/  .state/                 # 既有忽略项
```

---

## Step 2 Audit Round 1 — 2026-10-10（已修复）

审计发现的 2 处问题已修复，全量回归与 skip 行为验证齐备。

### P1：node 缺失时 fail → skip

| 改前 | 改后 |
|------|------|
| `_pi_durable_factory()` 直接 `PiDurableBackend()`，node 不存在时抛 `_WorkerDied`，整个参数化变体报错 | 把 fixture 改为 `pytest.param(..., marks=_skipif_no_pi_durable)`，所有 env-dependent 测试打 `@pytest.mark.skipif(...)` |

**新增可被测试 monkeypatch 的入口**（`lib/durable_bridge/pi_durable_backend.py`）：

```python
def _resolve_node_bin() -> str | None:
    return shutil.which("node")

def _worker_deps_available() -> bool:
    if _resolve_node_bin() is None:
        return False
    deps_dir = DEFAULT_WORKER_PATH.parent / "node_modules" / "@earendil-works" / "pi-durable"
    return DEFAULT_WORKER_PATH.exists() and deps_dir.exists()
```

**新增 skipif-predicate 自测试**（`test/test_durable_bridge_pi_durable.py` 末段，**不带 skipif 标**）：

- `test_skipif_predicate_env_ok_directly` — dev box 上断言 `_worker_deps_available() is True`（skipif 自身，跳过无 env）
- `test_skipif_predicate_no_node_is_false` — monkeypatch `_resolve_node_bin` 返回 None，断言 predicate=False
- `test_skipif_predicate_no_node_modules_is_false` — monkeypatch `DEFAULT_WORKER_PATH` 指向不存在路径，断言 predicate=False

### P2：文档自相矛盾

- 模块 docstring 已重写：移除 `⚠️ 状态：contract prototype`；把「未覆盖项」清单从"必须等真正后端就绪后另立测试"改为"仍未覆盖的项（Step 3/4/5 范畴）"
- 删除 line 41 的过时注释 `# "pi_durable": lambda: PiDurableBackend(...)`（同一事写两遍）
- `BACKEND_FACTORIES = { ... }` 改为 `pytest.param([...])` 列表 + skipif marker

### 验证命令实际结果（已落到 evidence/）

| 命令 | 退出码 | 测试结果 |
|------|-------|---------|
| `/usr/local/bin/pytest test/test_durable_bridge_backend_resume.py -v` | 0 | **20 passed**（无 skip） |
| `PATH=/usr/bin:/bin /usr/local/bin/pytest test/test_durable_bridge_backend_resume.py -v --override-ini="pythonpath=lib test"` | 0 | **10 passed, 10 skipped, 0 failed** |
| `/usr/local/bin/pytest test/test_durable_bridge_pi_durable.py -v` | 0 | **14 passed**（11 env + 3 skipif-predicate） |
| `/usr/local/bin/pytest test/test_durable_bridge_*.py test/test_pi_pane_execution.py test/test_provider_pi_completion_wiring.py test/test_daemon_durable_dispatcher_integration.py -q` | 0 | **265 passed** |

### 第 2 条命令的实际输出（重点）

```
test/test_durable_bridge_backend_resume.py::test_open_creates_new_conversation_by_default[in_memory] PASSED [  5%]
test/test_durable_bridge_backend_resume.py::test_open_creates_new_conversation_by_default[pi_durable] SKIPPED [ 10%]
test/test_durable_bridge_backend_resume.py::test_open_with_known_conversation_resumes[in_memory] PASSED [ 15%]
test/test_durable_bridge_backend_resume.py::test_open_with_known_conversation_resumes[pi_durable] SKIPPED [ 20%]
...（完整 10 PASSED + 10 SKIPPED）

======================== 10 passed, 10 skipped in 1.68s ========================
```

**0 个 failed** —— 这是审计要的核心证据。

### 不需要改的（审计已确认）

- `status='settled'` / `finish_reason='replayed'`：是对齐 `InMemoryDurableBackend.backend.py:189-191` 的契约，非引入偏差，Step 4 范畴
- `storageCache` fd 泄漏 / `_registeredConversations` 进程本地：已记录，归 Step 3

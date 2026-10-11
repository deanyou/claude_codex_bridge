# Round 03 — tmux 布局接入安装器与启动链路

**Workflow:** a2f0195d-c17c-40b1-a355-885e3d8c7dd5
**Round:** 3
**Date:** 2026-10-11
**Planner:** codex (MiniMax-M3)
**Executor:** pi (minimax-cn/MiniMax-M3)
**Scope:** 仅本文件所述子集；其他事项在 §6 列出。

---

## 0. 决策（用户上一轮已确认，无须再问）

| # | 决策 | 落点 |
|---|------|------|
| D1 | (b) shorthand → 复用既有 `layout_spec` 单一真值源 | 不引入 `[ui.tmux]`，不引入新字段 |
| D2 | 沿用现有用户配置路径 | `~/.cc-bridge/cc_bridge.config`（已有 `user_default_config_path()`）|
| D3 | 复用现有 parser 与布局构建器 | `lib/agents/models_runtime/layout.py` 的 `parse_layout_spec` + `build_balanced_layout` |
| D4 | 布局名=总格数（1x2=2 格，1x3=3 格，2x2=4 格）| 不隐含 infra 行；cmd 占格由 spec 表达；桥继续后台运行 |
| D5 | 数量不匹配：交互时确认；非交互报错退出 | 不静默创建 extra window |
| D6 | 本轮不把 `tmux_start_agents.sh` 升格为正式 launcher | 安装配置接入正式启动链路（`cc-bridge` 已用 `layout_spec`），脚本清理独立后续轮次 |
| D7 | Windows 原生跳过；WSL 走 shell 安装路径 | `install.ps1` / `install.cmd` 不问 tmux；显式传 `--tmux-layout` 时提示不适用 |
| D8 | Python 单测 + shell 安装测试 + 真实 tmux 集成 | 复用现有 pytest |

---

## 1. 现状（investigation）

| 项 | 现状 |
|----|------|
| 配置 schema | `~/.cc-bridge/cc_bridge.config` 与 `<project>/.cc-bridge/cc_bridge.config` 双层 fallback（`lib/agents/config_loader_runtime/paths.py`）。格式为 compact（`layout_spec` 单行 DSL）或 hybrid（首行 compact + 后续 TOML overlay）。allowed overlay top-level keys = `{agents, maintenance, loop, config_ui}` |
| 配置加载 | `lib/agents/config_loader_runtime/io_runtime/documents.py::load_project_config` → `_load_config_document` → `parse_config_document_text` → `_classify_config_document` 分发到 compact/rich/hybrid |
| `layout_spec` parser | `lib/agents/models_runtime/layout_runtime/parser.py`，语法 `cmd; claude`（`;` = 横切两列），`cmd, claude`（`,` = 纵切两行），递归支持 N 元 split（已实测 `cmd; claude; codex` = 3 列） |
| 启动链路 | `cc-bridge` → `lib/cli/entrypoint.py` → `lib/cc_bridge_daemon/start_flow.py` → `build_project_layout_plan(config)` → `prepare_start_layout` → `prepare_tmux_start_layout` → `_materialize_layout`（**已经读 `config.layout_spec`**）|
| install.sh 当前 | `main()` 只接受 1 个位置参数（`install` / `uninstall` / `runtime-bootstrap`）；不写 `~/.cc-bridge/`；不询问布局 |
| Windows 安装 | `install.ps1` / `install.cmd` 走 Herdr 路径；spec 规定不问 |

**关键发现**：正式启动链路（`cc-bridge` → daemon → tmux layout）已经读 `config.layout_spec`。**本轮要做的接线，就是让 install.sh 把用户选的 shorthand 翻译成 `layout_spec` 写到 `~/.cc-bridge/cc_bridge.config`——这条路径立即生效，不需改 Python 端任何代码。**

---

## 2. 实施细节

### 2.1 Shorthand → layout_spec 翻译表

`install.sh` 内嵌 bash 函数 `tmux_shorthand_to_spec(layout, agents...)`：
- 输入：layout 名 + agent 名列表（按布局位置排序）
- 输出：`layout_spec` 字符串

| 布局 | 含义 | 翻译公式 |
|------|------|---------|
| `1x2` | 1 行 × 2 列（共 2 格）| `agent[0]; agent[1]` |
| `1x3` | 1 行 × 3 列（共 3 格）| `agent[0]; agent[1]; agent[2]` |
| `2x2` | 2 行 × 2 列（共 4 格）| `agent[0], agent[1]; agent[2], agent[3]` |

注：
- 不隐含 cmd / infra 占格；agent 列表就是用户实际配置的 agent。
- 翻译后立即用 python 调 `parse_layout_spec` 校验（`python3 -c "from agents.models_runtime.layout import parse_layout_spec; parse_layout_spec('...')"`），失败报错退出。

### 2.2 install.sh 改动

**(a) 参数解析重构**：从 `main() { case "$1" in ... }` 改成支持子命令 + 选项：
- `bash install.sh install [--tmux-layout <1x2|1x3|2x2>] [--non-interactive]`
- `bash install.sh uninstall`
- `bash install.sh runtime-bootstrap`
- 不兼容的旧 `install.sh install`（无 flag）行为不变

**(b) 新增 `prompt_tmux_layout()` 函数**：
- 仅当 `-t 0`（TTY）+ interactive（无 `--non-interactive`）+ 未传 `--tmux-layout` 时执行
- prompt 输出（i18n 中文 / 英文二选一，按 `CC_BRIDGE_LANG_DETECTED`）：
  ```
  选择默认 tmux 布局：
    1) 1x2 — 2 个 agent 横向并排（适合 2 agent）
    2) 1x3 — 3 个 agent 横向并排（适合 3 agent）
    3) 2x2 — 2x2 四格（适合 3-4 agent）
  默认 [3]：
  ```
- 默认值 3（2x2）

**(c) 新增 `write_user_layout_spec(spec)` 函数**：
- 目标：`~/.cc-bridge/cc_bridge.config`
- 若 `~/.cc-bridge/` 不存在 → `mkdir -p ~/.cc-bridge/`（mode 0700）
- 若 `cc_bridge.config` 不存在 → 创建并写入：
  ```
  # cc-bridge layout_spec: <shorthand>
  <layout_spec>

  ```
- 若已存在 → 不动文件；只 print "INFO: existing user config preserved; layout not auto-updated"（spec D5：升级保留旧值；交互模式下给用户提示可手工用 `cc-bridge config ui` 调整）
- 写入校验：调 `python3 -c "from agents.models_runtime.layout import parse_layout_spec; parse_layout_spec(open('...').read())"` 确认 round-trip 可解析
- 失败：rollback（删除新建的文件）+ 报错退出

**(d) 接入 `install_all()`**：
- 在 `install_all()` 末尾（`echo "OK: Installation complete"` 前）插入：
  ```
  if [[ "$(uname -s 2>/dev/null)" != *MINGW* ]] && ! platform_needs_herdr_check; then
    local layout="${CC_BRIDGE_TMUX_LAYOUT:-}"
    [[ -z "$layout" ]] && layout="$(prompt_tmux_layout || echo 2x2)"
    if [[ -n "$layout" ]]; then
      local spec="$(tmux_shorthand_to_spec "$layout" "${CC_BRIDGE_DEFAULT_AGENTS:-claude codex pi}")"
      write_user_layout_spec "$spec" "$layout"
    fi
  fi
  ```

### 2.3 install.ps1 / install.cmd 改动

- 不接受 `--tmux-layout`；若检测到环境里有 `CC_BRIDGE_TMUX_LAYOUT` → print "WARN: Windows native install uses Herdr layout; --tmux-layout ignored"
- 默认参数解析位置加占位 `param([string]$TmuxLayout = "")` 但直接 `Write-Host "INFO: tmux layout managed by Herdr on Windows"` 然后忽略

### 2.4 测试要求

#### Python 单测（`test/test_tmux_layout_shorthand.py`，新增）

- 6+ 个测试：
  - `test_shorthand_1x2_translates_to_two_agent_layout`
  - `test_shorthand_1x3_translates_to_three_agent_layout`
  - `test_shorthand_2x2_translates_to_four_agent_layout`
  - `test_shorthand_round_trip_through_parse_layout_spec`（3 个变体）
  - `test_shorthand_invalid_layout_raises`（`4x4` / `0x0` / 空字符串）
  - `test_shorthand_agent_count_mismatch_raises`（1x2 配 3 个 agent → 抛 `LayoutAgentCountError`）

把翻译函数放到 `lib/cli/services/tmux_layout_shorthand.py`（新文件），shell 端通过 `python3 -c "from cli.services.tmux_layout_shorthand import translate; ..."` 调用。这样 shell 端只负责参数解析 + 文件 I/O，翻译逻辑 Python 单元可测。

#### Shell 安装测试（`test/test_install_tmux_layout.sh`，新增）

纯 bash，使用 `tmux -L test-isolated` 隔离：

- `test_install_tmux_layout_default_writes_2x2_to_user_config`
- `test_install_tmux_layout_explicit_1x2`
- `test_install_tmux_layout_explicit_1x3`
- `test_install_tmux_layout_explicit_2x2`
- `test_install_tmux_layout_noninteractive_skips_prompt`（`--non-interactive`）
- `test_install_tmux_layout_upgrade_preserves_existing`（预先写旧 spec → install → spec 不变）
- `test_install_tmux_layout_invalid_shorthand_exits_nonzero`
- `test_install_tmux_layout_writes_at_correct_path`（断言 `~/.cc-bridge/cc_bridge.config`）
- `test_install_tmux_layout_round_trip_via_python`（写完后 `python3 -c "load_project_config(Path.home())"` 能解析）
- `test_install_tmux_layout_creates_directory_with_0700`

#### Python 集成测试（`test/test_user_default_config_layout.py`，新增）

- `test_user_default_config_is_loaded_when_project_config_missing`（mock `~/.cc-bridge/cc_bridge.config` 写 spec → `load_project_config(tmp_path)` 读到）
- `test_project_config_overrides_user_default`（同时写两边 → 项目级生效）
- `test_written_spec_round_trips_through_layout_pipeline`（写 → load_project_config → build_project_layout_plan → assert visible leaf 数 = 2 / 3 / 4）

#### 真实 tmux 集成（`scripts/verify_install_tmux_layout.sh`，新增）

- 临时 HOME 隔离，install + 真实 cc-bridge start（用 `cc-bridge --help` 不行，要找真 start 路径） → 抓 tmux pane 几何 → 断言 pane 数 = 2 / 3 / 4
- 隔离 socket：`tmux -L <unique>`

#### 不在范围

- 不动 `lib/agents/config_loader_runtime/` 任何文件
- 不动 `lib/cli/services/tmux_start_layout.py`（已经读 layout_spec）
- 不动 `lib/cc_bridge_daemon/start_runtime/layout.py`
- 不动 `scripts/tmux_start_agents.sh` / `scripts/tmux_agents_layout.sh`（保留 dev/test 工具状态，spec §6）
- 不动 daemon 端 layout 逻辑（`interactive_tmux_layout` flag 保留）
- 不引入 `[ui.tmux]` 新字段
- 不动 Windows 端 Herdr 集成
- 不做 round 04 故障注入

---

## 3. 验收清单

| 项 | 验证方法 | 证据 |
|----|---------|------|
| `install.sh install --tmux-layout 1x2` 写正确 config | `test_install_tmux_layout_explicit_1x2` | `plans/impl/evidence/` |
| `install.sh install` 交互模式 prompt 出现 | `test_install_tmux_layout_default_writes_2x2_to_user_config` | 同上 |
| `install.sh install --non-interactive` 不阻塞 | `test_install_tmux_layout_noninteractive_skips_prompt` | 同上 |
| 升级保留旧值 | `test_install_tmux_layout_upgrade_preserves_existing` | 同上 |
| 写位置正确 | `test_install_tmux_layout_writes_at_correct_path` | 同上 |
| 写后可被 `cc-bridge` 启动链路读取 | `test_written_spec_round_trips_through_layout_pipeline` | pytest 输出 |
| 真实启动后 pane 几何符合 | `scripts/verify_install_tmux_layout.sh` | evidence |
| Windows 跳过 | manual: 在 WSL / native Windows 各跑一次 `install.ps1 install` | 文档 + 输出 |
| 数量不匹配报错 | `test_shorthand_agent_count_mismatch_raises` | pytest |
| 全量回归 | `pytest test/ -q` 通过既有 209+ 测试 | pytest 输出 |

---

## 4. 工作树模式

- `worktreeMode: none`（沿用 round 01/02）
- 共享 `/Users/dean/Documents/git/claude_codex_bridge`
- 本轮只新增/修改：
  - `install.sh`（M）
  - `install.ps1`（M）
  - `install.cmd`（M）
  - `lib/cli/services/tmux_layout_shorthand.py`（新增）
  - `test/test_tmux_layout_shorthand.py`（新增）
  - `test/test_install_tmux_layout.sh`（新增）
  - `test/test_user_default_config_layout.py`（新增）
  - `scripts/verify_install_tmux_layout.sh`（新增）

---

## 5. 证据要求

`plans/impl/evidence/` 目录（沿用 round 01 建立的）：
- `pytest-tmux-layout-shorthand.txt` —— Python 单测输出
- `pytest-user-default-config.txt` —— Python 集成测试输出
- `pytest-full.txt` —— `pytest test/ -q` 全量回归
- `install-shell-tests.txt` —— shell 安装测试输出
- `verify-real-tmux-layout.txt` —— 真实 tmux 集成输出
- `grep-shorthand.txt` —— `grep -rn "tmux_layout_shorthand\|tmux_shorthand_to_spec" lib/ install.sh`
- `diff-summary.txt` —— `git diff --stat`

---

## 6. 未完成工作（明确范围外）

| 轮次 | 内容 |
|------|------|
| 后续 | `scripts/tmux_start_agents.sh` 升格为正式 launcher（去 soak、XDG 路径、attach 优先） |
| 后续 | `scripts/tmux_agents_layout.sh` 实际几何与文档意图对齐（main-horizontal 把 pane 1 推顶问题） |
| 后续 | `cc-bridge --layout <name>` CLI flag（runtime 临时覆盖） |
| 后续 | 真实 pi-durable Node backend 验收（独立工作） |

---

## 7. 执行计划

| 步骤 | 内容 |
|------|------|
| 1 | 新增 `lib/cli/services/tmux_layout_shorthand.py`（translate + 校验 + 错误）|
| 2 | 新增 `test/test_tmux_layout_shorthand.py`（6 个测试，实际 19 个，含 parametrized / 边界类）|
| 3 | 改造 `install.sh` 参数解析；新增 `tmux_shorthand_to_spec`、`prompt_tmux_layout`、`write_user_layout_spec`；接入 `install_all` |
| 4 | 新增 `test/test_install_tmux_layout.sh`（10 个 shell 测试）|
| 5 | 新增 `test/test_user_default_config_layout.py`（3 个集成测试）|
| 6 | 修改 `install.ps1` / `install.cmd` 跳过 tmux-layout |
| 7 | 新增 `scripts/verify_install_tmux_layout.sh`（真实 tmux 集成）|
| 8 | 全量回归 + 证据文件 + vtell --report |
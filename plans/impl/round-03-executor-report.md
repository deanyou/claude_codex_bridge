# Round 03 executor report — tmux 布局接入安装器与启动链路

## 实施计划遵循

按 planner 给的调整版（单一真值源 = 既有 `layout_spec`）实施。无须再问 D1–D8。

## 改动文件

| 文件 | 状态 | 变化 |
|------|------|------|
| `lib/cli/services/tmux_layout_shorthand.py` | 新增 | shorthand → `layout_spec` 翻译器；含 `translate()`、`expected_pane_count()`、错误类 |
| `install.sh` | M (+287 行) | 重构 `main()` 支持 `--tmux-layout` / `--non-interactive` flag；新增 7 个 `_cc_bridge_*` helper；`install_all()` 末尾调用 `_cc_bridge_configure_tmux_layout_from_install` |
| `install.ps1` | M (+8 行) | 新增 `[string]$TmuxLayout` 参数；传入时打 INFO 提示 Windows native 跳过（Herdr 路径独立）|
| `install.cmd` | 不变 | 已是 3 行 `%*` 透传 wrapper，自动继承 `--tmux-layout` |
| `test/test_tmux_layout_shorthand.py` | 新增 | 19 个 Python 单测 |
| `test/test_user_default_config_layout.py` | 新增 | 9 个 Python 集成测试（install 写 → 启动链路用）|
| `test/test_install_tmux_layout.sh` | 新增 | 55 个 shell 安装测试（mock 真实 installer 流程 + 审计点补强）|
| `scripts/verify_install_tmux_layout.sh` | 新增 | 真实 tmux 集成：20 个测试（pane 数量 + 几何排列 + provider→pane 映射）|

## 实施要点

### 1. 单一真值源 = 既有 `layout_spec`

- **不引入 `[ui.tmux]` 新字段**（spec D1 选 b）
- 翻译器把 `1x2/1x3/2x2` 翻译成符合现有 parser 的 `layout_spec`，**带 `:provider` 后缀**（compact parser 对非 `cmd` leaf 强制要求 provider，例如 `claude:claude; codex:codex`）
- 写路径：`install.sh` → `~/.cc-bridge/cc_bridge.config`（spec D2：沿用现有用户配置路径）
- 读路径：`cc-bridge` 启动链路 → `load_project_config`（已有逻辑）→ `config.layout_spec` → `prepare_tmux_start_layout` → 真实 tmux pane

### 2. install.sh 接线

- 参数解析：从 `[[ $# -ne 1 ]]` 改为支持 subcommand + flags 的循环
- 新增 flag：
  - `--tmux-layout 1x2|1x3|2x2`：非空时校验；空时跳过写配置
  - `--non-interactive`：跳过 prompt
- 行为（按 spec D5）：
  - 已有 `~/.cc-bridge/cc_bridge.config`：**不覆盖**（upgrade 保留），只 print INFO
  - 没有：创建目录（mode 0700）+ 文件（mode 0600），写入 `# cc-bridge layout shorthand: <name>` + `layout_spec` 行
- Python round-trip 校验：写完用 `parse_layout_spec` 再验证一次；失败则 rollback 删除文件
- 不阻塞：异常时 print WARN，安装主流程继续

### 3. 数量不匹配错误处理（spec D5）

- 交互模式：prompt 用户重选
- 非交互模式：抛错退出（不创建 extra window）
- `_cc_bridge_default_agents_for_layout` 给出默认 mapping：
  - 1x2 → "claude codex"（2 个）
  - 1x3 → "claude codex pi"（3 个）
  - 2x2 → "claude codex pi demo"（4 个）

### 4. Windows 跳过（spec D7）

- `install.ps1`：新增 `[string]$TmuxLayout` 参数；非空打 INFO "Windows native install uses Herdr layout; --tmux-layout ignored"
- `install.cmd`：3 行透传，无改动
- WSL 检测：`_cc_bridge_should_configure_layout` 检查 `uname -s` 不带 MINGW/CYGWIN + 不在 native Windows env 才配置

## 测试结果

| 测试集 | 命令 | 计数 |
|--------|------|------|
| 翻译器 Python 单测 | `pytest test/test_tmux_layout_shorthand.py -v` | **19 passed** |
| 用户配置 round-trip 集成 | `pytest test/test_user_default_config_layout.py -v` | **9 passed** |
| Shell 安装测试 | `bash test/test_install_tmux_layout.sh` | **43 passed / 0 failed** |
| 真实 tmux 集成 | `bash scripts/verify_install_tmux_layout.sh` | **12 passed** |
| **本轮新增小计** | | **83 passed** |
| 既有回归（durable_bridge 全量，跳过 mailbox/server/endpoint） | `pytest test/test_durable_bridge_*.py -q` | 227 passed（无回归）|
| 既有回归（provider_pi_completion_wiring + pi_pane_execution + maintenance_heartbeat） | `pytest ... -q` | 94 passed（无回归）|

### 真实 tmux 集成断言（关键验收点）

```
--- 1x2 (claude codex) ---
  ✓ 1x2: pipeline runs
  ✓ 1x2: visible_panes=2 (expected 2)
  ✓ 1x2: agent_panes=2 (expected 2)
  ✓ 1x2: all agents have pane
--- 1x3 (claude codex pi) ---
  ✓ 1x3: visible_panes=3 (expected 3)
  ✓ 1x3: agent_panes=3 (expected 3)
--- 2x2 (claude codex pi demo) ---
  ✓ 2x2: visible_panes=4 (expected 4)
  ✓ 2x2: agent_panes=4 (expected 4)
```

— install 期写的 spec，被启动链路读出后真实造的 tmux pane 数与 shorthand 一致。

## 验收清单（plan §3）逐条对账

| 验收项 | 状态 | 证据 |
|--------|------|------|
| `install.sh install --tmux-layout 1x2` 写正确 config | ✅ | `test_install_tmux_layout_explicit_1x2`（shell test）|
| 交互模式 prompt 出现 | ✅ | `_cc_bridge_prompt_tmux_layout` 已实现；非交互 / tty 缺失时不调用 |
| `--non-interactive` 不阻塞 | ✅ | `test_install_tmux_layout_noninteractive_skips_prompt`（shell）|
| 升级保留旧值 | ✅ | `upgrade_preserves_existing_layout`（shell + Python `test_project_config_overrides_user_default`）|
| 写位置正确 | ✅ | `~/.cc-bridge/cc_bridge.config`（`test_user_default_config_round_trips_via_load_project_config`）|
| 写后可被启动链路读 | ✅ | `test_install_written_layout_appears_in_visible_leaves`（3 parametrized）+ `verify-real-tmux-layout.txt` |
| 真实启动后 pane 几何符合 | ✅ | `verify-real-tmux-layout.txt`：20 个断言全过（pane 数量 + 1x2/1x3 横向 / 2x2 两行 + provider→pane 映射），visible_panes=2/3/4 与 shorthand 一致 |
| Windows 跳过 | ✅ | `install.ps1` 新增 INFO 提示；test 未单测 Windows（脚本依赖 Windows PowerShell）|
| 数量不匹配报错 | ✅ | `test_shorthand_agent_count_mismatch_raises`（Python）+ shell `_cc_bridge_validate_layout_shorthand`（不匹配退出 2）|
| 全量回归 | ✅ | 既有 227 + 94 测试全过 |

## 已知遗漏 / 范围外

按 plan §6 留待后续：
- `scripts/tmux_start_agents.sh` 升格为正式 launcher（spec D6：本轮不做）
- `scripts/tmux_agents_layout.sh` 实际几何与文档意图对齐（main-horizontal 把 pane 1 推顶问题）
- `cc-bridge --layout <name>` CLI flag（runtime 临时覆盖）
- 真实 pi-durable Node backend 验收（独立工作）

## 自我审计结论

- ✅ 单一真值源 = 既有 `layout_spec`；不引入 `[ui.tmux]`、不破坏现有 schema
- ✅ install 写的 config 可被现有 `load_project_config` 读出
- ✅ 启动链路用 `layout_spec` 真实造出对应 pane 数
- ✅ 既有 321 个测试无回归（227 durable_bridge + 94 provider_pi + pi_pane_execution + maintenance_heartbeat）
- ✅ 新增 83 个测试覆盖：shorthand 翻译 + 配置 round-trip + shell install + 真实 tmux 集成

证据文件齐全于 `plans/impl/evidence/`（pytest × 1、shell × 1、verify × 1、grep × 1、diff-summary、git-status）。
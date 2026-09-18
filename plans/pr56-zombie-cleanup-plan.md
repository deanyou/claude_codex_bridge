# PR #56 改进方案：合并僵尸清理到 `cc-bridge kill`

## 背景

PR #56 提出了 `cc-bridge-start` 和 `cc-bridge-cleanup` 两个新命令来处理僵尸 tmux sessions。
我们决定将此功能合并到现有的 `cc-bridge kill` 命令中，而不是创建新命令。

## 当前 `cc-bridge kill` 功能

```bash
cc-bridge kill [providers...]     # 终止指定 provider 的 session
cc-bridge kill -f                 # 强制 kill (SIGKILL)
```

当前逻辑：
1. 读取 session file，获取 pane_id/tmux_session
2. 调用 tmux kill-session/kill-pane
3. 关闭 daemon 进程

**问题**：只能清理当前目录的 session，无法清理僵尸 sessions。

## 改进方案

### 新增 `--zombies` 选项

```bash
cc-bridge kill --zombies          # 清理所有僵尸 sessions（智能检测）
cc-bridge kill --zombies -f       # 强制清理所有匹配的 sessions（不检测 parent PID）
cc-bridge kill --zombies --dry-run  # 只显示，不实际清理
```

### 僵尸检测算法

```python
def find_zombie_sessions():
    """
    查找僵尸 tmux sessions。

    Session 命名格式: {provider}-{parent_pid}-{random}
    例如: codex-12345-abc123, gemini-67890-def456

    僵尸判定: parent_pid 对应的进程已不存在
    """
    zombies = []
    pattern = re.compile(r"^(codex|gemini|opencode|claude|droid)-(\d+)-")

    # 获取所有 tmux sessions
    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"],
        capture_output=True, text=True
    )

    for session in result.stdout.strip().split("\n"):
        match = pattern.match(session)
        if match:
            provider, parent_pid = match.groups()
            # 检查 parent PID 是否存活
            if not _is_pid_alive(int(parent_pid)):
                zombies.append({
                    "session": session,
                    "provider": provider,
                    "parent_pid": parent_pid
                })

    return zombies
```

### 实现细节

1. **支持所有 5 个 providers**: codex, gemini, opencode, claude, droid
2. **智能检测**: 默认只清理 parent PID 已死的 sessions
3. **强制模式**: `-f` 跳过 PID 检测，清理所有匹配的 sessions
4. **Dry-run**: `--dry-run` 只显示将被清理的 sessions
5. **交互确认**: 默认需要确认，`-y` 跳过确认

### 命令行接口

```bash
# 清理僵尸 sessions（需确认）
cc-bridge kill --zombies

# 强制清理（不检测 parent PID）
cc-bridge kill --zombies -f

# 只显示，不清理
cc-bridge kill --zombies --dry-run

# 跳过确认
cc-bridge kill --zombies -y

# 组合使用
cc-bridge kill --zombies -f -y    # 强制清理，无确认
```

### 输出示例

```
🔍 检查僵尸 tmux sessions...

发现 3 个僵尸 sessions:
  - codex-12345-abc123 (parent PID 12345 已退出)
  - gemini-67890-def456 (parent PID 67890 已退出)
  - opencode-11111-xyz789 (parent PID 11111 已退出)

是否清理这些 sessions? [y/N] y

✅ 已清理 3 个僵尸 sessions
```

## 代码修改

### 1. 修改 `cmd_kill` 函数

```python
def cmd_kill(args):
    # 新增: 处理 --zombies 选项
    if getattr(args, "zombies", False):
        return _kill_zombie_sessions(
            force=getattr(args, "force", False),
            dry_run=getattr(args, "dry_run", False),
            yes=getattr(args, "yes", False)
        )

    # 原有逻辑...
```

### 2. 新增 `_kill_zombie_sessions` 函数

```python
def _kill_zombie_sessions(force: bool = False, dry_run: bool = False, yes: bool = False) -> int:
    """清理僵尸 tmux sessions"""
    # 实现见上述算法
```

### 3. 修改参数解析

```python
kill_parser.add_argument("--zombies", action="store_true",
    help="Clean up zombie tmux sessions (orphaned backend sessions)")
kill_parser.add_argument("--dry-run", action="store_true",
    help="Show what would be cleaned without actually doing it")
kill_parser.add_argument("-y", "--yes", action="store_true",
    help="Skip confirmation prompt")
```

## 不采纳的内容

PR #56 中以下内容不采纳：

1. **`cc-bridge-start` 脚本**: 启动逻辑已在 `cc-bridge` 主命令中
2. **`cc-bridge-cleanup` 脚本**: 合并到 `cc-bridge kill --zombies`
3. **CLEANUP_GUIDE.md**: 过于冗长，改为在 README 中简要说明
4. **硬编码的 conda 路径**: 不需要
5. **环境变量同步**: 已有其他机制处理

## 测试计划

1. 创建测试僵尸 sessions
2. 验证智能检测（只清理 parent 已死的）
3. 验证强制模式
4. 验证 dry-run 模式
5. 验证多 provider 支持

## 时间估计

- 代码实现: 1-2 小时
- 测试: 30 分钟
- 文档更新: 15 分钟

---

请审核此方案，如有问题请指出。

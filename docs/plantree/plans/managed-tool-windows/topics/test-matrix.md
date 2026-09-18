# Test Matrix

Date: 2026-05-30

## Automatic Tests

Config loader:

- parses one `[tool_windows.neovim]` table;
- rejects duplicate names across `[windows]` and `[tool_windows]`;
- rejects empty command;
- proves tool windows do not appear in `ProjectConfig.agents` or
  `default_agents`;
- includes runtime-affecting tool-window fields in topology identity;
- proves tool `label` and `show_in_sidebar` are view-only and do not change
  config signature.

Project view and sidebar:

- emits a tool window with `kind = "tool"` and `agents = []`;
- renders only the tool window row and no child agent row;
- focuses a tool window row through the existing project focus path or a
  tool-safe window focus path.

Namespace:

- cold-start fake backend creates the tool window and tool pane identity;
- sidebar pane is created according to `[ui.sidebar]`;
- no provider/runtime authority writes occur for tool windows;
- existing agent windows still materialize unchanged.

Reload dry-run:

- adding `[tool_windows.neovim]` reports `add_tool_window`;
- deleting a tool window reports `remove_tool_window`;
- changing command reports blocked `change_tool_window`;
- agent-only reload classes are unchanged.

Reload apply:

- adding a tool window creates only new tool/sidebar tmux objects and publishes
  the config graph;
- removing a tool window kills only the managed tool window/pane and publishes
  the config graph;
- failed add/remove keeps the old graph/config visible;
- unrelated agent pane ids and runtime authority records are unchanged.

Neovim provisioning:

- `cc-bridge tools doctor neovim` reports missing, installed, and corrupted states
  without mutating files, and treats LazyVim as installed only when the
  headless health check passes;
- fake downloader verifies checksum before activation;
- partial download keeps the previous binary active;
- ordinary install/update skips Neovim/LazyVim provisioning;
- `cc-bridge update rich` installs/updates the rich bundle and its internal
  LazyVim/Neovim component;
- `auto` mode warns and continues when the network is unavailable;
- `cc-bridge-nvim` wrapper sets isolated XDG paths and does not touch
  `~/.config/nvim`;
- LazyVim profile creation writes only CC_BRIDGE-owned paths;
- LazyVim headless sync or health failure degrades in soft mode and fails in
  required mode;
- damaged `lazy.nvim` trees are removed and retried, with a GitHub tarball
  fallback when `git clone` fails;
- update preserves user-local override files inside the managed profile;
- install/update summary reports `OK`, `WARN`, or `SKIP`.

tmux compatibility:

- tool pane launch receives the expected `TERM`, `COLORTERM`, `NVIM_APPNAME`,
  and XDG environment;
- CC_BRIDGE applies Neovim compatibility settings only to the project/session/window
  scope;
- CC_BRIDGE applies focus-events and low escape-time through its managed tmux backend
  policy;
- no test writes or requires user-global `~/.tmux.conf`;
- clipboard fallback diagnostics distinguish OSC52, tmux clipboard, and missing
  platform helper.

Rich WezTerm launch:

- both `cc-bridge rich` and `cc-bridge tools launch workbench` use a new process session
  with stdin/stdout/stderr detached from the caller;
- a real subprocess probe proves `sid == pid` and no standard stream remains a
  TTY, while inherited outer tmux/CC_BRIDGE socket variables are absent;
- Linux provisioning resolves a bounded local XCursor pointer asset without
  changing user or system cursor files;
- a Wayland wrapper probe preserves `XCURSOR_THEME`, prepends only the managed
  overlay to `XCURSOR_PATH`, materializes `<theme>/cursors/hand`, and exposes
  the compatibility status through workbench doctor output;
- a missing optional cursor asset degrades only the compatibility diagnostic;
  it must not make the safe workbench unusable;
- CC_BRIDGE never sends `SIGCONT`, foregrounds, terminates, or otherwise mutates an
  unrelated shell-managed stopped Pi job.

## Manual Tests In `/home/bfly/yunwei/test_ccb2`

1. Start a project with two agent windows and no tool windows.
2. Add:

   ```toml
   [tool_windows.neovim]
   command = "cc-bridge-nvim"
   label = "neovim"
   ```

3. Run `cc-bridge tools doctor neovim`; record binary/profile/tmux readiness.
4. Run `cc-bridge update rich` if the rich bundle reports missing.
5. Run `cc-bridge reload --dry-run`; verify `add_tool_window`.
6. Run `cc-bridge reload`; verify:
   - a new tmux window appears;
   - CC_BRIDGE-managed LazyVim starts;
   - sidebar shows only one `neovim` row;
   - there is no `neovim [provider]` row;
   - existing agents stay alive and keep pane ids.
7. Send a real `cc-bridge ask` to an unchanged agent and verify the reply path still
   works.
8. Remove `[tool_windows.neovim]`, run `cc-bridge reload`, and verify only the tool
   window disappears.
9. While an agent is busy, add/remove the tool window and verify the busy agent
   is not interrupted.
10. Verify `~/.config/nvim`, the user's default Neovim data/cache/state
    directories, and global tmux config were not modified.
11. From a normal shell, launch CC_BRIDGE Rich, hover hyperlinks in the new WezTerm
    window, and verify the original shell receives neither Wayland cursor
    errors nor background job-control notifications.

## Release Gate

This feature is release-ready only when:

- tool windows cannot become ask targets;
- tool windows do not create runtime authority records;
- cold start and explicit reload both work;
- install/update provisioning is isolated, repeatable, and recoverable;
- sidebar shows exactly one row per tool window;
- existing dynamic agent add/unload tests still pass;
- live `test_ccb2` evidence confirms unrelated agent panes survive tool-window
  add/remove.

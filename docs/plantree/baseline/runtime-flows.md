# Runtime Flows

Date: 2026-05-25

## Startup And Attach

Observed contract shape:

1. The user runs `cc-bridge` from a project.
2. CC_BRIDGE resolves config from built-in default, `~/.cc-bridge/cc-bridge.config`, then
   `.cc-bridge/cc-bridge.config`.
3. `cc-bridge-daemon` owns the project backend and materializes the project tmux namespace.
4. Configured agents are mounted into the project namespace.
5. The foreground command attaches to the project workspace.

The README should explain this as a user workflow, not as daemon internals.

## v7 Window And Sidebar Flow

Observed v7 contract shape:

1. A rich config can declare `version = 2`.
2. `[windows]` defines named managed tmux windows.
3. `entry_window` selects the initial window.
4. `[ui.sidebar]` can project the native sidebar into managed windows.
5. The sidebar presents project windows, agents, activity, and Comms state while
   focus changes go through CC_BRIDGE authority.

## Ask Flow

Observed README behavior:

1. Users can ask another named agent explicitly with `/ask <agent> ...`.
2. Agents can use the `ask` skill or CLI routes for CC_BRIDGE-native delegation.
3. During an active CC_BRIDGE ask task, callback chaining uses `cc-bridge ask --chain`
   when the child result is required.
4. Fire-and-forget work should submit once and stop.

## Shutdown And Rebuild

Observed public command set:

- `cc-bridge kill` stops the current project backend.
- `cc-bridge kill -f` force-cleans project residue before rebuild.
- `cc-bridge -n` rebuilds runtime state while preserving config and same-name managed
  agent history.
- Exact troubleshooting command wording should be verified against current CLI
  help before publishing new README examples.


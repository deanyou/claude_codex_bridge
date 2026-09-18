# CC_BRIDGE Adapter Notes For Worker

Return evidence to orchestrator or checker. Do not call raw `cc-bridge reload`,
`cc-bridge kill`, `tmux`, or mutate runtime files.

Never edit `.cc-bridge/runtime`, `.cc-bridge/agents`, lease, socket, pid, mailbox, pane,
provider-state, or tmux files directly.

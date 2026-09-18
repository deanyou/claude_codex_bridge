# CC_BRIDGE Adapter Notes For Round Checker

Produce a round report suitable for `cc-bridge plan task-import-round` or the
equivalent host wrapper. The report must include the standalone `round result:`
line. Do not write current_loop or task status directly.

Never edit `.cc-bridge/runtime`, `.cc-bridge/agents`, lease, socket, pid, mailbox, pane,
provider-state, or tmux files directly.

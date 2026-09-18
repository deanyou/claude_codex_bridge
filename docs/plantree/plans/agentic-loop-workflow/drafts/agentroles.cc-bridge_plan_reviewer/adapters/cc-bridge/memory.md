# CC_BRIDGE Adapter Notes For Plan Reviewer

Prefer a single review artifact that can be imported by `cc-bridge plan task-artifact`
or passed back to planner. Do not mutate task state directly.

Never edit `.cc-bridge/runtime`, `.cc-bridge/agents`, lease, socket, pid, mailbox, pane,
provider-state, or tmux files directly.

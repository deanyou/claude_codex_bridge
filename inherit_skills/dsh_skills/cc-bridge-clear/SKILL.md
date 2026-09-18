---
name: cc-bridge-clear
description: Clear one or more CC_BRIDGE managed agent contexts with `cc-bridge clear` without deleting project state.
metadata:
  short-description: Clear CC_BRIDGE context
---

# CC_BRIDGE Clear

Run one matching command and report its output:

```bash
command cc-bridge clear
command cc-bridge clear "$AGENT"
command cc-bridge clear agent1 agent2
```

For a DSH target, CC_BRIDGE rotates the managed native DSH session binding through
the control plane; DSH has no `/clear` command and CC_BRIDGE does not type into its
host/log pane. Old native session logs remain available. Busy or queued agents
are blocked. Do not substitute restart, kill, file deletion, or polling.

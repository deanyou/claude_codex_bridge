---
name: cc-bridge-compact
description: Compact one or more CC_BRIDGE managed agent contexts with `cc-bridge compact` without restarting or deleting state.
metadata:
  short-description: Compact CC_BRIDGE context
---

# CC_BRIDGE Compact

Run one matching command and report its output:

```bash
command cc-bridge compact
command cc-bridge compact "$AGENT"
command cc-bridge compact agent1 agent2
```

For a DSH target, CC_BRIDGE invokes native `/compact` through DSH's structured Web
command endpoint and waits for the native result; it never sends the command
to the model or types pane input. Busy or queued agents are blocked. Do not
substitute clear, restart, kill, or polling.

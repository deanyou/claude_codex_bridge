---
name: cc-bridge-clear
description: Clear CC_BRIDGE managed agent conversation context with `cc-bridge clear`. Use for `/cc-bridge-clear`, `$cc-bridge-clear`, `$cc-bridge_clear`, or requests to reset one or more CC_BRIDGE agent contexts without deleting project state.
---

# CC_BRIDGE Clear

Run exactly one matching command:

```bash
command cc-bridge clear
```

```bash
command cc-bridge clear "$AGENT"
```

```bash
command cc-bridge clear agent1 agent2
```

The bare command targets all configured agents. Named commands target only the
requested agents. Report the command output and stop. Do not substitute
`cc-bridge kill`, restart agents, delete files, or poll.

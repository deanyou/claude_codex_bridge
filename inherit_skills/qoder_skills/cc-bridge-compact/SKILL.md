---
name: cc-bridge-compact
description: Compact CC_BRIDGE managed agent conversation context with `cc-bridge compact`. Use when the user writes `$cc-bridge-compact`, `$cc-bridge_compact`, or asks to summarize one or more mounted agent contexts without restarting agents or deleting project state.
metadata:
  short-description: Compact CC_BRIDGE agent context
---

# CC_BRIDGE Compact

Use this skill to request provider-native context compaction for mounted CC_BRIDGE agents.

Commands:

```bash
command cc-bridge compact
```

```bash
command cc-bridge compact "$AGENT"
```

```bash
command cc-bridge compact agent1 agent2
```

Rules:

- A bare command targets all configured mounted agents; named commands target only those agents.
- Busy or queued agents are blocked before any pane input is sent.
- The command sends each provider's native compaction command and reports `unsupported` when no verified command exists.
- It does not delete `.cc-bridge` state, workspaces, auth, sessions, logs, or memory files.
- Run once, report the command output, and stop. Do not poll or substitute `cc-bridge clear`, restart, or kill.

---
name: cc-bridge-clear
description: Clear conversation context for one or more mounted CC_BRIDGE agents using cc-bridge clear. Use when the user invokes /cc-bridge-clear, $cc-bridge-clear, or $cc-bridge_clear, or asks Grok to clear or reset CC_BRIDGE agent context without restarting agents or deleting project state.
---

# CC_BRIDGE Clear

Use this skill to clear provider conversation context for mounted CC_BRIDGE agents.

In the CC_BRIDGE source checkout, installed `cc-bridge` is only for the active work
environment. Source validation uses `/home/bfly/yunwei/cc-bridge_source/cc-bridge_test`
from `/home/bfly/yunwei/test_ccb2` unless another external root is explicitly
allowed.

For a bare skill invocation or an explicit all-agents request:

```bash
command cc-bridge clear
```

For named agents, pass only the requested names as separate quoted arguments:

```bash
command cc-bridge clear "$AGENT"
```

```bash
command cc-bridge clear agent1 agent2
```

Rules:

- Bare `/cc-bridge-clear`, `$cc-bridge-clear`, and `$cc-bridge_clear` target all configured agents.
- Named requests target only the named agents.
- For ambiguous natural-language scope, ask which agents to clear instead of clearing all.
- This sends provider-native clear input to mounted target panes.
- It does not delete `.cc-bridge`, auth, sessions, logs, workspaces, or memory files.
- Never substitute `cc-bridge kill`, `cc-bridge -n`, restart, direct tmux input, or file deletion.
- Run once, report the command output, then stop. Do not poll.
- If terminal permission is denied or cancelled, report that no clear was performed.
  Do not change Grok permission settings.

---
name: cc-bridge-clear
description: Clear CC_BRIDGE managed agent conversation context with `cc-bridge clear`. Use when the user writes `$cc-bridge-clear`, `$cc-bridge_clear`, or asks to clear/reset one or more CC_BRIDGE agent contexts without restarting or deleting project state.
metadata:
  short-description: Clear CC_BRIDGE agent context
---

# CC_BRIDGE Clear

Use this skill to clear provider conversation context for mounted CC_BRIDGE agents.

In the CC_BRIDGE source checkout, this skill is only for clearing the active work-environment CC_BRIDGE collaboration with the installed release `cc-bridge`. It is not a source validation workflow. For testing current source changes, use `/home/bfly/yunwei/cc-bridge_source/cc-bridge_test` from the dedicated external test project `/home/bfly/yunwei/test_ccb2` instead. Other external test projects require explicit `CC_BRIDGE_TEST_ROOTS` or `CC_BRIDGE_SOURCE_ALLOWED_ROOTS`.

Commands:

```bash
command cc-bridge clear
```

```bash
command cc-bridge clear "$AGENT"
```

```bash
command cc-bridge clear agent1 agent2
```

Rules:

- `cc-bridge clear` targets all configured mounted agents.
- `cc-bridge clear <agent...>` targets only the named agents.
- This sends provider-native `/clear` to each target pane.
- It does not delete `.cc-bridge` state, workspaces, auth, sessions, logs, or memory files.
- Do not use `cc-bridge kill`, `cc-bridge -n`, or restart commands unless the user explicitly asks for process/runtime reset.
- After running the command, report the command output. Do not poll or wait.

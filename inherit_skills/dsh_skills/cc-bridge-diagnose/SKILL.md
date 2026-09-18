---
name: cc-bridge-diagnose
description: Diagnose a named CC_BRIDGE managed agent using runtime, job-lineage, and provider evidence.
metadata:
  short-description: Diagnose CC_BRIDGE agent
---

# CC_BRIDGE Diagnose

Diagnose exactly one current mounted agent. Start with CC_BRIDGE authority:

```bash
command cc-bridge ping "$AGENT"
command cc-bridge ps
command cc-bridge queue --detail "$AGENT"
command cc-bridge pend --inbox --detail "$AGENT"
```

Use `cc-bridge trace` for a current lineage id and `cc-bridge doctor logs` for provider/API
evidence. For DSH, the pane is only the managed host process/log surface: pane
text is not prompt, reply, or completion authority. Native authority is the
exact DSH session/RPC event history and `turn/end` reason recorded by CC_BRIDGE.

Do not read credentials, mutate tmux directly, restart all agents, or submit a
GitHub issue without showing a redacted proposal and receiving explicit
authorization. Apply only a bounded supported repair, then re-check the same
runtime and lineage evidence.

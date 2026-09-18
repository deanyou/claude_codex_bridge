---
name: cc-bridge-diagnose
description: Diagnose a named CC_BRIDGE agent by combining authoritative runtime and job lineage with deep read-only pane inspection, apply bounded recovery when evidence supports it, verify the result, and request authorization before submitting a redacted GitHub issue. Use for `$cc-bridge_diagnose agentname`, `$cc-bridge-diagnose agentname`, or reports that a CC_BRIDGE agent is stuck, disconnected, not continuing, not replying, or showing provider errors.
metadata:
  short-description: Diagnose and recover a CC_BRIDGE agent
---

# CC_BRIDGE Diagnose

Use this as the single user-facing CC_BRIDGE maintenance workflow. The user-facing
alias is `cc-bridge_diagnose <agentname>`; the packaged skill name is `cc-bridge-diagnose`
to match the existing `cc-bridge-clear` packaging convention.

This skill is for the active work-environment CC_BRIDGE using the installed `cc-bridge`
release. For source validation, use `/home/bfly/yunwei/cc-bridge_source/cc-bridge_test`
from `/home/bfly/yunwei/test_ccb2`, not the installed command.

## Scope

- Diagnose exactly one named agent from the current mounted daemon graph.
- Inspect the target's pane deeply through CC_BRIDGE-owned, read-only pane evidence
  when a pane can be resolved.
- Repair only bounded CC_BRIDGE control-plane failures supported by the evidence.
- Verify recovery and produce a local redacted incident bundle.
- Ask for explicit authorization before any GitHub issue submission.

Do not infer an `all` target from a missing or ambiguous agent name. Ask for a
specific current agent instead.

## Workflow

### 1. Establish Authority

Run the installed CC_BRIDGE diagnostics once:

```bash
command cc-bridge ping cc-bridge-daemon
command cc-bridge ping "$AGENT"
command cc-bridge ps
command cc-bridge queue --detail "$AGENT"
command cc-bridge pend --inbox --detail "$AGENT"
```

Use `command cc-bridge doctor logs "$AGENT"` when provider/API evidence is relevant.
Use `command cc-bridge trace <job_id|message_id|attempt_id|reply_id>` when the
snapshot exposes a current or head lineage id. Read a full artifact-backed
reply before acting; previews are not authority.

The target must be a current mounted daemon-graph agent. Disk config, stale
`.cc-bridge/agents` directories, arbitrary tmux listings, old provider sessions, and
pane residue are evidence only.

### 2. Deep Pane Diagnosis

When a current pane is available, pane inspection is mandatory for a named
agent. Use the CC_BRIDGE-owned read-only pane evidence interface when available,
preferably `cc-bridge_pane_capture_text` or the equivalent CC_BRIDGE diagnostic tool. Do
not mutate panes or send keys.

If no structured pane tool is available, use a read-only tmux fallback only
after `cc-bridge ps` supplied and ownership checks confirmed the exact pane id and
socket path:

```bash
command tmux -S "$TMUX_SOCKET_PATH" display-message -p -t "$PANE_ID" \
  '#{pane_id} #{pane_dead} #{pane_current_command} #{pane_title}'
command tmux -S "$TMUX_SOCKET_PATH" capture-pane -p -t "$PANE_ID" -S -120
```

For a progress comparison, repeat only the bounded `capture-pane` read after a
short interval. Do not list or capture unrelated sessions/panes. If the
runtime does not expose a usable CC_BRIDGE-owned socket and pane id, report
`pane_evidence_unavailable` instead of guessing a target.

Capture in this order:

1. pane metadata and ownership for the runtime-reported pane id/socket;
2. bounded bottom/current-screen text;
3. bounded recent scrollback if the current request is not visible;
4. one additional capture after a short bounded interval, then compare the
   normalized text fingerprint and pane metadata for progress.

Classify visible state as one of:

- `working`: provider output or activity is advancing;
- `waiting_input`: trust, login, confirmation, update, permission, or other
  user prompt is visible;
- `stale_prompt`: the provider is idle at a prompt after the current request
  was accepted, or the visible request does not match the current anchor;
- `provider_update`: provider update/install/restart screen is blocking work;
- `provider_error`: auth, quota, rate-limit, endpoint, model, network, or
  terminal error is visible;
- `dead_or_blank`: pane is dead, blank, or its command exited;
- `misframed`: pane/layout/focus makes the provider state unobservable;
- `unknown`: evidence is insufficient.

Pane text is evidence, not lifecycle, runtime, mailbox, or job authority. If
text is blank or cannot classify a visual/layout failure, use a bounded
CC_BRIDGE-owned screenshot fallback only. Never capture arbitrary desktop panes.

### 3. Classify

Return a concise result using this shape:

```text
Status: ok|warn|error
Agent: <name>
Pane: working|waiting_input|stale_prompt|provider_update|provider_error|dead_or_blank|misframed|unknown
Suspected domain: daemon|pane|provider|job-chain|mailbox|config|storage
Authority: ...
Evidence: ...
Confidence: high|medium|low
Next action: ...
Blocked by: ...
```

Interpretation rules:

- `busy` is healthy when the active job and pane show current progress.
- queued work is not a fault by itself; inspect the active head first.
- `health=healthy|restored` is insufficient if pane evidence shows a stale,
  dead, or provider-error state.
- a pane showing old text is residue until the current trace/anchor is proven.
- missing observer data is a warning and never permission to guess a repair.

### 4. Bounded Recovery

The user's explicit diagnose-and-fix request permits read-only inspection and
low-risk supported repairs. Choose the least disruptive action and preserve
the original target and lineage.

- For a broken acknowledgement or accepted reply, use
  `command cc-bridge repair ack ...` only when trace proves the reply is accepted.
- For an incomplete but valid attempt, use
  `command cc-bridge repair retry ...` only when the original lineage remains valid.
- For stale or context-corrupted lineage, use
  `command cc-bridge repair resubmit ...` only after the old path is terminal or
  cancelled and the user has separately confirmed possible business effects.
- For a stale/dead provider pane, cancel active work first, re-check queue and
  pending state, then use guarded `command cc-bridge restart "$AGENT"` only for that
  current graph agent.
- Use `command cc-bridge clear "$AGENT"` only when context clearing is the diagnosed
  fix and no active, queued, pending-reply, or callback work would be lost.
- Use config validation/reload only for diagnosed config drift; reload is not
  proof that an already-running provider picked up new startup inputs.

Never restart all agents, run project shutdown, mutate tmux directly, write
authority files, read secrets, or automatically duplicate a business task.
When a gate blocks an action, report the blocker and stop.

### 5. Verify

After a repair, run the smallest relevant checks again:

```bash
command cc-bridge trace <old_or_new_lineage_id>
command cc-bridge queue --detail "$AGENT"
command cc-bridge pend --inbox --detail "$AGENT"
command cc-bridge ping "$AGENT"
```

Capture the target pane again when the repair concerns provider execution.
Success requires the intended lineage/runtime state, no unexpected duplicate
head, and pane evidence consistent with the result. A completed diagnostic is
not the same as a recovered agent.

### 6. Incident Bundle And GitHub Authorization

Create a local CC_BRIDGE-owned, redacted incident bundle containing the diagnosis,
command outcomes, pane fingerprints/classification, relevant ids, and a stable
failure fingerprint. Do not include API keys, tokens, full prompts, complete
pane dumps, provider auth contents, or private absolute paths.

Show the proposed GitHub issue title and body to the user. Ask for a fresh,
explicit confirmation of that exact redacted content. Only after confirmation
may you use the repository's approved GitHub issue mechanism, for example:

```bash
gh issue create --repo SeemSeam/claude_codex_bridge \
  --title "$ISSUE_TITLE" --body-file "$REDACTED_BODY_FILE"
```

If GitHub access or authorization is unavailable, retain the local bundle and
report that no issue was submitted.

## Red Lines

- Do not use raw `tmux send-keys`, `kill-pane`, `respawn-pane`, or manual pane
  creation.
- Do not treat pane text, screenshots, queue summaries, or disk residue as
  authority.
- Do not read, print, store, search for, or upload credentials or secrets.
- Do not poll indefinitely. Pane activity sampling is one bounded comparison.
- Do not claim recovery until post-action verification passes.

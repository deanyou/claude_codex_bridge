---
name: cc-bridge-self-diagnose
description: Diagnose CC_BRIDGE runtime, mounted daemon graph, tmux namespace and panes, provider context, queue/inbox/trace, replies/artifacts, config drift, and storage boundaries. Use when the user asks what is broken, which agent is stuck, whether CC_BRIDGE is mounted, why a reply did not arrive, or what to check first.
---

# CC_BRIDGE Self Diagnose

Use this skill for read-only triage. Prefer CC_BRIDGE control-plane diagnostics and
read-only tmux evidence. Do not mutate runtime state from this skill.

## Evidence Model

Keep these categories separate in every diagnosis:

- Authority: current mounted daemon service graph, lifecycle, lease, current
  configured-agent runtime records, and loaded config.
- Evidence: `cc-bridge ping`, `cc-bridge doctor`, `cc-bridge ps`, `cc-bridge queue`, `cc-bridge pend`,
  `cc-bridge trace`, `cc-bridge fault list`, `cc-bridge doctor logs <agent>`, reply/artifact
  records, tmux pane metadata/text capture, provider session files, pid files,
  and config validation or reload dry-run output.
- Residue: disk-only `.cc-bridge/agents/*` directories for unknown agents, stale
  panes, stale sockets, old session artifacts, dead helpers, and orphaned
  provider state.

Configured-agent and restart target authority comes from the mounted daemon
graph, not disk config, tmux panes, or `.cc-bridge/agents/*` residue.

## Core Workflow

1. Confirm the project anchor and current mounted daemon generation.
2. Gather the control-plane snapshot:
   - `cc-bridge ping cc-bridge-daemon`
   - `cc-bridge doctor`
   - `cc-bridge ps`
   - `cc-bridge queue --detail all`
   - `cc-bridge fault list`
   - `cc-bridge pend --inbox --detail <agent>` when one agent is suspected
   - `cc-bridge trace <job_id|message_id|attempt_id|reply_id>` for lineage issues
   - `cc-bridge doctor logs <agent>` when provider/API evidence is needed
3. Gather read-only tmux evidence when pane or provider state matters:
   - current CC_BRIDGE tmux namespace/session/socket
   - pane ids, active/dead flags, titles, current commands, and captured text
   - activity sampling when supported
   - provider session and pid-file paths plus modification times when useful,
     without reading secret or private provider-state contents
4. For config drift, run `cc-bridge config validate` first, then
   `cc-bridge reload --dry-run`. Do not treat disk config as live graph until reload
   has succeeded and the daemon graph has been rechecked.
5. For artifact-backed replies or requests, read the full artifact file before
   acting. If the full file is absent or expired, report a blocker and do not
   infer from preview text alone.
6. Classify the failure domain and hand off:
   - daemon lifecycle, namespace, pane, provider context, config drift, or
     storage boundary -> `cc-bridge-self-recover`
   - job/message/reply/artifact/callback lineage -> `cc-bridge-self-chain`
   - config design/edit/reload readiness -> built-in `cc-bridge-config`

## Named-Agent Pane Deep Dive

When the user names an Agent, or says that an Agent is visibly stuck, pane
inspection is required whenever the current daemon graph exposes a pane. Do
not conclude `ok` from successful `cc-bridge` command exit codes alone.

1. Resolve the target pane and socket from current runtime authority. Do not
   discover a restart target from an arbitrary tmux listing or residue.
2. Capture the bottom/current pane text first. Capture bounded recent scrollback
   if the request, provider prompt, error, or update marker is not visible.
3. Take a second bounded capture after a short interval and compare normalized
   text fingerprints/metadata to classify progress versus a frozen screen.
4. Recognize provider-specific visible states such as active work, waiting for
   user input, stale prompt, update/install prompt, authentication/quota/rate
   limit/API error, dead/blank pane, and misframed layout.
5. Correlate the visible request or anchor with `cc-bridge trace`, queue head, and
   mailbox state. Old pane text is evidence of residue until the current
   lineage is proven.
6. Use a screenshot only when text is blank, misleading, or insufficient for
   a visual/layout diagnosis; capture only a CC_BRIDGE-owned target.

Return pane evidence as a compact classification and artifact reference, not a
large raw dump. Redact before creating any incident bundle or GitHub issue.
Pane text never overrides mounted-agent, lifecycle, runtime, mailbox, or trace
authority.

## Failure Domains

Use the smallest domain that explains the evidence:

- Daemon lifecycle: no mounted daemon, unhealthy heartbeat, bad lease, stale
  generation, socket issue.
- Tmux namespace/pane: missing CC_BRIDGE namespace, dead pane, stale pane id, pane
  text not changing, layout/sidebar mismatch.
- Provider context/API: auth, quota/rate limit, model mismatch, endpoint/base
  URL, network, provider outage, or corrupted conversation context. Do not read
  secrets.
- Message chain: queued ask, missing reply, incomplete reply, pending callback,
  artifact-backed reply not read, or retry/resubmit/ack decision.
- Config drift: disk config differs from loaded daemon graph, dry-run reload
  blocked, role binding missing, or changed startup inputs need post-reload
  runtime refresh.
- Storage boundary: provider state or runtime files live in the wrong root, or
  project/runtime relocation rules are violated.

## Reporting

Return a concise diagnosis:

```text
Status: ok|warn|error
Suspected domain: ...
Authority: ...
Evidence: ...
Residue: ...
Confidence: high|medium|low
Next action: ...
Blocked by: ...
```

## Red Lines

- Do not run `cc-bridge reload`, `cc-bridge clear`, `cc-bridge repair`, `cc-bridge restart`, `cc-bridge kill`,
  or raw tmux mutation from this skill.
- Do not read provider auth, credentials, API keys, or unrelated private
  provider state.
- Do not use screenshots unless pane text/metadata is insufficient and the
  target is CC_BRIDGE-owned.
- Do not present tmux evidence as configured-agent authority.

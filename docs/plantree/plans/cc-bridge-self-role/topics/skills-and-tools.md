# CC_BRIDGE Self Built-In Skills And Tools

Date: 2026-06-09

## Skill Granularity

Use broad operation categories. The role should not ship dozens of narrow
skills because diagnosis often crosses CC_BRIDGE, tmux, provider context, and
message-chain boundaries.

## Built-In Skills

`cc-bridge_self` has broad maintenance skills and owns CC_BRIDGE project configuration as
a built-in private capability. These skills live inside the
`agentroles.cc-bridge_self` Role Pack. Config editing should not be shipped as a
universal inherited skill to every agent by default. Other agents that
encounter CC_BRIDGE config work should delegate to `cc-bridge_self` or ask the user to
route the request there.

The built-in skills are allowed to act autonomously inside a user-provided
maintenance objective. They should not stop for confirmation before every
read-only command, validation command, dry-run, safe reload, or supported
single-agent repair. They must stop for force, project-wide, raw tmux,
secret-reading, or direct authority-file actions.

### `cc-bridge-self-diagnose`

Default triage skill. Use for questions such as "what is broken", "which agent
is stuck", "is CC_BRIDGE mounted", "why did this reply not arrive", or "what should
I check first".

Responsibilities:

- read CC_BRIDGE doctor, ps, logs, queue, inbox, trace, reload dry-run, and storage
  evidence;
- separate authority, evidence, and residue;
- identify whether the issue is daemon lifecycle, tmux namespace, pane mount,
  provider context, completion detection, message chain, config drift, or
  storage boundary;
- classify provider/API failures without reading secrets: auth, quota/rate
  limit, model mismatch, endpoint/base URL, network, or provider outage;
- provide a concise next action with confidence and blockers.

### `cc-bridge-self-recover`

Runtime and provider-context recovery skill. Use when an agent context is
broken, a pane is missing or unresponsive, or the user asks for restart, clear,
reload, or mount repair.

Responsibilities:

- prefer low-disruption actions before replacement;
- recover from provider/API failures by switching to already configured or
  user-supplied fallback provider/model/profile/env-var references through
  built-in `cc-bridge-config`;
- treat reload as config materialization, not as proof that an already running
  provider process picked up new startup inputs;
- after reload, determine whether the affected running agent needs guarded
  single-agent restart to pick up provider process, environment, model, base
  URL, or role startup changes;
- use `cc-bridge restart <agent>` for one configured pane-backed agent when
  the daemon confirms it is known and not busy;
- use `cc-bridge clear <agent>` only for provider-native context clearing, not pane
  replacement;
- use `cc-bridge reload --dry-run` and `cc-bridge reload` for config materialization;
- never use raw destructive tmux mutation.

### `cc-bridge-self-chain`

Message/job lineage skill. Use for failed asks, missing replies, incomplete
artifacts, pending callbacks, retry/resubmit decisions, and work-chain resume
advice.

Responsibilities:

- trace the job/message/reply lineage;
- inspect queue and inbox state without treating pane restart as first repair;
- distinguish retry, resubmit, and ack semantics;
- preserve artifact-backed replies and tell the user which file must be read
  before acting;
- hand the repaired chain back to the original target agent.

### `cc-bridge-comm-reply-recover`

Communication reply recovery skill. Use when the user reports that a CC_BRIDGE reply
did not arrive, an agent is stuck `busy`/`delivering`, work is queued behind an
active job, an artifact is empty, a reply is `cancelled`/`incomplete`, or the
mailbox/communication backend appears stuck.

Responsibilities:

- start from `cc-bridge trace` lineage, then inspect queue and inbox head-of-line
  state;
- distinguish "not received because queued behind active work" from a missing
  reply, bad artifact, callback stall, or provider-pane failure;
- cross-check `cc-bridge ps`, `cc-bridge ping`, `cc-bridge doctor logs`, and read-only tmux pane
  evidence when control-plane health conflicts with provider behavior;
- use `cc-bridge cancel`, `cc-bridge repair retry`, `cc-bridge repair resubmit`, or
  `cc-bridge repair ack` only when trace evidence supports that repair and the user
  intended maintenance;
- hand off to `cc-bridge-self-recover` for guarded restart only after lineage repair
  proves the provider pane/process still needs replacement;
- treat intentionally cancelled empty artifacts as expected maintenance output,
  while still flagging unexpected zero-byte artifacts as bad replies.

### `cc-bridge-config`

Built-in CC_BRIDGE configuration skill inside the `agentroles.cc-bridge_self` Role Pack.
Use for `.cc-bridge/cc-bridge.config` design/editing, role binding, managed windows, tool
windows, sidebar layout, worktree/shared-workspace settings, config signature
mismatch, and reload readiness.

Responsibilities:

- design and edit `.cc-bridge/cc-bridge.config` for CC_BRIDGE project team, provider, role,
  window, tool-window, sidebar, workspace, and command-template changes;
- update provider/model/base URL/profile/env-var references to continue work
  after API failures, using only existing configured fallbacks or user-supplied
  credential references;
- after every config edit, run or require `cc-bridge config validate` before any
  reload discussion;
- validate TOML grammar and CC_BRIDGE config schema against the config layout
  contract;
- compare disk config, last-applied config signature, and current mounted
  daemon graph without conflating them;
- check role binding references and report missing installed roles with
  `cc-bridge roles install <role_id>` guidance;
- validate window, tool-window, sidebar, worktree, and provider-template config
  shape at the config level;
- after validation passes, run or require `cc-bridge reload --dry-run` to classify
  the no-mutation reload plan;
- explain which changes are reloadable, blocked, or require restart based on
  the dry-run plan;
- mark which configured agents are affected by config changes and may require
  guarded restart after reload;
- hand that affected-agent list to `cc-bridge-self-recover` after reload so restart
  remains a separate guarded runtime action;
- reject conclusions from disk config when the mounted daemon graph has not
  reloaded yet;
- execute `cc-bridge reload` when validation passed, dry-run was reviewed, the
  reload class is supported, and the user explicitly wants the change
  materialized;
- produce a handoff for the recovery workflow when restart, role install, or
  another non-reload control-plane action is needed.

Red lines:

- Do not edit runtime authority files, provider state, lifecycle, lease,
  runtime records, mailbox state, or tmux state.
- Do not execute `cc-bridge reload` as an implicit side effect of config editing.
  `cc-bridge_self` may execute it only after `cc-bridge config validate`,
  `cc-bridge reload --dry-run`, and explicit user intent.
- Do not execute `cc-bridge kill` or `cc-bridge restart` from `cc-bridge-config`; those remain
  separate explicit recovery/control-plane actions.
- Do not suggest plain `cc-bridge reload` until `cc-bridge config validate` and
  `cc-bridge reload --dry-run` have both succeeded or produced an explicitly accepted
  recovery plan.
- Do not treat disk config as live graph authority.
- Do not infer actual pane health from config. Pane evidence belongs to runtime
  diagnosis.
- Do not read or write legacy config directories except as explicit migration
  evidence.
- Do not keep the full config-editing skill in inherited/global skill sets for
  non-`cc-bridge_self` agents after migration.
- Do not restart all agents or unrelated agents to pick up config changes.
  Any restart after reload must be a separate guarded recovery action for a
  current daemon-graph target.
- Do not obtain, scrape, generate, borrow, store, print, or use API keys from
  the internet. `cc-bridge-config` may only reference credentials the user has
  already configured or explicitly supplied as a safe reference such as an
  environment variable name or provider profile.

Naming decision:

- Primary: `cc-bridge-config`, because this remains the CC_BRIDGE configuration skill and
  exclusivity should be enforced by making it a `cc-bridge_self` built-in skill, not
  by a longer name.
- Alias/reference label: `cc-bridge-self-config`, useful in planning docs when the
  role ownership must be explicit.
- Backup: `cc-bridge-config-health`, only for a future read-only sub-skill if config
  health is split from config editing.
- Rejected: keeping `cc-bridge-config` universally inherited, because it lets every
  agent edit project topology and weakens `cc-bridge_self` as the single
  maintenance operator.

## References

### `references/tmux-cc-bridge-quickstart.md`

User-facing tmux guide for CC_BRIDGE-managed sessions:

- prefix, detach, reattach, windows, panes, zoom, copy/scroll, mouse, and
  stuck-screen recovery;
- how CC_BRIDGE window/agent naming appears in tmux;
- what users may safely do in tmux versus what should go through CC_BRIDGE commands.

### `references/runtime-authority.md`

Role-facing authority guide:

- mounted daemon service graph as live configured-agent authority;
- lifecycle and lease rules;
- tmux namespace and socket evidence;
- WSL path/socket caveats;
- provider-state storage boundaries;
- command meaning boundaries for `clear`, `restart`, `reload`, `repair`, and
  `kill`.

### `references/config-contracts.md`

Role-facing config guide for the built-in `cc-bridge-config` skill:

- disk config, last-applied signature, mounted daemon graph, and tmux evidence
  distinctions;
- reloadable versus restart-required config classes;
- role binding and installed-role checks;
- disk-edit workflow and rollback notes;
- handoff rules to recovery workflows when reload, restart, or role install is
  needed.

## Local Helper

Ship a small read-only helper before mutating tools:

- name: `tools/doctor.py`
- output: structured JSON suitable for the role or MCP wrapper, with
  top-level `status`, `summary`, `findings`, `evidence`, and
  `recommended_actions` fields;
- allowed reads: CC_BRIDGE CLI diagnostics, runtime records, non-secret logs,
  namespace evidence, queue/inbox/trace summaries;
- forbidden reads: provider auth, credentials, environment secrets, and raw
  provider private data unrelated to CC_BRIDGE runtime health;
- forbidden writes: all runtime authority and tmux mutation.

## MCP Tool Surface

First batch should be read-only:

- `cc-bridge_runtime_snapshot`: daemon, keeper, lifecycle, lease, config signature,
  graph version, and mounted state summary.
- `cc-bridge_agent_status`: current graph agents, provider, pane evidence, runtime
  record, busy indicators, and restart eligibility.
- `cc-bridge_trace_lineage`: job/message/reply lineage and artifact pointers.
- `cc-bridge_queue_status`: queue, inbox, pending callback, and outstanding delivery
  summary.
- `cc-bridge_reload_plan`: dry-run config diff and reload blockers.
- `cc-bridge_storage_summary`: provider-state/storage boundary health without
  secrets.
- `cc-bridge_namespace_snapshot`: tmux session/window/pane evidence from the CC_BRIDGE
  namespace only.
- `cc-bridge_tmux_pane_list`: read-only pane/window metadata for CC_BRIDGE-owned tmux
  targets, including ids, titles, geometry, current command/path, active/dead
  flags, and known slot mapping.
- `cc-bridge_pane_capture_text`: read-only text capture for a configured CC_BRIDGE agent,
  sidebar, or managed tool window.
- `cc-bridge_pane_activity_sample`: v1 read-only sampling to distinguish active,
  idle, rendering, and stuck panes without sending keys.

Screen evidence should be a second read-only tier:

- `cc-bridge_pane_screenshot`: screenshot a CC_BRIDGE-owned pane/window/sidebar/tool target
  and return an image artifact path with metadata.
- `cc-bridge_visual_inspect`: optional OCR or vision summary over a screenshot
  artifact when text capture is insufficient.

Screen tools must never capture arbitrary desktops or unrelated tmux sessions.
They are evidence only and must not define runtime authority.

Controlled mutating tools can come later:

- `cc-bridge_restart_agent`: wraps `cc-bridge restart <agent>` only.
- `cc-bridge_repair_retry`: wraps `cc-bridge repair retry`.
- `cc-bridge_repair_resubmit`: wraps `cc-bridge repair resubmit`.
- `cc-bridge_repair_ack`: wraps `cc-bridge repair ack`.
- `cc-bridge_clear_agent`: wraps `cc-bridge clear <agent>`.
- `cc-bridge_reload_project`: wraps `cc-bridge reload`, requires a preceding
  `cc-bridge_reload_plan` or equivalent `cc-bridge reload --dry-run` result, and reports
  affected agents before mutation. Its result must say whether each affected
  agent still needs post-reload runtime refresh.

Each mutating MCP call must require explicit mutation intent, return blockers
instead of forcing busy agents by default, and report the exact CC_BRIDGE command
semantics it invoked.

For `cc-bridge_self`, explicit mutation intent can come from the user's maintenance
request, not only from a second confirmation prompt. Tools that pass all gates
may execute and then report the audit trail. Tools with blockers or destructive
scope must stop.

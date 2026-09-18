# CC_BRIDGE Self First Slice Blueprint

Date: 2026-06-09

## Goal

Define the concrete first implementable package for `agentroles.cc-bridge_self`.
This blueprint turns the role design into a Role source, while keeping CC_BRIDGE
runtime code changes separate.

Update: the first slice has been reworked for the updated Agent Roles protocol
and materialized at `/home/bfly/yunwei/agent-roles-spec/roles/cc-bridge-self`.

## Package Shape

The production role content should live in the role catalog or a local editable
role source, not inside `cc-bridge_source` production paths.

Updated Agent Roles target shape:

```text
roles/cc-bridge-self/
  README.md
  role.toml
  memory.md
  skills/
    cc-bridge-self-diagnose/SKILL.md
    cc-bridge-self-recover/SKILL.md
    cc-bridge-self-chain/SKILL.md
    cc-bridge-comm-reply-recover/SKILL.md
    cc-bridge-pane-view-diagnose/SKILL.md
    cc-bridge-config/SKILL.md
  references/
    runtime-authority.md
    tmux-cc-bridge-quickstart.md
    recovery-runbooks.md
  adapters/
    cc-bridge/
      adapter.toml
      memory.md
      tools/doctor.py
  tests/
    validation.md
  tools/
    README.md
```

Provider-specific skill folders are no longer the source shape. Host adapters
project the generic Role skills into provider-native surfaces.

## `role.toml`

Required identity:

- `id = "agentroles.cc-bridge_self"`
- display name: `CC_BRIDGE Self Maintainer`
- default agent name: `cc-bridge_self`
- category: `ops`
- purpose: CC_BRIDGE runtime self-maintenance and auxiliary recovery.

Responsibilities:

- diagnose CC_BRIDGE runtime, tmux namespace, provider pane, config, storage, and
  message-chain health;
- inspect real CC_BRIDGE-owned pane text through read-only capture when
  self-supervision cannot classify progress from control-plane evidence alone;
- recover from provider/API failures by switching to already configured or
  user-supplied provider/model/profile/env-var references;
- perform bounded autonomous maintenance under a user maintenance objective;
- own CC_BRIDGE project config design/editing through built-in `cc-bridge-config`;
- return original business work to the original target agent after repair.

Non-goals:

- do not own coding/product tasks;
- do not replace `cc-bridge-daemon`, keeper, lifecycle, mailbox, or provider authority;
- do not make other agents depend on `cc-bridge_self`;
- do not run project-wide destructive operations autonomously.

Permissions:

- filesystem: project read/write for `.cc-bridge/cc-bridge.config` only through
  `cc-bridge-config`; read-only diagnostics elsewhere unless a CC_BRIDGE control-plane
  command performs the mutation;
- secrets: none;
- network: none for v1, except role catalog update paths owned by CC_BRIDGE role
  commands. It may point users to official provider docs when asked, but it
  must not obtain, scrape, borrow, or use API keys from the internet;
- tmux: read-only pane/window evidence only.

## `memory.md`

Keep under 50 lines. It should include:

- identity and non-goals;
- failure isolation;
- authority/evidence/residue;
- config ownership;
- command boundaries;
- bounded autonomy;
- secret boundary;
- handoff rule.

Use the skeleton in [memory-and-mcp-tools.md](memory-and-mcp-tools.md) as the
starting point.

## Built-In Skills

### `cc-bridge-self-diagnose`

Entry point for "what is broken" questions. It should:

- gather structured CC_BRIDGE diagnostics and tmux pane evidence;
- classify failure domains;
- separate authority, evidence, and residue;
- choose a next skill or action.

### `cc-bridge-self-recover`

Runtime recovery. It should:

- handle provider context, pane, mount, clear, reload, and guarded restart
  flows;
- after config/API reload, re-read runtime status and pane/provider evidence
  before declaring recovery complete;
- restart only affected current-graph agents whose provider process or context
  still reflects stale startup inputs, and only when guarded restart is
  available and busy checks pass;
- run busy/pending checks before `clear` or `restart`;
- refuse force/restart-all/project shutdown without separate confirmation.

### `cc-bridge-self-chain`

Message/job lineage repair. It should:

- trace job/message/reply/artifact/callback state;
- read artifact-backed replies before acting;
- choose retry, resubmit, or ack from lineage evidence;
- hand off to recover only when process/context repair is truly needed.

### `cc-bridge-comm-reply-recover`

Communication reply recovery. It should:

- diagnose "reply not received" incidents from trace, queue, inbox, and pane
  evidence;
- identify head-of-line blockage and duplicate retries;
- prefer cancelling stale active jobs before retrying or restarting;
- use pane capture to decide whether a running job is genuinely progressing.

### `cc-bridge-pane-view-diagnose`

Pane-view self-supervision. It should:

- start from current CC_BRIDGE authority to resolve the target pane;
- use `tmux capture-pane` style text capture, biased toward the bottom/current
  prompt and recent scrollback;
- compare short-interval captures to classify active work versus stuckness;
- use screenshot fallback only when text is unavailable or insufficient;
- keep pane text and screenshots as evidence, not authority.

### `cc-bridge-config`

CC_BRIDGE config ownership. It should:

- edit `.cc-bridge/cc-bridge.config`;
- run `cc-bridge config validate` after every edit;
- run `cc-bridge reload --dry-run` before materialization;
- execute `cc-bridge reload` autonomously when gates pass and the user wants the
  change applied;
- identify affected agents that may need guarded restart after reload;
- hand affected-agent refresh decisions to `cc-bridge-self-recover`; `cc-bridge-config`
  does not perform runtime replacement itself;
- never execute `cc-bridge restart`, `cc-bridge kill`, or raw runtime writes from
  `cc-bridge-config` itself.

## References

V1 should include:

- `runtime-authority.md`: daemon graph, lifecycle, lease, runtime records,
  tmux evidence, residue, and command boundaries.
- `tmux-cc-bridge-quickstart.md`: user-facing tmux basics and safe/unsafe CC_BRIDGE tmux
  actions.
- `recovery-runbooks.md`: short operational flows, not full architecture
  contracts.
- `config-contracts.md`: config validation, reload gates, role binding,
  window/tool-window/sidebar/workspace rules.

## `tools/doctor.py`

V1 helper should be read-only and JSON-only:

```json
{
  "status": "ok|warn|error",
  "summary": "...",
  "findings": [],
  "evidence": [],
  "recommended_actions": []
}
```

Allowed reads:

- installed `cc-bridge` diagnostics;
- non-secret CC_BRIDGE logs and artifact metadata;
- daemon/runtime/config status through CC_BRIDGE CLI or stable runtime APIs;
- CC_BRIDGE-owned tmux pane/window evidence.

Forbidden:

- provider credentials or auth files;
- internet-sourced API keys or unknown third-party credentials;
- raw lifecycle/lease/runtime writes;
- raw tmux mutation;
- arbitrary screenshots.

## MCP V1

V1 MCP should prioritize read-only evidence:

- `cc-bridge_runtime_snapshot`
- `cc-bridge_agent_status`
- `cc-bridge_trace_lineage`
- `cc-bridge_queue_status`
- `cc-bridge_reload_plan`
- `cc-bridge_storage_summary`
- `cc-bridge_namespace_snapshot`
- `cc-bridge_tmux_pane_list`
- `cc-bridge_pane_capture_text`
- `cc-bridge_pane_activity_sample`
- `cc-bridge-pane-view-diagnose` should be able to consume these text artifacts as
  the default self-supervision path.

V1 mutation can remain CLI-driven through the role's normal shell commands if
MCP mutation wrappers are not ready.

## MCP V2

Add screenshot fallback and controlled mutations:

- `cc-bridge_pane_screenshot`
- `cc-bridge_visual_inspect`
- `cc-bridge_reload_project`
- `cc-bridge_clear_agent`
- `cc-bridge_repair_retry`
- `cc-bridge_repair_resubmit`
- `cc-bridge_repair_ack`
- `cc-bridge_restart_agent` after `cc-bridge restart <agent>` exists.

Screenshot artifacts must stay in CC_BRIDGE-owned project/runtime artifact storage
and must only target CC_BRIDGE-owned panes/windows/tool windows. They are fallback
evidence when text capture cannot classify the state.

## Migration Work

1. Move full config editing instructions out of inherited/global
   `cc-bridge-config` into the `agentroles.cc-bridge_self` Role.
2. Replace non-self inherited `cc-bridge-config` with a tiny delegation stub or remove
   it from non-self agents.
3. Update provider memory so non-self agents know CC_BRIDGE config changes belong to
   `cc-bridge_self`.
4. Update repo hygiene tests that currently expect inherited `cc-bridge-config`
   content.

## Validation

Use source-runtime isolation rules:

- Run source validation with `/home/bfly/yunwei/cc-bridge_source/cc-bridge_test` from
  `/home/bfly/yunwei/test_ccb2`.
- Use isolated `HOME` and `CC_BRIDGE_SOURCE_HOME` under the external test project.
- Do not run source runtime from `cc-bridge_source`.
- Do not delete active `.cc-bridge/agents/*` or `.cc-bridge/cc-bridge-daemon/*` in this work
  environment.

V1 acceptance:

- `cc-bridge roles install/add agentroles.cc-bridge_self` binds `cc-bridge_self`.
- `cc-bridge_self` receives role memory and all built-in skills.
- Non-self agents do not receive full config editing instructions.
- `cc-bridge ask cc-bridge_self "diagnose CC_BRIDGE"` can gather read-only diagnostics.
- Built-in `cc-bridge-config` follows edit -> validate -> dry-run -> safe reload.
- Provider/API config recovery verifies post-reload runtime state and either
  proves the affected agents picked up the change or reports/executes guarded
  per-agent restart when the target is restartable and busy checks pass.
- Pane evidence tools read only CC_BRIDGE-owned panes and do not mutate tmux state.
- Pane-view self-supervision can classify a stuck-provider incident from
  trace + bottom pane capture + activity sample, and uses screenshot only as
  fallback when text evidence is insufficient.

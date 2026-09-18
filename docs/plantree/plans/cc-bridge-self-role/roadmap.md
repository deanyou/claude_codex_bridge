# CC_BRIDGE Self Role Roadmap

Date: 2026-06-10

## Done

- Chose `cc-bridge_self` as the default project-local agent name.
- Chose `agentroles.cc-bridge_self` as the stable role id.
- Established that `cc-bridge_self` is an auxiliary maintenance role, not a business
  task owner.
- Established that `cc-bridge_self` failure must not affect other configured agents,
  daemon lifecycle, provider sessions, or tmux panes.
- Reviewed the current configured-agent authority boundary: restartable agent
  targets must come from the mounted daemon service graph, not disk-only config,
  tmux pane lists, or `.cc-bridge/agents/*` residue.
- Reviewed the preferred runtime restart command shape:
  `cc-bridge restart <agent>`, with `repair` kept for message/job lineage recovery.
- Reviewed tmux user/reference guidance: include practical CC_BRIDGE-managed tmux
  usage, but do not expose raw destructive tmux controls as agent tools.
- Chose four broad capability groups instead of many narrow skills:
  `cc-bridge-self-diagnose`, `cc-bridge-self-recover`, `cc-bridge-self-chain`, and built-in
  `cc-bridge-config`.
- Recorded the auxiliary-agent boundary in
  [decisions/001-auxiliary-self-agent.md](decisions/001-auxiliary-self-agent.md).
- Accepted the user's product direction that CC_BRIDGE config design/editing should
  be a built-in `cc-bridge_self` role skill, not universally available to all agents.
  See
  [decisions/002-built-in-cc-bridge-config-skill.md](decisions/002-built-in-cc-bridge-config-skill.md).
- Added the memory/tooling direction: role memory should carry identity,
  authority, command boundaries, and delegation rules; MCP tools should start
  read-only and include bounded screen evidence only for CC_BRIDGE-owned targets.
- Incorporated reviewer2's skill review: bootstrap config repair, chain/recover
  handoff, role asset update commands, v1 pane activity sampling, reload
  dry-run prerequisites, screenshot artifact storage, and config-skill test
  impact.
- Accepted stronger bounded autonomy for `cc-bridge_self`: maintenance intent allows
  autonomous read-only diagnostics, validation, dry-runs, safe reloads, supported
  chain repairs, role asset repair, and guarded single-agent recovery.
- Recorded that provider/API or startup-affecting config recovery is
  reload-then-recheck, with guarded per-agent restart when a running provider
  process or context still needs refresh.
- Defined the v1/v2 Role blueprint in
  [topics/first-slice-blueprint.md](topics/first-slice-blueprint.md).
- Drafted reviewable first-slice `agentroles.cc-bridge_self` Role content under
  [drafts/agentroles.cc-bridge_self/](drafts/agentroles.cc-bridge_self/), including role
  memory, four Codex built-in skill drafts, references, and a draft read-only
  doctor helper contract.
- Captured initial isolated validation evidence in
  [topics/skill-drafts-review-test-evidence.md](topics/skill-drafts-review-test-evidence.md):
  static role/skill checks pass, config validate and reload dry-run gates work,
  `repair retry|resubmit|ack` command semantics are visible, the initial
  `cc-bridge restart <agent>` contract blocker was captured, and catalog validation
  is blocked until `agentroles.cc-bridge_self` is materialized.
- Completed coworker and reviewer3 review loops for the four built-in skills,
  processed findings in
  [topics/skill-drafts-review-test-evidence.md](topics/skill-drafts-review-test-evidence.md),
  and fixed the remaining chain cancel-failure blocker.
- Reworked the accepted draft for the updated Agent Roles protocol and
  materialized it in `/home/bfly/yunwei/agent-roles-spec/roles/cc-bridge-self`.
  The new source uses host-neutral `skills/`, CC_BRIDGE-specific adapter metadata in
  `adapters/cc-bridge/`, catalog aliases, and tests that pass the Agent Roles CLI
  and manifest loader.
- Moved the full `cc-bridge-config` skill under `agentroles.cc-bridge_self` Role source and
  removed it from the public inherited Codex/Claude skill folders. Install
  paths now clean old public `cc-bridge-config` residue.
- Implemented guarded `cc-bridge restart <agent>` as a current-graph, single-agent
  cc-bridge-daemon control-plane operation with busy/pending/callback blockers and
  old/new runtime evidence.
- Mounted the prepared Role into the local `agent-roles-spec` catalog with
  aliases, roles index entry, mount-oriented wording, and local
  install/resolve/doctor/full-suite validation ready for the user to push.
- Collected legacy public `cc-bridge-config` residue into
  `/home/bfly/.cc-bridge/deprecated/cc-bridge-config-public-20260610T081814+0800` and
  verified the current project now exposes `cc-bridge-config` only through the
  Role-owned `cc-bridge_self` private skill symlink.
- Added the CC_BRIDGE-side 7.4.0 provisioning direction: `install.sh install` now
  attempts to install or refresh `agentroles.cc-bridge_self` as a recommended default
  Role Pack, post-update Role Pack provisioning installs missing recommended
  roles, the built-in blank-project default binds `cc-bridge_self:codex` to
  `agentroles.cc-bridge_self`, and existing custom configs can still add it with
  `cc-bridge roles add agentroles.cc-bridge_self:codex`.
- Recorded future modification guardrails in
  [decisions/006-future-modification-guardrails.md](decisions/006-future-modification-guardrails.md):
  new behavior must use canonical `agentroles.cc-bridge_self`, while maintenance
  heartbeat remains opt-in and disabled by default.
- Recorded the default install boundary in
  [decisions/004-default-recommended-install.md](decisions/004-default-recommended-install.md):
  role assets are prepared by default, but project topology changes remain
  explicit.
- Accepted the next product direction that `cc-bridge_self` should become the
  project-local CC_BRIDGE expert, not only a maintenance operator. Captured the
  expert knowledge model in
  [topics/cc-bridge-expert-knowledge-role.md](topics/cc-bridge-expert-knowledge-role.md).
- Chose the expert knowledge packaging model: keep role memory compact, add
  one broad expert lookup skill, and store CC_BRIDGE source, GitHub, command/config,
  and talk1 manual navigation in role references. See
  [decisions/005-expert-knowledge-database.md](decisions/005-expert-knowledge-database.md).
- Materialized the v1 CC_BRIDGE expert upgrade in
  `/home/bfly/yunwei/agent-roles-spec/roles/cc-bridge-self`: role version `0.2.0`,
  six built-in skills including `cc-bridge-expert-reference`, eleven role
  references including GitHub/source/manual/command/runtime/release indexes,
  compact expert routing memory, and passing `agent-roles-spec` tests.
- Chose a single user-facing maintenance workflow,
  `cc-bridge_diagnose <agentname>`, with bounded recovery, verification, and
  explicitly authorized redacted GitHub issue submission. See
  [decisions/007-unified-diagnose-entrypoint.md](decisions/007-unified-diagnose-entrypoint.md).

## In Progress

- Finish 7.4.0 release validation and push after review.
- Validate the updated `agentroles.cc-bridge_self` Role Pack through CC_BRIDGE
  install/refresh/materialization once the user wants source runtime validation.

## Next

1. Decide whether to add a separate non-self delegation stub; the full inherited
   `cc-bridge-config` source has been removed.
2. Add the v1 structured MCP/control-plane diagnostic helper contracts.
3. Add release/update awareness and knowledge-refresh once the first expert
   references prove useful.
4. Extend and verify the materialized `cc-bridge_diagnose` command/skill adapter,
   including mandatory pane-first deep diagnosis, incident-bundle/fingerprint
   handling, confirmation, and exit-status contracts.

## Deferred

- Automatic background self-healing without user request.
- `restart all` or window-level restart commands.
- Role-driven raw tmux mutation.
- Force, project-wide, or destructive repair without confirmation.
- Business-task continuation by `cc-bridge_self` after another agent fails.
- Reintroducing the full config editing skill as a global inherited skill for
  non-`cc-bridge_self` agents by default.
- Multiple maintenance roles with shared lock arbitration.
- Automatically indexing or embedding the whole CC_BRIDGE source tree before the
  manual expert-reference model proves insufficient.

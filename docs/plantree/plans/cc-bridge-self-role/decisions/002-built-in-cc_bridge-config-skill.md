# Built-In CC_BRIDGE Config Skill

Date: 2026-06-09

## Context

The user wants `cc-bridge_self` to be the CC_BRIDGE self-maintenance operator. That
includes project configuration work: designing and editing `.cc-bridge/cc-bridge.config`,
checking role bindings, understanding tmux/window layout implications,
detecting config drift, and deciding when reload or restart is needed.

CC_BRIDGE previously treated `cc-bridge-config` as a universal inherited skill available
to all agents. That is convenient, but it spreads topology-changing authority
across the whole team. For a self-maintenance role, a cleaner model is that
other agents do their business work and route CC_BRIDGE configuration changes to
`cc-bridge_self`.

Naming update: [006-future-modification-guardrails.md](006-future-modification-guardrails.md)
supersedes the early `agentroles.cc-bridge_self` spelling. The canonical Role Pack id
is now `agentroles.cc-bridge_self`.

## Decision

Make `cc-bridge-config` a built-in skill of `agentroles.cc-bridge_self`.

The canonical skill name should remain `cc-bridge-config` because it is the CC_BRIDGE
configuration skill. The skill is built directly into the
`agentroles.cc-bridge_self` Role Pack as a role-owned asset. It is not a global
inherited skill and is not a separate shared skill later assigned to the role.
When CC_BRIDGE installs or materializes the role for an agent, the built-in skill
appears only in `cc-bridge_self`'s managed provider home.

The built-in `cc-bridge-config` skill may edit `.cc-bridge/cc-bridge.config` and validate config
health. It must keep disk config, last-applied config signature, current daemon
graph, and tmux evidence separate. It may recommend reload/restart classes and
may execute `cc-bridge reload` for `cc-bridge_self` after validation gates pass and user
intent is explicit. It must not silently execute `cc-bridge reload`, and it must not
execute `cc-bridge restart` or `cc-bridge kill`.

Every config edit has a required validation gate:

1. Write the disk config change.
2. Run or require `cc-bridge config validate`.
3. If the user wants the change materialized and validation passed, run or
   require `cc-bridge reload --dry-run`.
4. Only after the dry-run plan is understood may `cc-bridge_self` execute
   `cc-bridge reload`.
5. After reload, `cc-bridge_self` must re-check affected agents. Provider command,
   provider profile, model, base URL, environment, role asset, or startup
   context changes may require a separate guarded single-agent restart.

## Consequences

- `cc-bridge_self` becomes the single normal route for CC_BRIDGE project configuration
  design, edits, drift diagnosis, and reload readiness.
- Other agents should delegate config changes to `cc-bridge_self` instead of editing
  `.cc-bridge/cc-bridge.config` directly.
- The skill can cover both design-time editing and runtime config health,
  reducing fragmentation.
- Runtime mutation remains separate from config editing: config writes affect
  disk intent; live graph changes require explicit CC_BRIDGE control-plane actions.
- Migration must remove the full inherited/global `cc-bridge-config` from non-self
  agents, or replace it with a lightweight delegation stub.

## Naming

Primary name: `cc-bridge-config`.

Rationale: users already understand the phrase, and the skill still owns CC_BRIDGE
configuration. The fact that it is private to `cc-bridge_self` should be represented
by being a built-in Role Pack skill, not by forcing the name to carry
ownership.

Acceptable alias in docs: `cc-bridge-self-config`, when the discussion needs to
emphasize the role owner.

Rejected names:

- `cc-bridge-runtime-config`: ambiguous with daemon/runtime internals.
- `cc-bridge-config-health`: too narrow once the private skill can edit disk config.
- `cc-bridge-config-maintenance`: too broad and suggests runtime mutation.
- `cc-bridge-ops-config`: less specific than `cc-bridge_self` ownership.

## Migration Notes

The transition should avoid breaking existing projects abruptly:

1. Move the full config editing skill into the `agentroles.cc-bridge_self` Role Pack
   as a built-in skill.
2. Remove the full skill from inherited/global skill sets for non-self agents.
3. Optionally leave a tiny non-self stub that says: route CC_BRIDGE config edits to
   `cc-bridge_self`; do not edit `.cc-bridge/cc-bridge.config` directly.
4. Update provider memory so non-self agents know CC_BRIDGE topology/config work is
   owned by `cc-bridge_self`.
5. Keep tests proving the built-in skill is materialized for `cc-bridge_self`.

Test impact:

- Existing repo hygiene tests that require inherited
  `inherit_skills/*/cc-bridge-config/SKILL.md` content must be updated when the full
  skill moves into `agentroles.cc-bridge_self`.
- If a non-self delegation stub remains, tests should assert that it delegates
  to `cc-bridge_self` and does not preserve full config-editing instructions.

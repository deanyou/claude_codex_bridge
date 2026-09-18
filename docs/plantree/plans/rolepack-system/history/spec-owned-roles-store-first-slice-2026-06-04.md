# Spec-Owned Roles Store First Slice

Date: 2026-06-04

## Scope

This checkpoint records the first executable bridge from CC_BRIDGE-owned Role Pack
payload management toward a spec-owned `agent-roles` package manager and
`.roles/installed` store.

## Implemented

- `agent-roles-spec` provides a preview Python CLI/package named
  `agent-roles`.
- The preview CLI owns `.roles/installed` role payload writes and stable JSON
  output for package operations.
- The preview alias table maps `cc-bridge.archi` to `agentroles.archi`.
- CC_BRIDGE reads both legacy `$XDG_DATA_HOME/cc-bridge/roles` and spec-owned
  `.roles/installed` stores for config loading, runtime projection, lock
  lookup, role status, and catalog status.
- CC_BRIDGE can delegate `roles install`, `roles update`, and `roles sync` payload
  operations to `agent-roles` when `CC_BRIDGE_AGENT_ROLES_MANAGER=1`.
- CC_BRIDGE wraps `agent-roles` missing executable, exec failure, timeout, nonzero
  JSON error, and non-JSON failure paths as Role Pack errors so the CLI emits
  `roles_status: failed` without traceback.

## Direct-Switch Delta

The initial opt-in position was superseded during the same release train. The
current direction is default-on delegation to `agent-roles`, `.roles/installed`
as the preferred store, automatic copy migration from the legacy CC_BRIDGE role store,
and `CC_BRIDGE_AGENT_ROLES_MANAGER=0` as a temporary rollback valve.

## Validation

- `agent-roles-spec`: `3 passed`
- CC_BRIDGE `test/test_rolepacks.py`: `48 passed`
- CC_BRIDGE targeted Role Pack/update/source guard/repo hygiene suite: `99 passed`
- CC_BRIDGE compileall for touched runtime modules: passed
- CC_BRIDGE and `agent-roles-spec` `git diff --check`: passed
- Real isolated `cc-bridge_test` smoke proved:
  - `cc-bridge roles install cc-bridge.archi --skip-tools` can call `agent-roles` and write
    `.roles/installed/agentroles.archi`.
  - `cc-bridge roles show cc-bridge.archi` resolves the spec-owned store snapshot as
    canonical `agentroles.archi`.

## Release Position

This slice is no longer the final release position. `v7.2.11` was created from
the opt-in handoff before cancellation completed and must be superseded by the
direct-switch migration build after review and validation.

## Residual Risks

- A globally installed incompatible `agent-roles` command could return an
  unexpected JSON schema until version negotiation is added.
- Dual-store lookup must keep old project locks resolving old content-addressed
  snapshots through the copy migration window.
- Tool hook execution remains CC_BRIDGE-owned; the package manager writes role
  payloads but does not decide CC_BRIDGE required/optional tool policy.

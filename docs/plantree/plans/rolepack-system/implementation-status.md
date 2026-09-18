# Role Pack System Implementation Status

Date: 2026-06-17

## Current Phase

Single-current `.roles` package-manager bridge and restart-based role adoption.

## Done This Phase

- `agent-roles-spec` now has a preview `agent-roles` package manager with JSON
  `list`, `install`, `update`, `sync`, `doctor`, and `resolve` commands.
- `agent-roles-spec` records the legacy alias
  `cc-bridge.archi -> agentroles.archi`.
- CC_BRIDGE runtime/config lookup reads only the spec-owned `AGENT_ROLES_STORE` /
  `~/.roles/installed` installed store.
- CC_BRIDGE role package operations delegate to `agent-roles`; the old CC_BRIDGE-owned
  installed-role writer and `CC_BRIDGE_AGENT_ROLES_MANAGER` rollback switch have been
  removed.
- CC_BRIDGE management commands migrate installed legacy role snapshots from
  `$XDG_DATA_HOME/cc-bridge/roles` into `.roles/installed` without deleting the old
  store. The legacy store is migration input only, not a runtime fallback.
- The `agent-roles` subprocess bridge now reports missing CLI, exec failures,
  timeouts, nonzero JSON errors, and non-JSON failures through the normal
  `roles_status: failed` CLI channel instead of leaking tracebacks.
- `cc-bridge roles sync --with-tools` now composes manager-owned package sync with
  CC_BRIDGE-owned tool-hook execution, and malformed sync `roles` payloads fail closed.
- `cc-bridge-config` skill docs say configs must keep canonical role ids and must not
  write local store paths such as `~/.roles` into `.cc-bridge/cc-bridge.config`.
- The target model now removes project role locks and multi-version installed
  history. `.roles` keeps one installed current package per role id, and live
  agents adopt role changes through guarded restart. See
  [decisions/007-single-current-store-and-restart-adoption.md](decisions/007-single-current-store-and-restart-adoption.md).
- `agent-roles-spec` writes installed roles to
  `.roles/installed/<role-id>/current` plus `install.json`; legacy
  `versions/<version>/<digest>` stores remain readable for compatibility.
- CC_BRIDGE role lookup and projection now follow installed current and treat
  `.cc-bridge/role-lock.json` as legacy diagnostic residue only. Role memory and
  skills are no longer suppressed by lock mismatch.
- `cc-bridge roles add` writes project config only. The role-lock writer/adopt API has
  been removed, and the remaining role-lock refresh service is a no-op
  diagnostic path.
- Provider launch session files record `cc-bridge_role_id`, `cc-bridge_role_version`, and
  `cc-bridge_role_digest`.
- `cc-bridge restart <agent>` checks launch role digest against installed current
  before respawn. If the digest changed, restart fails explicitly with
  `role_digest_changed_fresh_restart_unsupported` instead of silently resuming
  an old provider conversation.

## Active TODO

1. Add provider-specific fresh-start support for `cc-bridge restart <agent>` when the
   launch role digest differs from installed current. Current behavior is a
   safe explicit failure, not automatic adoption.
2. Add a doctor/cleanup command for old `.cc-bridge/role-lock.json` residue.
3. Remove or dev-gate the source-checkout fallback for `~/yunwei/agent-roles-spec`
   before the bridge graduates from preview.

## Blockers

- No current blocker for the single-current store and role-lock removal slice.
  Automatic provider fresh-start on role digest change remains a follow-up
  enhancement.
- `v7.2.11` was created from the earlier opt-in handoff before cancellation
  completed; `VERSION`, `cc-bridge`, README, README_zh, and CHANGELOG now target
  `v7.2.12` and mark `v7.2.11` as superseded.

## Next Commit Target

Commit only the Role Pack / Agent Roles bridge files and plan-tree updates.
Do not include unrelated ask/runtime dirty files currently present in the
worktree.

## Last Verified Commands

- In `agent-roles-spec`: `python -m pytest -q`
- In `agent-roles-spec`: `python -m compileall -q agent_roles`
- In `agent-roles-spec`: `git diff --check`
- In `cc-bridge_source`: `PYTHONPATH=lib python -m pytest -q test/test_rolepacks.py test/test_role_lock_refresh.py test/test_cli_management_update.py test/test_v2_config_loader.py test/test_cc-bridge_restart.py` (`200 passed`)
- In `cc-bridge_source`: `PYTHONPATH=lib python -m compileall -q lib/rolepacks/service.py lib/cli/services/role_lock_refresh.py lib/cc-bridge-daemon/handlers/project_restart.py lib/cli/services/runtime_launch_runtime/session_files.py lib/rolepacks/runtime_lookup.py lib/agents/config_loader_runtime/role_lookup.py`
- In `cc-bridge_source`: `git diff --check -- <rolepack/restart/plan-tree files>`
- In `cc-bridge_source`: `python -m pytest -q test/test_rolepacks.py` (`53 passed`)
- In `cc-bridge_source`: `python -m pytest -q test/test_rolepacks.py test/test_cli_management_update.py test/test_repo_hygiene.py test/test_source_runtime_guard.py` (`104 passed`)
- In `cc-bridge_source`: `python -m compileall -q lib/agents/config_loader_runtime/role_lookup.py lib/rolepacks/runtime_lookup.py lib/rolepacks/sources.py lib/rolepacks/service.py lib/rolepacks/agent_roles_manager.py`
- In `cc-bridge_source`: `git diff --check`
- In `cc-bridge_source`: `python cc-bridge --print-version` (`v7.2.12`)
- In `/home/bfly/yunwei/test_ccb2`: isolated default-switch smoke used a legacy
  `$XDG_DATA_HOME/cc-bridge/roles` install, then manager mode with
  `AGENT_ROLES_CLI=/home/bfly/yunwei/agent-roles-spec/cli/agent-roles` ran
  `cc-bridge_test roles update agentroles.archi --skip-tools` and
  `cc-bridge_test roles show cc-bridge.archi`. Current resolved from `.roles/installed`.

# Final Rolepack Validation - 2026-06-03

## Scope

Final checkpoint for the CC_BRIDGE Role Pack first slice and the external
`agentroles.archi` production role before handing release execution to agent4.

## PR State

- Repository: `https://github.com/SeemSeam/agent-roles-spec`
- PR: `https://github.com/SeemSeam/agent-roles-spec/pull/1`
- Branch: `cc-bridge/archi-production-role-20260603`
- Head: `80f0f0e Add production archi role`
- Production role path: `roles/archi`
- Canonical id: `agentroles.archi`
- Version: `0.2.0`

The PR keeps production role content out of `cc-bridge_source`. CC_BRIDGE consumes
`agent-roles-spec` as catalog authority and uses local/system/cache sources for
discovery and installation.

## Reviews

- `archi`: no blocking architecture issue. Non-blocking README wording and
  permission/network semantics were fixed in the PR.
- `agent3`: PR acceptable to merge, no blockers. Non-blocking note about
  reference/production parity is accepted for the first release; PR body now
  calls out the reference adapter enhancement.

## Fixes From Final Test

- CC_BRIDGE role hook execution sets `PYTHONDONTWRITEBYTECODE=1`.
- `agent-roles-spec` CC_BRIDGE adapter hook commands now use `python -B ...`.
- Existing polluted `versions/<version>/<digest>/` targets are repaired from a
  clean staging copy when their tree digest no longer matches the path digest.
- Project locks write the installed metadata digest so locks resolve to a real
  content-addressed snapshot path.
- `cc-bridge roles list` renders duplicate source warnings, including the opt-in
  `reference_roles/` duplicate case where production `roles/` wins.

## Automated Validation

From `/home/bfly/yunwei/cc-bridge_source`:

```text
pytest -q test/test_rolepacks.py test/test_cli_management_update.py test/test_install_script_sidebar.py test/test_agents_layout_runtime.py test/test_v2_ask_service.py test/test_v2_config_loader.py test/test_build_linux_release_script.py test/test_source_runtime_guard.py
209 passed
```

Additional checks:

- `git diff --check` passed in `cc-bridge_source`.
- `git diff --check` passed in `agent-roles-spec`.
- Production/reference role TOML parsed.
- Production/reference CC_BRIDGE adapter tool Python files passed AST syntax
  compilation without generating pyc.
- `agent-roles-spec/roles` and `agent-roles-spec/reference_roles` had no
  `__pycache__` or `*.pyc` files after validation.

## Real Test Project

Project: `/home/bfly/yunwei/test_ccb2/roles_release.zoFqSP`

Environment:

- `AGENT_ROLES_SPEC_HOME=/home/bfly/yunwei/agent-roles-spec`
- `XDG_DATA_HOME=/home/bfly/yunwei/test_ccb2/roles_release.zoFqSP/.xdg-data`
- `XDG_CACHE_HOME=/home/bfly/yunwei/test_ccb2/roles_release.zoFqSP/.xdg-cache`

Validated:

- `cc-bridge roles list` default catalog shows production `agentroles.archi`.
- `CC_BRIDGE_AGENT_ROLES_INCLUDE_REFERENCE=1 cc-bridge roles list` shows production wins
  and renders the ignored reference duplicate warning.
- `cc-bridge roles install/update agentroles.archi` runs Architec tool hooks
  successfully in the isolated XDG data root.
- `cc-bridge roles doctor agentroles.archi` reports the managed wrapper and
  `llmgateway` config.
- `cc-bridge roles add agentroles.archi:codex --window main` writes shorthand config
  and `.cc-bridge/role-lock.json`.
- Final installed/locked production digest:
  `sha256:ca22724106f53fb984dac94f4ef279729c557062df5b4e7107c1062ae0bf67ba`.
- Installed current and project lock digests matched after explicit re-add.
- Lock pinning held across installed-current drift; role memory stayed on the
  locked digest until explicit re-add.
- `cc-bridge roles sync <path>` updated installed current without changing project
  locks.
- No-argument `cc-bridge roles sync` used the current working directory as the only
  sync boundary.
- Codex projection found role memory and skills:
  `archi-advice`, `archi-diff`, `archi-full`, `archi-goal`,
  `archi-tooling`.
- Materialized Codex home contained `AGENTS.md` with role memory and adapter
  memory plus projected role skills.
- `cc-bridge` startup mounted `agent1` and `archi`.
- `cc-bridge reload` returned `no_change` without destabilizing runtime.
- `cc-bridge doctor` reported `cc-bridge-daemon_state: mounted`, `cc-bridge-daemon_health: healthy`, and
  `archi` bound to a live tmux pane.

## Residuals

- `cc-bridge ask archi` was not submitted in this checkpoint because CC_BRIDGE ask is
  submit-only and the next CC_BRIDGE ask is reserved for the release handoff to
  agent4. Ask routing remains covered by automated ask-service tests, and the
  mounted runtime accepted the `archi` agent as bound and healthy.
- `agent-roles-spec` still has local untracked `.architec/` evidence; it is
  not part of PR #1.
- Follow-up architecture work remains around warning-only missing locked
  content, explicit projection refresh/adopt, concurrency safety, and tool-hook
  rollback/degraded metadata.

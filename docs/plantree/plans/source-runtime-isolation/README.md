# Source Runtime Isolation Plan

Date: 2026-06-09

## Purpose

Keep CC_BRIDGE source editing, source-under-test validation, and stable installed
work-environment usage separated. The target developer flow is:

1. Edit source in `/home/bfly/yunwei/cc-bridge_source`.
2. Validate current source through `/home/bfly/yunwei/cc-bridge_source/cc-bridge_test`.
3. Run stateful source tests only from `/home/bfly/yunwei/test_ccb2`.
4. Keep normal project collaboration on the installed-release `cc-bridge`.

This prevents a live source checkout or source test from changing the current
development CC_BRIDGE environment or other CC_BRIDGE projects.

## File Map

- [roadmap.md](roadmap.md): current readiness and follow-up implementation
  sequence.
- [topics/development-workflow.md](topics/development-workflow.md): operator
  workflow, command lanes, and validation contract.
- [topics/repository-cleanup-and-filesystem-plan.md](topics/repository-cleanup-and-filesystem-plan.md):
  cleanup rules for source checkout runtime state, test projects, and wrapper
  path hygiene.
- [topics/stable-entrypoint-boundary.md](topics/stable-entrypoint-boundary.md):
  stable installed `cc-bridge` authority, temporary-prefix drift findings, and
  wrapper/doctor gates.
- [decisions/001-installed-cc-bridge-authority.md](decisions/001-installed-cc-bridge-authority.md):
  stable installed `cc-bridge` remains the work-environment authority.

## Related Sources

- [../../../cc-bridge](../../../cc-bridge)
- [../../../cc-bridge_test](../../../cc-bridge_test)
- [../../../test/test_source_runtime_guard.py](../../../test/test_source_runtime_guard.py)
- [../../baseline/test-and-release-gates.md](../../baseline/test-and-release-gates.md)
- [../install-update-stability/topics/validation-runbook.md](../install-update-stability/topics/validation-runbook.md)

## Scope

In scope:

- Source checkout entrypoint discipline.
- `cc-bridge_test` source-under-test workflow and test-project boundaries.
- `/home/bfly/yunwei/test_ccb2` as the default dedicated stateful test anchor.
- Project memory and runbook wording that prevents agents from using source
  runtime commands in the work environment.
- Cleanup policy for source checkout `.cc-bridge` runtime state and test-project
  residue.

Out of scope:

- Publishing a release or changing the globally installed `cc-bridge`.
- Deleting active project agents in `/home/bfly/yunwei/cc-bridge_source/.cc-bridge`.
- Replacing provider authentication or provider-native account configuration.
- Migrating every historical plan note that mentions older `cc-bridge_test` command
  examples.

## Non-Drift Contract

- `/home/bfly/yunwei/cc-bridge_source` is source code plus an installed-release work
  environment, not the stateful source-test project.
- Source changes must not change what the installed-release `cc-bridge` imports for
  normal collaboration.
- Normal bare `cc-bridge` startup must resolve to a stable installed-release prefix,
  not to `/tmp`, the source checkout, or a disposable install/update smoke
  prefix.
- Stateful source validation uses `/home/bfly/yunwei/cc-bridge_source/cc-bridge_test` from
  `/home/bfly/yunwei/test_ccb2` by default. Any other external test project
  requires an explicit `CC_BRIDGE_TEST_ROOTS` or `CC_BRIDGE_SOURCE_ALLOWED_ROOTS`
  override.
- Runbooks should prefer the absolute source `cc-bridge_test` wrapper because `PATH`
  can contain old release or smoke-test wrappers.
- `cc-bridge_test --diagnose` is the lightweight preflight for wrapper/root
  ambiguity; it must not start or mutate a project backend.
- Provider/account state for source validation should use
  `/home/bfly/yunwei/test_ccb2/source_home` through `HOME` and
  `CC_BRIDGE_SOURCE_HOME`, unless the test intentionally exercises inherited real
  provider configuration.
- `.cc-bridge/agents/*`, `.cc-bridge/cc-bridge-daemon/*`, tmux sockets, and provider-state directories
  under the source checkout are work-environment runtime state. They are not
  source-test cleanup targets.
- `CC_BRIDGE_SOURCE_RUNTIME_OK=1` is a narrow diagnostics override, not a normal
  developer workflow; agents should not set it unless the user explicitly asks
  for that diagnostic bypass.

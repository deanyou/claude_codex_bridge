# Source Runtime Isolation Roadmap

Date: 2026-06-09

## Done

- `cc-bridge` has a source-checkout guard that refuses stateful commands outside
  allowed external test roots while still allowing safe introspection.
- `cc-bridge_test` wraps the source checkout and refuses to run from
  `/home/bfly/yunwei/cc-bridge_source` or against a project inside the source
  checkout.
- `test/test_source_runtime_guard.py` covers the source entrypoint guard,
  `cc-bridge_test` external-project behavior, and source-checkout rejection.
- Project memory now states that source validation must use `cc-bridge_test` from an
  external project and must not install source changes into the global/system
  environment.
- Default source-test roots are narrowed to `/home/bfly/yunwei/test_ccb2` for
  both `cc-bridge` and `cc-bridge_test`; legacy sibling directories require explicit
  `CC_BRIDGE_SOURCE_ALLOWED_ROOTS` or `CC_BRIDGE_TEST_ROOTS` overrides.
- `cc-bridge_test` preflight now rejects arbitrary external CWD and `--project`
  targets unless they are under an allowed source-test root.
- `cc-bridge_test --diagnose` reports the running wrapper, source `cc-bridge`, CWD,
  project paths, default roots, explicit env roots, effective roots, checked
  paths, and whether the current invocation is allowed as a source-test
  project.
- The 2026-06-15 stable-entrypoint closure added `cc-bridge doctor` entrypoint and
  daemon implementation-root diagnostics, added installer protection against
  temporary-prefix installs writing external bin dirs, and restored
  `/home/bfly/.local/bin/cc-bridge` to the durable installed release. See
  [topics/stable-entrypoint-boundary.md](topics/stable-entrypoint-boundary.md).

## In Progress

- Make the operational workflow explicit in project memory, baseline gates,
  and active runbooks so agents stop treating source validation as a normal
  `cc-bridge` command.
- Record cleanup rules for project-agent runtime state so active installed
  work-environment state is not deleted during source testing.
- Track restart hygiene for already-running project daemons that may still have
  inherited the old temporary smoke-prefix PATH or implementation root.

## Next

1. Add a test or hygiene check that active runbooks use the absolute source
   wrapper when validating current source changes.
2. Define an explicit test-project reset procedure for
   `/home/bfly/yunwei/test_ccb2` that stops its backend before removing
   disposable runtime residue.
3. Add a small restart runbook for moving live projects off a temporary
   implementation root without deleting project runtime state.

## Deferred

- Automatic migration or deletion of old ad hoc test directories under
  `/home/bfly/yunwei`.
- Automatically repairing user shell startup files or global PATH order.
- Removing diagnostic overrides such as `CC_BRIDGE_SOURCE_RUNTIME_OK=1`.

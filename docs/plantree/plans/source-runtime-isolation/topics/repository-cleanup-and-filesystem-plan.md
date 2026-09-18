# Repository Cleanup And Filesystem Plan

Date: 2026-06-09

## Purpose

Define what can and cannot be cleaned while separating source development from
the installed CC_BRIDGE work environment.

## Current Inventory

- `/home/bfly/yunwei/cc-bridge_source` is the source checkout and also has an active
  installed-release CC_BRIDGE work environment under `.cc-bridge`.
- On 2026-06-09, `.cc-bridge/cc-bridge-daemon/lifecycle.json` in `cc-bridge_source` reported
  `desired_state: running`, `phase: mounted`, and generation `161`.
- On 2026-06-09, `.cc-bridge` in `cc-bridge_source` was about `1.5G`, with active agent
  directories for `main`, `bugb`, `worker1`, `worker2`, `worker3`, `reviewer1`,
  `reviewer2`, `reviewer3`, `archi`, `push`, and `coworker`.
- `/home/bfly/yunwei/test_ccb2` is the only default external
  source-validation project and already contains `.cc-bridge`, provider homes, and
  `source_home`.
- Other sibling test directories exist under `/home/bfly/yunwei`, including
  `test_cc-bridge`, `cc-bridge_test2`, `test_cc-bridge_provider_memory_matrix`, and timestamped
  smoke directories. They are not default source-test roots; use
  `CC_BRIDGE_TEST_ROOTS` or `CC_BRIDGE_SOURCE_ALLOWED_ROOTS` when one is intentionally
  under test.
- On 2026-06-09, `PATH` resolved bare `cc-bridge` and `cc-bridge_test` to
  `/tmp/cc-bridge-v7.2.1-install-smoke/prefix` before `~/.local/bin`. Treat bare
  wrapper commands as ambiguous until verified.

## Target Structure

- `cc-bridge_source`: source files, durable docs/plans, and installed-release
  work-environment `.cc-bridge` state only.
- `test_ccb2`: default stateful source-under-test project.
- Temporary install/update simulations: isolated homes and prefixes outside
  `cc-bridge_source`, preferably disposable directories under `/tmp` or clearly named
  sibling test directories.

## Keep / Move / Archive / Delete Rules

- Keep `.cc-bridge/cc-bridge.config`, `.cc-bridge/cc-bridge_memory.md`, `AGENTS.md`, and active
  provider-state in `cc-bridge_source` unless the task is explicitly to reset the
  work environment.
- Do not delete `cc-bridge_source/.cc-bridge/agents/*` or `cc-bridge_source/.cc-bridge/cc-bridge-daemon/*` during
  source validation.
- Test-project runtime residue may be cleaned only after the corresponding
  test backend is stopped.
- Historical test directories should be archived or deleted only after their
  purpose, owner, and rollback value are recorded.
- Global wrappers and shell PATH should be audited before repair; do not
  silently repoint system `cc-bridge` to a source checkout.
- Do not add `CC_BRIDGE_SOURCE_ALLOWED_ROOTS` or `CC_BRIDGE_TEST_ROOTS` to persistent shell
  startup files. Use them only around one explicit source-validation command or
  script.

## Cleanup Sequence

1. Record `git status --short` in `cc-bridge_source`.
2. Record wrapper resolution with `command -v cc-bridge`, `command -v cc-bridge_test`, and
   `readlink -f`.
3. If cleaning `/home/bfly/yunwei/test_ccb2`, first run:

   ```bash
   cd /home/bfly/yunwei/test_ccb2
   /home/bfly/yunwei/cc-bridge_source/cc-bridge_test kill
   ```

4. Remove only test-project runtime artifacts that are known generated state,
   such as its `.cc-bridge/cc-bridge-daemon`, `.cc-bridge/agents`, and provider session files.
5. Recreate or validate the test anchor with:

   ```bash
   cd /home/bfly/yunwei/test_ccb2
   HOME=/home/bfly/yunwei/test_ccb2/source_home \
   CC_BRIDGE_SOURCE_HOME=/home/bfly/yunwei/test_ccb2/source_home \
   /home/bfly/yunwei/cc-bridge_source/cc-bridge_test config validate
   ```

## Safety Checks

- `./cc-bridge doctor` from `cc-bridge_source` should refuse stateful source-checkout
  execution unless an explicit diagnostic override is set.
- `/home/bfly/yunwei/cc-bridge_source/cc-bridge_test doctor` should refuse when run from
  `cc-bridge_source`.
- The same `cc-bridge_test doctor` should run from `/home/bfly/yunwei/test_ccb2`.
- `/home/bfly/yunwei/cc-bridge_source/cc-bridge_test --diagnose` should show the source
  wrapper, effective roots, and `allowed_source_test_project: yes` from
  `/home/bfly/yunwei/test_ccb2`.
- Installed work-environment `cc-bridge` should not import from
  `/home/bfly/yunwei/cc-bridge_source/lib`.
- No cleanup task should leave another CC_BRIDGE project pointing at
  `/home/bfly/yunwei/cc-bridge_source` as its runtime implementation.

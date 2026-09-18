# Installed CC_BRIDGE Owns The Work Environment

Date: 2026-06-09

## Context

The source checkout `/home/bfly/yunwei/cc-bridge_source` is also used as a live CC_BRIDGE
collaboration project. When source edits, source runtime tests, and installed
work-environment commands share wrappers or runtime state, a code change can
appear to affect the current development environment or other CC_BRIDGE projects.

The repo already has guarded source entrypoints, but operational instructions
and runbooks still need a durable authority statement.

## Decision

The installed-release `cc-bridge` is the authority for normal work-environment CC_BRIDGE
collaboration in `cc-bridge_source`. Current source changes are validated only
through `/home/bfly/yunwei/cc-bridge_source/cc-bridge_test` from the default external test
project `/home/bfly/yunwei/test_ccb2`, unless another external root is
explicitly allowed with `CC_BRIDGE_TEST_ROOTS` or `CC_BRIDGE_SOURCE_ALLOWED_ROOTS`.

Source validation must not delete or rewrite `cc-bridge_source/.cc-bridge/agents`,
`cc-bridge_source/.cc-bridge/cc-bridge-daemon`, provider-state directories, or global/system wrappers.
Promotion from source to the installed environment is an explicit install,
update, or release action after validation gates pass.

## Consequences

- Agents should not suggest bare `cc-bridge` or source `./cc-bridge` commands for
  source-change validation.
- Runbooks should use the absolute source `cc-bridge_test` wrapper or first prove the
  bare command resolves to that wrapper.
- Cleanup of project agents in `cc-bridge_source` is work-environment maintenance,
  not source-test cleanup.
- Future implementation can narrow default allowed test roots or add wrapper
  diagnostics without changing the operator contract.

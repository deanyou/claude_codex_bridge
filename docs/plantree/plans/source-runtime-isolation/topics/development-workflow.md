# Development Workflow

Date: 2026-06-09

## Goal

Make every CC_BRIDGE development lane explicit:

- edit source in `/home/bfly/yunwei/cc-bridge_source`
- validate source with `/home/bfly/yunwei/cc-bridge_source/cc-bridge_test`
- run stateful validation from `/home/bfly/yunwei/test_ccb2`
- keep normal collaboration on the installed-release `cc-bridge`

## Work-Environment Lane

Use this lane for normal project collaboration in `cc-bridge_source`.

- The active `.cc-bridge` backend, configured agents, provider sessions, and tmux
  state belong to the installed-release work environment.
- Use installed-release `cc-bridge` and `ask` for ordinary collaboration.
- Do not run `./cc-bridge`, `python cc-bridge`, or source `cc-bridge_test` from this checkout for
  normal work-environment commands.
- Do not delete `.cc-bridge/agents/*` or `.cc-bridge/cc-bridge-daemon/*` as source cleanup. If the
  work environment itself must be reset, do that as an explicit installed-cc-bridge
  maintenance task.

## Source-Under-Test Lane

Use this lane after modifying source.

```bash
cd /home/bfly/yunwei/test_ccb2
export HOME=/home/bfly/yunwei/test_ccb2/source_home
export CC_BRIDGE_SOURCE_HOME=/home/bfly/yunwei/test_ccb2/source_home
/home/bfly/yunwei/cc-bridge_source/cc-bridge_test doctor
/home/bfly/yunwei/cc-bridge_source/cc-bridge_test config validate
```

For stateful smoke tests, keep using the same absolute source wrapper:

```bash
cd /home/bfly/yunwei/test_ccb2
export HOME=/home/bfly/yunwei/test_ccb2/source_home
export CC_BRIDGE_SOURCE_HOME=/home/bfly/yunwei/test_ccb2/source_home
/home/bfly/yunwei/cc-bridge_source/cc-bridge_test
/home/bfly/yunwei/cc-bridge_source/cc-bridge_test doctor
/home/bfly/yunwei/cc-bridge_source/cc-bridge_test kill
```

The absolute wrapper matters because `PATH` can contain a release or smoke-test
copy of `cc-bridge_test`. If a runbook intentionally uses a bare command, first
record:

```bash
command -v cc-bridge_test
readlink -f "$(command -v cc-bridge_test)"
```

Use the wrapper diagnostic when the path or root selection is uncertain:

```bash
cd /home/bfly/yunwei/test_ccb2
/home/bfly/yunwei/cc-bridge_source/cc-bridge_test --diagnose
```

`/home/bfly/yunwei/test_ccb2` is the only default stateful source-test root.
Other external projects must be explicitly allowed:

```bash
export CC_BRIDGE_TEST_ROOTS=/path/to/temporary-source-test-project
/home/bfly/yunwei/cc-bridge_source/cc-bridge_test config validate
```

## Update And Promotion Lane

Source validation does not update the installed work environment. Promotion is
a separate operation:

- Release simulations use isolated `HOME`, `XDG_*`, `CODEX_INSTALL_PREFIX`,
  and `CODEX_BIN_DIR` values.
- Managed `cc-bridge update` validation belongs in isolated install/update smoke
  projects, not in the source checkout's live `.cc-bridge` state.
- The global/system `cc-bridge` should be changed only after source validation,
  release packaging, and install/update gates are accepted.
- Do not leave `CC_BRIDGE_SOURCE_ALLOWED_ROOTS` or `CC_BRIDGE_TEST_ROOTS` in a long-lived
  shell profile. They are per-test overrides for source validation.

## Guardrails

- `cc-bridge_test` must not run from `/home/bfly/yunwei/cc-bridge_source`.
- `cc-bridge_test --project` must not point inside `/home/bfly/yunwei/cc-bridge_source`.
- `cc-bridge_test` must not run from sibling legacy test directories such as
  `/home/bfly/yunwei/test_cc-bridge` or `/home/bfly/yunwei/cc-bridge_test2` unless
  `CC_BRIDGE_TEST_ROOTS` or `CC_BRIDGE_SOURCE_ALLOWED_ROOTS` explicitly allows them.
- `CC_BRIDGE_SOURCE_RUNTIME_OK=1` is only for explicit diagnostics; do not set it for
  ordinary development validation.
- `HOME` and `CC_BRIDGE_SOURCE_HOME` should point at the test project's
  `source_home` unless the test is specifically about inherited real provider
  configuration.
- Before a long stateful test, verify no stale test backend is still running:

```bash
cd /home/bfly/yunwei/test_ccb2
/home/bfly/yunwei/cc-bridge_source/cc-bridge_test doctor
```

# Stable Entrypoint Boundary

Date: 2026-06-15

## User Requirement

Normal `cc-bridge` startup must always use the stable installed release selected for
the user work environment. Editing source files, running source validation, or
running install/update smoke tests must not change what a bare `cc-bridge` imports or
which runtime root an existing project backend uses.

## Finding And Closure

This was not fully true in the local environment at the start of the
2026-06-15 audit.

Observed on 2026-06-15:

- `command -v cc-bridge` resolves to `/tmp/cc-bridge-v7.2.1-install-smoke/prefix/cc-bridge`.
- `/home/bfly/.local/bin/cc-bridge` is a symlink to
  `/tmp/cc-bridge-v7.2.1-install-smoke/prefix/cc-bridge`.
- The live `cc-bridge_source` keeper and daemon run from
  `/tmp/cc-bridge-v7.2.1-install-smoke/prefix/lib/cc-bridge-daemon/...`, with
  `PYTHONPATH=/tmp/cc-bridge-v7.2.1-install-smoke/prefix/lib`.
- Multiple other live project daemons also run from the same temporary smoke
  prefix.
- The normal historical installed tree still exists at
  `/home/bfly/.local/share/codex-dual`, but it is no longer the first bare
  `cc-bridge` authority.

The source entrypoint guards and absolute `cc-bridge_test` workflow protect source
validation, but they do not by themselves protect the global installed
entrypoint from install/update smoke pollution.

Closed on 2026-06-15:

- `cc-bridge doctor` now reports `entrypoint_*` fields for the resolved bare `cc-bridge`,
  its realpath, expected install path, and match status.
- `cc-bridge doctor` now reports `cc-bridge-daemon_implementation_*` fields so temporary daemon
  implementation roots can be surfaced when the process cmdline is available.
- `install.sh install` now refuses a temporary `CODEX_INSTALL_PREFIX` when
  `CODEX_BIN_DIR` is outside the same temporary prefix or temporary HOME,
  unless `CC_BRIDGE_ALLOW_TEMP_INSTALL_GLOBAL_BIN=1` is explicitly set.
- `/home/bfly/.local/bin/cc-bridge` was restored to
  `/home/bfly/.local/share/codex-dual/cc-bridge`.
- The active `cc-bridge_source` tmux server global `PATH` was updated to remove
  `/tmp/cc-bridge-v7.2.1-install-smoke/prefix/bin` and
  `/tmp/cc-bridge-v7.2.1-install-smoke/prefix`, so newly created panes no longer
  inherit that temporary prefix first.
- A clean shell PATH resolves `cc-bridge` to the durable installed release
  `v7.2.1`.

Residual operational note:

- Already-running CC_BRIDGE panes and project daemons may still have inherited the
  old `/tmp/cc-bridge-v7.2.1-install-smoke/prefix` process environment or
  implementation root until those projects are restarted through the durable
  installed `cc-bridge`.

## Boundary Contract

- A release/update smoke test may use temporary `HOME`, `XDG_*`,
  `CODEX_INSTALL_PREFIX`, and `CODEX_BIN_DIR`, but it must not rewrite the
  user's real `~/.local/bin/cc-bridge` or persistent shell startup files.
- Bare `cc-bridge` in a normal project must resolve to a stable managed install
  prefix, not to `/tmp`, a source checkout, or a disposable release simulation
  prefix.
- `cc-bridge_test` may point at the source checkout only when invoked through the
  absolute source wrapper or after an explicit wrapper-resolution preflight.
- A project backend should record enough runtime-root evidence for `doctor` to
  flag a daemon whose implementation root is a temporary smoke prefix.
- Rich terminal launchers must drop inherited `TMUX`, `TMUX_PANE`,
  `CC_BRIDGE_TMUX_SOCKET`, and `CC_BRIDGE_TMUX_SOCKET_PATH` before opening a new terminal
  so nested startup cannot apply tmux UI changes to the wrong outer session.

## Required Gates

- `command -v cc-bridge` and `readlink -f "$(command -v cc-bridge)"` are recorded before
  work-environment startup and before declaring source validation complete.
- A stable-entrypoint audit fails if bare `cc-bridge` resolves under `/tmp`, under
  `/home/bfly/yunwei/cc-bridge_source`, or under a known smoke-test prefix.
- Install/update smoke tests prove `CODEX_BIN_DIR` and `CODEX_INSTALL_PREFIX`
  are isolated and do not mutate real user wrappers or shell rc files.
- `cc-bridge doctor` reports the implementation root for the current daemon and
  warns when that root is temporary.
- Restarting a normal project after source edits still starts from the stable
  installed release, not from the edited checkout.

## Verification

- `pytest -q test/test_doctor_runtime_identity.py test/test_install_root_confirmation.py`
  passed.
- `pytest -q test/test_v2_tmux_cleanup_history.py test/test_doctor_runtime_identity.py test/test_install_root_confirmation.py test/test_cli_management_install.py test/test_cli_management_update.py`
  passed.
- `HOME=/home/bfly/yunwei/test_ccb2/source_home CC_BRIDGE_SOURCE_HOME=/home/bfly/yunwei/test_ccb2/source_home /home/bfly/yunwei/cc-bridge_source/cc-bridge_test --diagnose`
  passed from `/home/bfly/yunwei/test_ccb2`.
- Source `cc-bridge_test doctor` flagged the polluted inherited bare `cc-bridge` as
  `entrypoint_status: degraded` with
  `entrypoint_reason: bare_cc-bridge_resolves_under_temporary_directory`.
- `env -i HOME=/home/bfly USER=bfly SHELL=/bin/zsh PATH=/home/bfly/.local/bin:/usr/local/bin:/usr/bin:/bin zsh -lc 'command -v cc-bridge; readlink -f "$(command -v cc-bridge)"; cc-bridge --print-version'`
  resolved to `/home/bfly/.local/share/codex-dual/cc-bridge` and printed `v7.2.1`.

## Open Work

1. Add a small operator runbook for restarting affected live projects through
   the durable installed release without deleting project runtime state.
2. Extend managed update coverage so tarball update simulations also prove they
   cannot mutate real user wrappers or shell startup files.

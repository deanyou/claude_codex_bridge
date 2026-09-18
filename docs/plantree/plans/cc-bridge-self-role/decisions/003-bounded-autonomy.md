# Bounded Autonomy

Date: 2026-06-09

## Context

The user wants `cc-bridge_self` to have stronger autonomy. A maintenance role that
only recommends commands would be too slow and would force the user to perform
every routine recovery step manually.

At the same time, `cc-bridge_self` must not become `cc-bridge-daemon`, bypass authority files,
or perform destructive project-wide operations without clear intent.

## Decision

Give `cc-bridge_self` bounded autonomy.

When the user gives a maintenance objective, `cc-bridge_self` may independently run
read-only diagnostics, tmux pane evidence tools, config validation, reload
dry-runs, safe config reloads after gates, supported message-chain repairs,
role asset repairs for itself, and guarded single-agent context recovery.
After provider/API or startup-affecting config changes, safe reload is only the
config materialization step; `cc-bridge_self` must re-check affected agents and may
perform guarded per-agent restart when stale running provider state remains.

It must stop for blockers or explicit confirmation before project-wide
shutdown, force actions, restart-all, raw tmux mutation, direct authority-file
writes, or any action involving secrets.

## Consequences

- `cc-bridge_self` can actually repair CC_BRIDGE workflows instead of only advising.
- Users do not need to approve every `doctor`, `trace`, pane capture,
  `config validate`, `reload --dry-run`, safe reload, or gated affected-agent
  restart step.
- Risky actions remain bounded by daemon graph authority, busy checks,
  dry-run plans, and hard red lines.
- The role's replies must include an audit trail of autonomous commands and
  changed state.

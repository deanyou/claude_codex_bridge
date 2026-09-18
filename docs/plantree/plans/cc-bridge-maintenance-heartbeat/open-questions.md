# CC_BRIDGE Maintenance Heartbeat Open Questions

Date: 2026-06-10

## Resolved Direction

- Runner shape: use a hybrid installed CC_BRIDGE command family such as
  `cc-bridge maintenance tick|status|schedule|enable|disable`. External schedulers,
  manual users, and sanctioned assessor requests call the same one-shot surface.
  Do not put the periodic tick inside cc-bridge-daemon or keeper.
- Scope: diagnose all configured agents from cc-bridge-daemon diagnostics and CC_BRIDGE
  communication state. The default escalation target is `cc-bridge_self`, but the
  assessor must be configurable and not hard-coded.
- Escalation: risk, unknown, or unhealthy states send a bounded diagnostic
  package to the configured assessor. Healthy idle state exits without waking a
  provider.
- V1 actions: assessor advice is limited to `report_only`, `ask_user`, and
  validated schedule recommendations. Mutating repair is deferred.
- State namespace: keep schedule and lock state in a dedicated heartbeat
  namespace under `.cc-bridge/cc-bridge-daemon/`, separate from keeper and cc-bridge-daemon lifecycle locks.
- Config/startup: effective `cc-bridge.config` enables heartbeat and selects the
  assessor. Normal `cc-bridge` project startup ensures the independent runner when
  heartbeat is enabled and the configured assessor exists.
- Escalation transport: v1 uses `ask --silence` to send bounded diagnostics to
  `self`/the configured assessor, so the runner does not wait for provider
  semantic analysis.
- Delayed recheck: if `self` needs to diagnose again later, it registers a
  CC_BRIDGE-owned follow-up through the maintenance schedule surface. The runner
  performs the later re-snapshot and only re-asks `self` if the condition is
  still ambiguous or unhealthy.
- Activation abstraction: heartbeat-to-self dispatch should use a reusable CC_BRIDGE
  scheduled-activation envelope so future schedule features can send bounded
  tasks to other configured agents through the same policy gates.
- Activation conditions: runtime state checks and scheduled follow-ups are
  condition producers. They produce one `ActivationIntent` structure, and
  dispatch remains a separate CC_BRIDGE policy step. V1 target scope is limited to
  `self` / `cc-bridge_self`.
- First safe slice defaults: `[maintenance.heartbeat]` is disabled by default,
  default assessor is `cc-bridge_self`, default interval is `3600` seconds, default
  minimum interval is `300` seconds, default unknown cap is `3`, default
  escalation policy is `report_only`, and `startup_ensure` defaults to `true`.
- One-shot tick snapshot source: enabled `cc-bridge maintenance tick` uses mounted
  daemon `project_view` as the preferred bounded snapshot and local `ps` as
  fallback.
- Activation dispatch: non-healthy due ticks write an `ActivationIntent` audit
  record to `activations.jsonl`, use `from_actor=maintenance-heartbeat`, submit
  one `ask --silence` through daemon `submit`, and suppress active or recent
  duplicate maintenance activations.
- Schedule command: `cc-bridge maintenance schedule --after <duration>
  [--reason <text>]` writes the next CC_BRIDGE-owned follow-up time and enforces
  `min_interval_s`.
- Unknown cap: when `unknown_streak` reaches `unknown_streak_cap`, cadence
  backs off to `interval_s` and `needs_user=true`.
- Locking: heartbeat operations use independent
  `.cc-bridge/cc-bridge-daemon/maintenance-heartbeat/lock.json` file locking, separate from
  keeper, lease, startup, and daemon locks.
- Startup ensure: normal `cc-bridge` startup runs a non-fatal due tick when heartbeat
  is enabled, `startup_ensure=true`, and the configured assessor exists.
- Enable/disable: v1 keeps enablement as config authority; `cc-bridge maintenance
  enable/disable` do not edit `.cc-bridge/cc-bridge.config`.
- Pane-view self-supervision: heartbeat does not read panes or screenshot every
  tick. For ambiguous execution progress, it passes target references and
  inconclusive reasons to `cc-bridge_self`; the assessor requests CC_BRIDGE-owned
  `tmux capture-pane` style bottom/current text, activity samples, and only
  then screenshot or visual inspection fallback through sanctioned read-only
  tools.
- Schedule consumption: v1 schedule-only state is insufficient. The next slice
  should add a CC_BRIDGE-owned project-scoped schedule consumer helper, ensured by
  normal project startup, that consumes due `schedule.json` entries and invokes
  the existing one-shot tick. Host OS scheduler installation remains deferred.
- Active anomaly detection: do not add `mode = "aggressive"` or another
  behavior branch. Pane/protocol/hook/control-plane conflict detection belongs
  to the single default heartbeat classifier; cadence, deduplication,
  escalation target, and policy gates control how often it wakes the assessor.

## Product

1. What default cadence is acceptable for healthy projects, and what minimum
   cadence prevents noisy self-wakeup loops?
2. Should heartbeat results be shown in `cc-bridge doctor`, sidebar status, both, or
   only in diagnostics files at first?

## Authority And Safety

1. Should an assessor be allowed to request schedule changes directly through a
   control-plane command, or should it only return structured advice that CC_BRIDGE
   validates and applies?
2. What actions remain report-only unless the user has separately enabled
   autonomous repair policy?

## Implementation

1. What snapshot fields are required for semantic assessment without making the
   prompt too large?
2. What is the fallback when the configured assessor is degraded or unable to
   answer after a successful activation?
3. What exact skill/command surface should the default `cc-bridge_self` assessor use
   to trigger the
   independent runner: one-shot tick, schedule-next, enable/disable, or all of
   these?
4. Does the later semantic diagnostic payload need fields not already exposed
   by `project_view`, local `ps`, and maintenance heartbeat status?
5. Should active follow-ups live inline in `schedule.json`, in a separate
   `followups/` directory, or in a compact append-only event file with a
   materialized current-state view?
6. What parts of the scheduled-activation envelope should become public CLI
   surface in v1, and what should remain internal until scheduled tasks to
   arbitrary agents are designed?
7. Which `ActivationIntent` fields should be stable enough for future
   non-heartbeat producers, and which should stay heartbeat-private until a
   second producer exists?
8. Should `cc-bridge maintenance enable/disable` edit `.cc-bridge/cc-bridge.config`, update only
   runtime schedule state, or be deferred until a config-editing policy exists?
9. What artifact retention and redaction policy should apply to pane text
   captures and screenshot fallback evidence captured for `cc-bridge_self`
   self-supervision?
10. Should the internal schedule consumer runner ever become a public command,
    or should `cc-bridge maintenance status|tick|schedule` remain the only documented
    user-facing heartbeat surface?
11. What maximum string bounds and stale-orphan race policy should bounded
    `provider_runtime` snapshots enforce after job terminalization or snapshot
    cleanup lag?

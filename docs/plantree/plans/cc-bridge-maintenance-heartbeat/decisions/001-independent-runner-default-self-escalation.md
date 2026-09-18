# Independent Runner With Default Self Escalation

Date: 2026-06-10

## Context

The maintenance heartbeat must diagnose CC_BRIDGE agent health periodically without
becoming another daemon authority and without relying on a provider-side loop.
Programmatic checks can identify many runtime and communication failures, but
semantic judgment is still needed for ambiguous task execution, weak replies,
stuck callback chains, or degraded diagnostics.

## Decision

The heartbeat is a generic CC_BRIDGE feature implemented as a relatively independent
runner, exposed through a project-aware command family such as
`cc-bridge maintenance ...`.

The runner reads cc-bridge-daemon diagnostics and CC_BRIDGE communication state, performs bounded
programmatic agent-health checks, and exits when the project is healthy and
idle. If it finds risk, diagnoses an unhealthy state, or cannot decide with
enough confidence, it sends a bounded diagnostic package to the configured
semantic assessor.

The default assessor is the project-local `cc-bridge_self` agent when available, but
the target must remain configurable and must not be hard-coded into the
heartbeat engine.

In v1, the assessor may return report-only advice, user-escalation requests,
and validated schedule recommendations. Mutating repair actions such as
`clear`, `restart`, `repair`, `kill`, force cleanup, or restart-all are
deferred until an explicit autonomous repair policy exists.

## Consequences

- Heartbeat scheduling, locking, state writes, and tick execution remain CC_BRIDGE
  responsibilities.
- `cc-bridge_self` supplies semantic supervision, but it is not the heartbeat
  process and does not become keeper, cc-bridge-daemon, lifecycle, or runtime authority.
- The runner must use an independent heartbeat lock namespace and must not
  share keeper or cc-bridge-daemon lifecycle locks.
- The diagnostics snapshot should reuse existing CC_BRIDGE diagnostics and
  communication surfaces instead of inventing a parallel collection path.
- Healthy idle projects do not wake a provider agent.
- Risk, unknown, and unhealthy states wake the assessor unless the assessor is
  busy, missing, degraded, or policy-disabled.

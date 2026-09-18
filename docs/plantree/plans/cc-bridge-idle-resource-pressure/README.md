# CC_BRIDGE Idle Resource Pressure Plan

Date: 2026-06-23

## Purpose

Design a low-risk path to reduce CC_BRIDGE's idle SSD writes, memory pressure, and
background CPU when many provider-backed agents stay mounted but are not
actively doing work.

## Problem Statement

The current runtime model keeps project daemons, provider bridges, tmux panes,
and provider CLI processes alive for fast interaction. That works for small
projects, but high-intensity multi-project usage causes idle resource pressure:

- `cc-bridge-daemon/main.py` and `keeper_main.py` continue to write heartbeat and runtime
  state while the project is idle.
- Each mounted provider can retain a full CLI process, bridge process, terminal
  pane, provider home, SQLite state, and session files.
- Runtime records such as `lease.json`, `keeper.json`, `lifecycle.json`,
  `runtime.json`, and `helper.json` can be rewritten even when the user sees no
  meaningful state change.
- Provider-local durable state, especially Codex session JSONL and SQLite WALs,
  can grow independently from CC_BRIDGE's own runtime metadata.
- A false-success pane recovery loop can turn a provider startup failure into
  continuous crash-log and atomic-state writes unless retry, stability, and
  circuit-breaker boundaries are explicit.

This plan focuses on idle behavior. Active task throughput and response
latency remain important, but idle safety should not require users to kill every
project manually.

## Goals

- Reduce repeated idle writes to `.cc-bridge/cc-bridge-daemon/*` and `.cc-bridge/agents/*/*.json`.
- Reduce memory and CPU from providers that are mounted but unused.
- Preserve fast wake-up for the first new ask or UI action after an idle period.
- Preserve ask correctness and callback stability: submit, queueing, callback
  continuation, reply delivery, cancellation, and resubmit semantics must remain
  authoritative while any idle policy is active.
- Keep durable state boundaries explicit: recoverable runtime residue should be
  movable to tmpfs or removable; user/session/auth state must remain safe.
- Provide observable counters so regressions are visible.

## Non-Goals

- Replacing provider CLIs or changing their internal storage format.
- Removing persistent provider sessions by default.
- Full Python control-plane rewrite.
- Making all runtime state in-memory only.
- Trading ask correctness for lower idle resource usage.

## Reading Path

1. [roadmap.md](roadmap.md)
2. [topics/idle-resource-pressure-solution.md](topics/idle-resource-pressure-solution.md)
3. [topics/worker-execution-goal.md](topics/worker-execution-goal.md)
4. [topics/callback-ledger-read-amplification.md](topics/callback-ledger-read-amplification.md)
5. [topics/pr234-runtime-accelerator-review.md](topics/pr234-runtime-accelerator-review.md)
6. Related baseline:
   [../../baseline/storage-and-state.md](../../baseline/storage-and-state.md),
   [../../baseline/runtime-flows.md](../../baseline/runtime-flows.md)
6. Related performance plan:
   [../cc-bridge-runtime-performance/README.md](../cc-bridge-runtime-performance/README.md)

## Current Evidence

Local diagnosis on 2026-06-23 found:

- Codex `logs_2.sqlite` write pressure was real. The `v7.6.14` trigger-only
  mitigation was insufficient because it still kept the database on durable
  storage and only filtered selected levels; the source hardening now redirects
  the managed DB to a temp path and blocks diagnostic inserts by default.
- A 10-second `/proc/<pid>/io` sample showed several project `cc-bridge-daemon/main.py`
  processes writing hundreds of KB to a few MB per 10 seconds while idle.
- `state_5.sqlite*` was not a release blocker in the local release sample:
  small aggregate size and no 15-second idle mtime/size movement were observed.
- Recently touched files during idle were dominated by:
  - `.cc-bridge/cc-bridge-daemon/lease.json`
  - `.cc-bridge/cc-bridge-daemon/keeper.json`
  - `.cc-bridge/cc-bridge-daemon/lifecycle.json`
  - `.cc-bridge/agents/<agent>/runtime.json`
  - `.cc-bridge/agents/<agent>/helper.json`
  - provider-side `state_5.sqlite-wal`, `sessions/*.jsonl`,
    `activity.json`, and `models_cache.json`
- Large disk usage came from per-agent `provider-state/codex/home` and shared
  plugin bundles; not all of that is continuous write pressure.
- On 2026-07-30, a separate active failure loop was measured at about 71.9 GB
  of physical writes over 70.6 hours with 19,602 pane crash logs. Recovery
  stability, backoff/circuit breaking, and online crash-log retention are now
  implemented in the working tree; this is distinct from ordinary idle
  heartbeat pressure.
- On 2026-08-01, a long-lived project exposed callback-ledger read
  amplification: a 18.8 MB ledger made one idle dispatcher tick take about
  26.8 seconds and kept `cc-bridge-daemon` near 91% CPU. The working-tree fix keeps JSONL
  as authority, adds a file-signature-invalidated latest-edge memory view, and
  limits recovery scans to actionable callback states.

## Status

In progress. Corrected Codex diagnostic SQLite hardening and pane-crash storm
containment are implemented in the working tree; broader idle CPU, memory,
heartbeat, and provider suspend work remains in planning.

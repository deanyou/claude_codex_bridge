# Inter-Agent Communication Reliability Roadmap

Date: 2026-06-14

Last updated: 2026-07-07

## Status Summary

- Current status: first small hard-gate source slice and no-progress Codex
  delivery timeout slice implemented in the working tree; release promotion
  still requires normal review/commit/release gates.
- Last analysis: PR226 improves low-probability Linux/macOS/WSL transport
  races, but it should not be treated as a completed stability boundary without
  follow-up guards.
- Last verified: targeted PR226-adjacent tests passed in a clean
  `origin/main` worktree:
  `python -m pytest -q test/test_bridge_fifo_persistent_reader.py test/test_fifo_delivery.py test/test_transport_parity.py test/test_cancel_flags.py`
  -> `26 passed`.
- Current review: PR238 is useful empty-reply diagnostics, but not a root
  communication-stability fix. PR239 contains useful observability pieces, but
  its Codex 900 second degraded fallback is a policy change rather than
  accepted-turn ownership, and the branch is too broad to merge as-is.
- Root direction: prioritize accepted-turn ownership, provider epochs, compact
  CC_BRIDGE-owned evidence, and chain reply lineage before adopting degraded timeout
  behavior as a default.
- Current focus: ask-after-reply temporal stability under clear and long
  provider session files.
- Minimal plan: start with tests, provider-acceptance fields, clear barriers,
  compact evidence on the existing polling path, and recovery-only fallback.
- Clear analysis: current `cc-bridge clear` is pane input, not an accepted-turn or
  provider-epoch boundary. Codex and Claude both need the same monotonic
  post-clear evidence boundary before further timeout fallback work.
- `cc-bridge_clear` direction: keep provider session files as raw evidence, but let
  CC_BRIDGE own continuity through per-agent epochs and a short post-clear probe.
- Temporal stability continuation: implement in small slices: tests/probes,
  provider acceptance fields, `cc-bridge_clear` barrier, compact polling evidence,
  terminal predicates, reply lineage, and recovery-only fallback.
- Narrowed first slice: first try a small hard-gate implementation using the
  existing `pending_anchor`, `anchor_seen`, session-rotate, and empty-reply
  detector paths before adding a tailer or larger evidence subsystem.
- Coworker review `job_7311c8f04328` passed the small hard-gate proposal with
  conditions: first implement provider-acceptance, fallback-quarantine, and
  session-rotate gates; defer clear barrier until dispatcher integration is
  selected.
- Low-latency direction: first remove broad fallback scans from the normal path
  and add compact evidence; persistent tailer remains benchmark-backed optional
  optimization.
- Coworker review `job_b5689ffafbf1` raised concerns that tailer-first is
  overdesigned for the first slice; this plan adopts the simpler polling-first
  implementation order.
- First source slice landed in the working tree: Codex active completions now
  require accepted request-anchor evidence or explicit `no_wrap`; broad anchor
  fallback is quarantined as diagnostic evidence; session rotate without a
  fresh anchor cannot complete as success.
- Last verified for the first source slice:
  `PYTHONPATH=lib python -m pytest -q test/test_v2_cc-bridge-daemon_dispatcher.py`
  -> `39 passed`;
  `PYTHONPATH=lib python -m pytest -q test/test_v2_execution_service.py`
  -> `63 passed`;
  `PYTHONPATH=lib python -m compileall -q ...` -> passed;
  `git diff --check -- ...` -> passed.
- Added strict temporal verification with fake-clock duration: fallback
  quarantine can persist for 30 minutes without completing the job, and a later
  official Codex session binding switch still produces `SESSION_ROTATE`,
  fresh `ANCHOR_SEEN`, and accepted new-session reply evidence.
- Second timing slice landed in the working tree: Codex prompt delivery now
  tracks `delivery_last_progress_at`; slow official session file movement keeps
  the ask pending, while a missing official session/log past the no-progress
  window returns `incomplete/codex_session_file_missing` with
  `no_reply_reason=completion_detection_gap`.
- Last verified for the no-progress slice:
  `PYTHONPATH=lib python -m pytest -q test/test_v2_execution_service.py`
  -> `65 passed`;
  `PYTHONPATH=lib python -m pytest -q test/test_stability_regressions.py`
  -> `16 passed`;
  `PYTHONPATH=lib python -m pytest -q test/test_provider_execution_service_runtime.py`
  -> `11 passed`;
  `PYTHONPATH=lib python -m pytest -q test/test_codex_runtime_accelerator_polling.py`
  -> `5 passed`;
  `PYTHONPATH=lib python -m compileall -q ...` -> passed;
  `git diff --check` -> passed.

## Done

- Recorded that the current user decision is plan-tree only: do not land new
  source changes or promote follow-up work into main.
- Classified PR226 benefits for Linux, macOS, and WSL:
  - reduces FIFO no-reader windows with a persistent reader
  - bounds sender waits when the bridge is unavailable
  - adds read-level ACK evidence
  - uses spool files for large FIFO payloads
  - adds communication-path logs for previously silent failures
- Recorded current risk analysis in
  [topics/pr226-risk-and-adoption-note.md](topics/pr226-risk-and-adoption-note.md).
- Recorded the current ask/clear/session ownership boundary and PR238/PR239
  review in
  [topics/accepted-turn-binding-and-pr238-239-review.md](topics/accepted-turn-binding-and-pr238-239-review.md).
- Expanded the root-fix architecture in
  [topics/root-stability-architecture.md](topics/root-stability-architecture.md).
- Added the focused temporal-stability model in
  [topics/ask-reply-temporal-stability.md](topics/ask-reply-temporal-stability.md).
- Added the minimal non-overdesigned landing plan in
  [topics/minimal-temporal-stability-plan.md](topics/minimal-temporal-stability-plan.md).
- Added source-backed Codex/Claude post-clear behavior analysis in
  [topics/clear-after-logic-codex-claude.md](topics/clear-after-logic-codex-claude.md).
- Added provider-neutral `cc-bridge_clear` epoch/probe design in
  [topics/cc-bridge-clear-epoch-probe-design.md](topics/cc-bridge-clear-epoch-probe-design.md).
- Added temporal-stability implementation slice design in
  [topics/temporal-stability-slice-design.md](topics/temporal-stability-slice-design.md).
- Added narrowed small hard-gate first-slice proposal in
  [topics/small-hard-gate-first-slice-plan.md](topics/small-hard-gate-first-slice-plan.md).
- Added persistent tailer low-latency design in
  [topics/persistent-tailer-low-latency-design.md](topics/persistent-tailer-low-latency-design.md).
- Recorded coworker review and accepted simplification in
  [topics/coworker-review-20260706-temporal-stability.md](topics/coworker-review-20260706-temporal-stability.md).
- Recorded coworker review for the narrowed hard-gate slice in
  [topics/coworker-review-20260706-small-hard-gate.md](topics/coworker-review-20260706-small-hard-gate.md).
- Implemented the reviewed first-batch hard gates from
  [topics/small-hard-gate-first-slice-plan.md](topics/small-hard-gate-first-slice-plan.md):
  provider acceptance, fallback quarantine, session rotate gating, and
  dispatcher-side normalization before `dispatcher.complete(...)`.
- Added the no-progress delivery timeout and degradation design in
  [topics/no-progress-delivery-timeout-and-degradation-plan.md](topics/no-progress-delivery-timeout-and-degradation-plan.md).
- Implemented the first no-progress delivery timeout source slice from
  [topics/no-progress-delivery-timeout-and-degradation-plan.md](topics/no-progress-delivery-timeout-and-degradation-plan.md):
  compact progress marker, `delivery_last_progress_at`, missing-session
  `incomplete` diagnostics, and no-progress snapshot deadline.

## Next

1. Decide whether CC_BRIDGE wants PR226-style transport hardening as a release goal
   or only as a diagnostic/stress-mode hardening track.
2. If promoted later, add focused tests for ACK semantics, marker uniqueness,
   spool path constraints, and cancel prompt injection before source changes.
3. Keep Linux/macOS/WSL as the only supported target set for this plan slice.
4. For ask/clear/session reliability, prioritize accepted-turn binding,
   provider epoch evidence, and compact CC_BRIDGE-owned event indexing before adding
   more timeout fallback behavior.
5. Resolve the first two root design questions: clear invalidation semantics
   and where compact provider evidence should live.
6. Promote the temporal state machine into an implementation-ready Slice 0 test
   list before touching source behavior.
7. Use [topics/minimal-temporal-stability-plan.md](topics/minimal-temporal-stability-plan.md)
   as the readiness gate for the first implementation slice.
8. Treat [topics/clear-after-logic-codex-claude.md](topics/clear-after-logic-codex-claude.md)
   as the provider-specific source map for clear barrier implementation.
9. Treat [topics/cc-bridge-clear-epoch-probe-design.md](topics/cc-bridge-clear-epoch-probe-design.md)
   as the workflow contract for self-clear, post-clear probe, and provider
   session continuity.
10. Use [topics/temporal-stability-slice-design.md](topics/temporal-stability-slice-design.md)
    to prepare the first implementation-ready test and field slice.
11. Add the second-batch clear barrier through a dispatcher-owned or
    dispatcher-consumed signal; do not make `project_clear.py` own job
    completion directly.
12. Decide whether to implement the deferred diagnostic-only pieces from
    [topics/no-progress-delivery-timeout-and-degradation-plan.md](topics/no-progress-delivery-timeout-and-degradation-plan.md):
    PR238 empty-reply sub-classification and narrow PR239 high-confidence
    provider error mapping.
13. Add reply lineage hardening for B -> C -> A chain completion paths.
14. Use [topics/persistent-tailer-low-latency-design.md](topics/persistent-tailer-low-latency-design.md)
    as an optional optimization candidate pending benchmark evidence.
15. Use [topics/coworker-review-20260706-temporal-stability.md](topics/coworker-review-20260706-temporal-stability.md)
    as the first-slice complexity gate.

## Deferred

- Changing shipped ACK wording or sender result semantics.
- Changing marker generation.
- Enforcing spool path restrictions.
- Changing cancel prompt injection behavior.
- Merging PR239 wholesale as a stability fix.
- Making Codex bounded no-terminal fallback the default without a separate
  policy decision and accepted-turn/epoch tests.
- Adding persistent tailer or a large global event-store abstraction before the
  compact polling evidence contract and recovery-only fallback are proven.
- Native Windows transport support.

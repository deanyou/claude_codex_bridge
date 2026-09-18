# Mother RolePack Design Review

Date: 2026-06-27

## Source

`mother` completed the RolePack design request for CC_BRIDGE agentic workflow roles.

- Job: `job_91c8cc2e374d`
- Reply: `rep_5a3c21688c97`
- Artifact:
  `/home/bfly/yunwei/cc-bridge_source/.cc-bridge/cc-bridge-daemon/artifacts/text/completion-reply/job_91c8cc2e374d-art_87dc4434f7c64b8b.txt`
- SHA256:
  `dce197536f7e207afc42b1aca70b5625753ed338874df169d5b94431a3aca955`

## Review Result

Accepted as the first Agent Roles spec handoff baseline, with one important
boundary: CC_BRIDGE command names, loop runner behavior, task locks, leases, tmux
layout, ask/callback mechanics, and runtime directory details must remain in a
CC_BRIDGE adapter layer, not in host-neutral core RolePack identity.

The report is aligned with the current workflow principle:

```text
scripts own hard authority
roles own semantic artifacts and recommendations
scripts commit or reject role outputs
```

## Accepted Priority Order

P0 complete RolePack design:

1. `agentroles.cc-bridge_planner`
2. `agentroles.cc-bridge_plan_reviewer`
3. `agentroles.cc-bridge_clarification_broker`
4. `agentroles.cc-bridge_orchestrator`
5. `agentroles.cc-bridge_round_checker`

P1 simplified RolePack design:

1. `agentroles.cc-bridge_frontdesk`
2. `agentroles.cc-bridge_worker`
3. `agentroles.cc-bridge_checker`

P2 boundary-only design:

1. `agentroles.cc-bridge_risk_reviewer`
2. `agentroles.cc-bridge_inner_monitor`
3. `agentroles.cc-bridge_recovery`
4. `agentroles.cc-bridge_plan_steward`
5. `agentroles.cc-bridge_domain_researcher`
6. `agentroles.cc-bridge_spec_checker`

## Accepted Common Rule

Every CC_BRIDGE workflow RolePack must carry a common authority rule:

```text
You may author semantic artifacts and recommend transitions.
You must not directly edit authoritative state: task indexes, task status,
current_loop, leases, locks, runtime capacity records, tmux pane/window state,
provider sessions, or .cc-bridge/runtime/loops authority files.

Use CC_BRIDGE-owned commands or host-provided skill wrappers such as cc-bridge plan,
cc-bridge loop, and cc-bridge question for authoritative writes. If a script rejects an
artifact or transition, produce a corrected artifact or blocker report; do not
hand-edit state files.
```

## Role-Specific Notes

- `cc-bridge_planner`: should output task packet artifacts plus compact
  `readiness.json`; it must not talk directly to the user or mark task status.
- `cc-bridge_plan_reviewer`: should reject vague acceptance, weak verification, and
  hidden fallback; it must not become a second full planner by default.
- `cc-bridge_clarification_broker`: should filter, default, defer, or normalize
  questions; it must not directly ask the user or start execution.
- `cc-bridge_orchestrator`: existing draft is directionally correct but needs
  stronger runner-router compatibility and stronger negative tests around
  runtime authority, fanout, and partial-to-done conversion.
- `cc-bridge_round_checker`: must emit a standalone machine line:
  `round result: pass|rework_node|partial|replan_required|global_blocker`.
  Without that line, loop runner must not infer success from provider
  completion alone.
- `cc-bridge_worker` and `cc-bridge_checker`: can start as simplified reference roles
  because the worker/checker pattern is already widely understandable; the
  important boundary is no scope shrinkage and no hidden fallback acceptance.

## Host-Neutral Versus CC_BRIDGE Adapter Split

Host-neutral Agent Roles spec should contain:

- role identity and mission;
- authority and non-authority;
- generic skills and workflow steps;
- artifact schemas and templates;
- negative instructions;
- conformance prompts and smoke tests.

CC_BRIDGE adapter-specific material should contain:

- exact `cc-bridge plan`, `cc-bridge loop`, and `cc-bridge question` command names;
- `loop runner --once` activation semantics;
- task lock, lease, `current_loop`, and runtime directory behavior;
- CC_BRIDGE `ask`, callback, and artifact-reply mechanics;
- capacity ensure/release and hot-load behavior;
- tmux, pane, provider-session, and rich/sidebar projection details.

## Landing Order

1. Add the common authority rule and shared artifact templates to the external
   Agent Roles spec baseline.
2. Materialize `cc-bridge_planner` and `cc-bridge_plan_reviewer`.
3. Materialize `cc-bridge_round_checker`.
4. Tighten the existing `cc-bridge_orchestrator` draft.
5. Add `cc-bridge_clarification_broker`.
6. Add simplified `frontdesk`, `worker`, and `checker`.
7. Add conformance and negative smoke tests.
8. Defer monitor, recovery, risk, steward, researcher, and spec-checker roles
   until the V1 runner/router loop is stable.

## Follow-Up

The next planning or implementation step should be a concrete Agent Roles spec
handoff package for the P0 roles, not another broad role taxonomy.

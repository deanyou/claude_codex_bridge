# 017 Flat Roles And Role Collections

Date: 2026-07-02
Status: Accepted for planning

## Decision

Use flat installable Roles plus Role Collections for Agent Roles source. Do not
add a source-level hierarchy of parent classes, child roles, or reusable group
templates.

`role.toml` describes exactly one Role. Grouped installation, update, removal,
profiles, and catalog hierarchy belong to `collections/<name>/collection.toml`
in the Agent Roles spec.

Recommended Collections for the CC_BRIDGE workflow:

- `agentroles.collections.planning_group`
  - required: `agentroles.cc-bridge_planner`
  - optional: planning-adjacent CC_BRIDGE roles such as a future plan reviewer or
    clarification broker; `agentroles.cc-bridge_task_detailer` is deliberately not
    required by this collection.
- `agentroles.collections.execution_workgroup`
  - required: `agentroles.coder`, `agentroles.code_reviewer`
  - optional: document, research, test, and source-reviewer Roles
- `agentroles.collections.agentic_loop_core`
  - required: `agentroles.cc-bridge_frontdesk`, `agentroles.cc-bridge_planner`,
    `agentroles.cc-bridge_orchestrator`, `agentroles.coder`,
    `agentroles.code_reviewer`, and `agentroles.cc-bridge_round_reviewer`
  - optional: `agentroles.cc-bridge_task_detailer` and future CC_BRIDGE review, risk,
    monitor, and recovery Roles

Collections do not inherit, merge, grant permissions, or automatically mount
all members. They are catalog and install-management artifacts.

## CC_BRIDGE Runtime Boundary

CC_BRIDGE may still use runtime topology groups such as `planning_group`,
`execution_group`, or `workgroup-node1`. These groups are Project Binding or
runtime-state records, not Agent Roles source objects.

CC_BRIDGE runtime groups should not be selected, loaded, or constrained by
Collection id. A runtime group must explicitly declare selected members,
roles, profiles, topology edges, artifact handoffs, lifecycle, release policy,
and Project Binding authority. Collection membership alone must not mount
agents, grant runtime permissions, or become a runtime selection key.

## Preserved From Decision 016

Decision 016 remains authoritative for `macro-adjustment-request`:
`agentroles.cc-bridge_task_detailer` must not directly update roadmap, status,
decisions, or macro task authority. When detail work proves that macro
assumptions need to change, it emits a `macro-adjustment-request` artifact for
`agentroles.cc-bridge_planner` review through script-owned plan surfaces.

## Consequences

- Agent Roles source stays simple: one Role per RolePack, one Collection per
  grouped install/profile bundle.
- CC_BRIDGE runtime remains free to model groups for layout, ask edges, release
  gates, and topology reconciliation without pushing those runtime mechanics
  into Agent Roles source.
- Host Adapters may use Collections for display, install profiles, and
  installation management, but runtime mounting remains an explicit Project
  Binding or runtime-topology decision.

## Related

- [016-agent-groups-and-macro-adjustment-request.md](016-agent-groups-and-macro-adjustment-request.md)
- [../topics/role-class-naming-and-hierarchy.md](../topics/role-class-naming-and-hierarchy.md)
- [../topics/runtime-workflow-graph-and-reconciler.md](../topics/runtime-workflow-graph-and-reconciler.md)

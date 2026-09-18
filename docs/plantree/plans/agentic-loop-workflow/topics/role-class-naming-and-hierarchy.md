# CC_BRIDGE Role Naming And Collections

Date: 2026-06-30
Updated: 2026-07-02

## Purpose

This file originally explored parent/child role hierarchy and then a fully
host-neutral role id direction. Both directions are superseded for the current
CC_BRIDGE workflow.

Current rule:

```text
CC_BRIDGE-specific workflow role ids keep agentroles.cc-bridge_*
generic execution roles stay portable where useful
collections group install/update/list only
runtime topology selects concrete agents explicitly
```

## Source Model

| Layer | Example | Meaning |
| :--- | :--- | :--- |
| CC_BRIDGE workflow Role | `agentroles.cc-bridge_orchestrator` | One CC_BRIDGE-specific specialist Role with explicit workflow boundary. |
| Generic execution Role | `agentroles.coder` | Portable worker Role that can be reused outside CC_BRIDGE. |
| Role Collection | `agentroles.collections.agentic_loop_core` | Catalog/install layer with required and optional Role members plus profiles. |
| CC_BRIDGE runtime group | `workgroup-node1` | Project Binding or runtime topology record that selects concrete mounted agents, edges, gates, placement, and release policy. |
| Runtime agent | `wf-coder-1` | CC_BRIDGE project instance selected by config, Project Binding, capacity profile, or committed topology. |

Collections are not parent Roles. They do not merge member memory, skills,
templates, tools, adapters, permissions, or runtime state. Installing a
Collection installs or updates member Roles; mounting remains an explicit CC_BRIDGE
topology or Project Binding decision.

## Current Role Ids

V1 CC_BRIDGE workflow Roles:

- `agentroles.cc-bridge_frontdesk`
- `agentroles.cc-bridge_planner`
- `agentroles.cc-bridge_orchestrator`
- `agentroles.cc-bridge_task_detailer`
- `agentroles.cc-bridge_round_reviewer`

Generic execution Roles:

- `agentroles.coder`
- `agentroles.code_reviewer`

Historical or rejected names:

- `agentroles.planner_task`: historical/deprecated alias material; do not use
  for new CC_BRIDGE workflow topology.
- `agentroles.plan_steward`: historical term for planner stewardship work mode
  or deterministic `cc-bridge plan` authority, not a required Role.
- `agentroles.cc-bridge_worker`: replaced by generic execution Roles such as
  `agentroles.coder`.
- `agentroles.cc-bridge_checker`: replaced by `agentroles.code_reviewer`.
- Bare CC_BRIDGE workflow aliases such as `agentroles.planner`,
  `agentroles.orchestrator`, `agentroles.task_detailer`, and
  `agentroles.round_reviewer` are not the current CC_BRIDGE workflow ids.

## Recommended Collections

### `agentroles.collections.planning_group`

Purpose: install the CC_BRIDGE macro planner and optional planning-adjacent
capabilities. It does not include task detailer; refinement is an
orchestrator-demanded capability rather than a planning-group member.

Required members:

- `agentroles.cc-bridge_planner`

Optional members:

- future CC_BRIDGE plan-review or clarification roles, if the V1 loop later proves
  they are needed.

### `agentroles.collections.execution_workgroup`

Purpose: install the default bounded implementation and independent review
Roles used by one CC_BRIDGE execution group.

Required members:

- `agentroles.coder`
- `agentroles.code_reviewer`

Optional members:

- future document, research, test, and source-review Roles.

### `agentroles.collections.agentic_loop_core`

Purpose: install the core Role set needed to run the CC_BRIDGE agentic loop design.

Required members:

- `agentroles.cc-bridge_frontdesk`
- `agentroles.cc-bridge_planner`
- `agentroles.cc-bridge_orchestrator`
- `agentroles.coder`
- `agentroles.code_reviewer`
- `agentroles.cc-bridge_round_reviewer`

Optional members:

- `agentroles.cc-bridge_task_detailer`
- future CC_BRIDGE review, risk, monitor, and recovery Roles.

## Runtime Use

CC_BRIDGE config and topology should reference concrete role profiles and runtime
instance names:

```toml
[loop.role_profiles.cc-bridge_orchestrator]
role = "agentroles.cc-bridge_orchestrator"
provider = "codex"
thinking = "high"
max_instances = 1

[loop.role_profiles.coder]
role = "agentroles.coder"
provider = "codex"
thinking = "high"
max_instances = 4

[loop.role_profiles.code_reviewer]
role = "agentroles.code_reviewer"
provider = "codex"
thinking = "medium"
max_instances = 4
```

Runtime topology may group instances for layout, dispatch, and release:

```json
{
  "id": "workgroup-node1",
  "kind": "execution_group",
  "members": [
    {"agent": "wf-coder-1", "role": "agentroles.coder", "profile": "coder"},
    {"agent": "wf-code-reviewer-1", "role": "agentroles.code_reviewer", "profile": "code_reviewer"}
  ]
}
```

Runtime topology is independently managed by CC_BRIDGE Project Binding and the
orchestrator/topology reconciler. It does not need a Collection id to load a
group; the orchestrator must explicitly constrain selected roles, members,
edges, gates, lifecycle, and release policy.

## Agent Roles Spec Requirements

The external Agent Roles spec should support:

- flat Role ids that are independently installable;
- Role Collections with required and optional members;
- named Collection profiles for install/update operations;
- list output that groups installed or available Roles under Collections;
- Host Adapter notes for how Collections seed display, team suggestions, or
  Project Binding defaults;
- deterministic behavior when a Collection member is missing, optional,
  already installed directly, or shared with another Collection;
- no inheritance, memory merge, permission grants, or automatic mount behavior
  from Collection membership.

# Provider Activity Is Execution-State Authority

Date: 2026-05-27

## Context

CC_BRIDGE asks are delivered to pane-backed providers by simulating normal user input.
From the provider's perspective, a CC_BRIDGE-managed task and a manual pane prompt are
both provider turns.

The old sidebar activity logic leaned on CC_BRIDGE job state and pane text. That makes
manual pane work look idle and can keep jobs visually active even when the
provider already failed or returned to the prompt.

## Decision

Provider-native activity is the primary execution-state authority for agent-row
status.

`cc-bridge-daemon` lifecycle facts remain the ownership guard:

- configured agent identity
- provider family
- current pane id
- runtime generation
- stopped/recovering/failed runtime state

CC_BRIDGE job, message, attempt, reply, and Comms records are metadata and workflow
state. They may enrich diagnostics and retry behavior, but they are not the
primary source for whether an agent is currently active, waiting, idle, or
failed.

The Rust sidebar remains read-only. It renders `project_view`; it does not
compute or write provider activity.

## Consequences

- Manual pane work and `cc-bridge ask` turns share one state path.
- `project_view` must validate provider activity artifacts against current
  `cc-bridge-daemon` ownership before trusting them.
- Dispatcher/retry code can later consume the same provider activity resolver
  when deciding whether a job is genuinely stale.
- Existing Comms state should not block provider-activity adoption; Comms is a
  communication workflow view, not execution-state authority.

# Sidebar View Config Is UI-Only

Date: 2026-05-27

## Context

The sidebar already has topology-facing configuration: mode, width, and bottom
height. Those settings affect namespace materialization or topology identity.

The proposed Tips panel and Comms display limit are different. They change
only how the existing sidebar pane renders information.

## Decision

Sidebar Tips text, Comms visible limit, compact rendering, and panel height
preferences should be modeled as UI-only sidebar view configuration. They
should be normalized by CC_BRIDGE and delivered to `cc-bridge-agent-sidebar` through
`project_view`.

They should not become authority for managed windows, agents, pane ownership,
provider runtime, message/job state, or namespace topology.

## Consequences

- Editing Tips text can hot-reload through the sidebar refresh loop.
- Harmless view changes do not require namespace recreation.
- The Rust sidebar still consumes `cc-bridge-daemon` state instead of reading
  `.cc-bridge/cc-bridge.config` directly.
- The implementation needs a separate config identity/topology boundary for
  UI-only fields.

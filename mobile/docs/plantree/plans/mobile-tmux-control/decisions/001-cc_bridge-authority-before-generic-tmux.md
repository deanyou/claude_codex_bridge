# Decision 001: CC_BRIDGE Authority Before Generic Tmux

Date: 2026-06-17
Status: Proposed

## Decision

Plan CC_BRIDGE mobile control as a CC_BRIDGE-aware project/agent control plane with
terminal views, not as a generic tmux remote client that happens to know about
CC_BRIDGE.

## Rationale

CC_BRIDGE's valuable state is not only tmux state. It includes `.cc-bridge` anchors,
`cc-bridge-daemon` lifecycle, namespace epochs, configured agents/windows, Comms, provider
runtime records, queue/callback state, pane recovery, and project-specific
authority.

A generic tmux client can render panes and send keys, but it cannot safely
decide which pane is an agent, whether a pane id is stale, whether an action
belongs to the current namespace epoch, or whether a split/kill/reflow operation
violates the project config.

## Consequences

- Mobile project identity must come from CC_BRIDGE project anchors and `cc-bridge-daemon`, not
  tmux session enumeration.
- Mobile focus actions should use CC_BRIDGE endpoints.
- Mobile pane snapshots and interactive terminal streams should be mediated by
  CC_BRIDGE endpoints.
- Raw tmux session/window/pane mutation should not be exposed as default mobile
  behavior.
- Existing tmux/mobile projects remain valuable references, but their command
  layers require CC_BRIDGE-specific adaptation.

## Validation Path

The decision is validated if an MVP can:

1. list multiple CC_BRIDGE projects accurately;
2. show multi-agent project state from `project_view`;
3. focus an agent/window through `cc-bridge-daemon`;
4. submit an ask/composer message through CC_BRIDGE;
5. show pane snapshots without relying on pane id as durable identity;
6. avoid unexpected tmux layout or lifecycle changes from mobile use.

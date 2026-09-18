# tmux-mobile Fork Adaptation

Date: 2026-06-18
Status: Superseded by Decision 005 for primary client base; retained as a
server-side gateway and tmux behavior reference.

## Purpose

Define how tmux-mobile can inform a CC_BRIDGE phone/iPad remote-control product.
Earlier analysis treated tmux-mobile as the preferred first implementation
base. Decision 005 moves the primary app base to native Flutter, while keeping
tmux-mobile useful for server-side WebSocket/PTY/tmux gateway design.

The goal is not to build an independent mobile agent app. The goal is to remote
control server-side CC_BRIDGE tmux panes with a mobile-optimized terminal, while CC_BRIDGE
metadata improves project selection, pane targeting, safety, Comms, and
Markdown reading.

## Why tmux-mobile Still Matters

tmux-mobile already matches the clarified product center:

- server-hosted web terminal;
- phone browser as a thin client;
- xterm.js-style terminal interaction;
- tmux socket/path configuration;
- session/window/pane listing;
- terminal attach, input, resize, and reconnect mechanics;
- common deployment path through LAN or tunnel.

That is still close to "remote into the server CC_BRIDGE tmux pane", but it is not
the best primary base for native Android, iOS, and iPadOS apps.

## Product Boundary

The adapted product should be "tmux-mobile for CC_BRIDGE", not "CC_BRIDGE rewritten as a
mobile app".

Keep:

- server-side process owns terminal access;
- mobile client renders and controls server tmux;
- CC_BRIDGE continues running on the server;
- CC_BRIDGE project tmux sessions remain the primary workspace;
- mobile/iPad UX optimizes remote terminal control.

Add:

- CC_BRIDGE project discovery;
- CC_BRIDGE project socket/session binding;
- CC_BRIDGE agent/window labels;
- CC_BRIDGE focus actions;
- CC_BRIDGE stale namespace/pane validation;
- CC_BRIDGE Comms and callback indicators;
- Markdown reader for CC_BRIDGE message/artifact content.

Avoid:

- arbitrary host tmux browsing by default;
- standalone mobile agent execution;
- mobile-created CC_BRIDGE projects;
- raw destructive tmux operations against CC_BRIDGE sessions;
- treating pane ids as stable deep-link identity.

## Adaptation Map

### Keep From tmux-mobile

- web terminal UI foundation;
- terminal WebSocket path;
- tmux attach/control plumbing;
- socket-name/socket-path configuration ideas;
- client reconnect behavior;
- mobile keyboard and terminal controls;
- deployment model suitable for LAN/tailnet/tunnel.

Source review note:

- tmux-mobile's tmux CLI executor supports `TMUX_MOBILE_SOCKET_NAME` and
  `TMUX_MOBILE_SOCKET_PATH`.
- Its PTY attach path currently does not pass that socket name/path into
  `tmux attach-session`.
- CC_BRIDGE adaptation must make terminal attach socket-aware before using project
  tmux sockets.

### Replace Or Wrap

- session list becomes CC_BRIDGE project list;
- raw tmux socket selection becomes CC_BRIDGE project socket selection;
- window/pane list is annotated and filtered by CC_BRIDGE project/agent metadata;
- select-window/select-pane should call CC_BRIDGE focus endpoints when targeting
  CC_BRIDGE-managed windows and agents;
- paste should use CC_BRIDGE/tmux-safe buffer strategy where possible;
- destructive pane/window/session operations should be removed from the normal
  UI or routed through explicit CC_BRIDGE admin endpoints.

### Add

- `cc-bridge mobile serve` entrypoint or equivalent wrapper;
- project registry from `.cc-bridge` anchors and `cc-bridge-daemon` lifecycle records;
- ProjectView side panel;
- agent quick switcher;
- Comms/callback attention badges;
- Markdown content drawer;
- QR/device pairing;
- permission scopes for view, terminal input, content, focus, and admin.

## CC_BRIDGE-Specific Runtime Rules

- Connect to the tmux socket path reported by CC_BRIDGE namespace state.
- Treat namespace epoch as a stale-view guard.
- Resolve panes by CC_BRIDGE user options where possible:
  `@cc-bridge_project_id`, `@cc-bridge_role`, `@cc-bridge_slot`, `@cc-bridge_window`,
  `@cc-bridge_managed_by`.
- Use pane id only as current evidence.
- On pane recovery or project restart, refresh CC_BRIDGE metadata before accepting
  further input.
- Detaching a mobile terminal must not stop `cc-bridge-daemon`, tmux session, or provider
  panes.

## UI Shape

Primary screen:

- full-screen terminal attached to the selected CC_BRIDGE project;
- top or side project/agent switcher;
- special key bar;
- paste/composer drawer;
- project health and callback badges;
- read-only lock or input-enabled state.

Secondary screens:

- project picker;
- agent/window picker;
- Comms and callback list;
- Markdown reader;
- device/settings page.

On iPad, a split view is useful:

- terminal on the right;
- project/agent/Comms navigation on the left;
- Markdown drawer or overlay for reading long agent output.

On phone, keep terminal full-screen and use bottom sheets for navigation and
Markdown.

## Implementation Sequence

1. Fork or vendor tmux-mobile outside the CC_BRIDGE core runtime.
2. Add a CC_BRIDGE project registry endpoint that returns active project socket and
   session facts.
3. Replace generic session list with CC_BRIDGE project list.
4. Attach terminal stream to the selected CC_BRIDGE project's tmux session.
5. Add ProjectView side data.
6. Route agent/window switching through `project_focus_agent` and
   `project_focus_window`.
7. Add paste and input validation against current namespace/pane evidence.
8. Add Comms and Markdown drawers.
9. Lock down destructive tmux operations.

## Risks

- tmux-mobile's grouped-session model may create state CC_BRIDGE does not own.
- Phone resize may affect desktop tmux layout if attach behavior is not
  controlled.
- Generic session/pane operations may bypass CC_BRIDGE authority.
- CC_BRIDGE project discovery must not accidentally include source checkout runtime
  state or unrelated tmux sessions.
- Public tunnel exposure needs strong pairing, token, and permission defaults.

## Acceptance Criteria

- A phone/iPad can open one active CC_BRIDGE project and interact with its server
  tmux pane.
- Project switching uses CC_BRIDGE project identity, not raw tmux session names.
- Agent/window switching keeps CC_BRIDGE sidebar/project view coherent.
- Terminal input cannot continue against stale namespace/pane evidence after
  project restart or pane recovery.
- Destructive tmux operations are unavailable by default.
- Comms/Markdown features enhance the remote session without replacing it.

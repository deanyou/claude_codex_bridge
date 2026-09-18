# tmux-mobile CC_BRIDGE Implementation Blueprint

Date: 2026-06-18
Status: Superseded by Decision 005 for primary client base; retained as a
gateway adaptation blueprint.

## Goal

Adapt tmux-mobile into a CC_BRIDGE-scoped gateway reference for server-side CC_BRIDGE tmux
projects. Earlier planning considered it as the first app base; the current
direction is a native Flutter app with tmux-mobile kept as server-side
WebSocket/PTY/tmux design input.

The adapted product should keep tmux-mobile's strongest part: mobile terminal
remote control. It should replace the generic tmux session browser with CC_BRIDGE
projects, named agents, ProjectView status, lifecycle controls, notifications,
and Markdown/math content drawers.

## Target Architecture

```
phone/iPad browser or thin shell
  |
  | HTTPS/WebSocket, paired device profile
  v
CC_BRIDGE mobile gateway, forked from tmux-mobile backend
  |
  | terminal stream through socket-aware tmux attach
  | CC_BRIDGE JSON RPC through project cc-bridge-daemon sockets
  | optional CC_BRIDGE CLI subprocess for wake/stop bootstrap
  v
server-side CC_BRIDGE project
  |
  | one cc-bridge-daemon + one project tmux socket/session + named agent panes
  v
provider CLIs and CC_BRIDGE panes
```

## New Backend Abstractions

### `CcBridgeProjectRegistry`

Purpose:

- list registered/favorite/recent CC_BRIDGE projects;
- store mobile ordering and pinned state;
- resolve project root to project id and current lifecycle facts;
- expose stopped/running/degraded/offline states.

Initial storage:

- gateway-local user config is acceptable for favorites;
- project authority still comes from each `.cc-bridge` anchor and `cc-bridge-daemon` records.

Required operations:

- `listProjects()`;
- `setFavorite(projectId, favorite, order)`;
- `resolveProject(projectId)`;
- `wakeProject(projectId)`;
- `closeMobileView(projectId)`;
- `stopProject(projectId, force?)`.

Wake/stop should use CC_BRIDGE-owned lifecycle behavior. Raw tmux kill is not
acceptable.

### `CcbdRpcClient`

Purpose:

- speak CC_BRIDGE's line-delimited JSON RPC over the project `cc-bridge-daemon` Unix socket from
  TypeScript;
- reuse existing endpoints before adding mobile-specific ones.

Existing endpoints to use:

- `project_view`;
- `project_focus_agent`;
- `project_focus_window`;
- `submit`;
- `queue`;
- `watch`;
- `inbox`;
- `ack`;
- `shutdown` or `stop_all` where lifecycle semantics are appropriate.

Implementation note:

CC_BRIDGE's `CcbdClient` protocol is simple enough to implement in Node: send one
JSON request line with `api_version`, `op`, and `request`, then read one JSON
response line.

### `CcBridgeTmuxGateway`

Purpose:

- wrap tmux-mobile's `TmuxCliExecutor` with CC_BRIDGE project scoping;
- always use the selected project's tmux socket path;
- expose the selected project session and mobile view session;
- list windows/panes with CC_BRIDGE user-option metadata.

Required changes:

- add tmux formats for `@cc-bridge_project_id`, `@cc-bridge_role`, `@cc-bridge_slot`,
  `@cc-bridge_window`, and `@cc-bridge_managed_by`;
- map CC_BRIDGE agent panes to named agents;
- hide unrelated tmux sessions;
- hide or label mobile grouped sessions.

### `CcBridgeTerminalRuntime`

Purpose:

- extend tmux-mobile `TerminalRuntime` so terminal attach is bound to project
  socket path, project session name, namespace epoch, and mobile client id.

Required change:

```ts
spawnTmuxAttach({
  socketPath,
  socketName,
  sessionName
})
```

This is the first technical seam to land because CC_BRIDGE depends on project tmux
sockets.

### `MobileViewClientStore`

Purpose:

- record per-device grouped sessions or terminal clients;
- make cleanup explicit;
- prevent stale mobile grouped sessions from becoming confusing residue.

Initial version can be gateway-local. A later version should project this into
`cc-bridge-daemon`-owned runtime state if grouped sessions become durable enough to matter.

## Protocol Shape

The current protocol is tmux-session-centric. CC_BRIDGE needs project-centric control
messages.

Client to server:

- `auth`;
- `list_projects`;
- `select_project`;
- `project_lifecycle`;
- `set_project_favorite`;
- `focus_agent`;
- `focus_window`;
- `capture_scrollback`;
- `send_compose`;
- `ask_agent`;
- `get_content`;
- `ack_notification`.

Server to client:

- `auth_ok`;
- `auth_error`;
- `projects`;
- `project_attached`;
- `project_view`;
- `tmux_state`;
- `notification`;
- `content`;
- `scrollback`;
- `error`;
- `info`.

Terminal data plane can stay separate, but terminal auth must bind to:

- device/client id;
- project id;
- namespace epoch;
- terminal token;
- permission scope.

## Frontend Shape

Keep xterm as the primary surface.

Suggested shell:

- top bar: project, window, active agent, connection/health indicator;
- main area: xterm.js terminal;
- bottom toolbar: special keys, paste, compose, font/zoom;
- left drawer on iPad: projects, agents, Comms, notifications;
- bottom sheets on phone: same content in narrower panels;
- Markdown/math drawer: content reader that can overlay or split on iPad.

Replace tmux-mobile drawer sections:

- Sessions -> Favorite Projects and All Projects;
- Windows -> CC_BRIDGE Windows;
- Panes -> Named Agents plus active window panes;
- Appearance -> Settings.

Normal UI should not show:

- new session;
- kill session;
- split pane;
- kill pane;
- kill window.

Those can return later as admin actions only if backed by CC_BRIDGE authority.

## Project Lifecycle Design

Project row states:

- stopped;
- starting;
- running;
- degraded;
- stopping;
- failed;
- offline;
- unknown.

Actions:

- `wake`: start/attach CC_BRIDGE project backend;
- `open`: open remote terminal for running project;
- `close`: close mobile view only;
- `stop`: run CC_BRIDGE shutdown semantics with confirmation;
- `force_stop`: admin-only.

Implementation path:

1. use CC_BRIDGE CLI subprocess for `wake` if no `cc-bridge-daemon` socket exists yet;
2. use `CcbdRpcClient` for running project actions;
3. later add explicit mobile lifecycle endpoints if CLI wrapping is too loose.

## Agent Switching Design

Agent rows come from `project_view.agents`.

Each row should show:

- name;
- provider;
- window;
- active marker;
- state/activity;
- queue depth;
- callback badge;
- completion/failure badge;
- health/degraded marker.

Tap behavior:

- call `project_focus_agent(agent, namespace_epoch)`;
- update terminal view to the focused pane/window;
- refresh ProjectView;
- lock input and request refresh on stale epoch.

Window taps use `project_focus_window`.

## Completion Notification Design

Notification sources:

- ProjectView deltas;
- queue/watch events;
- Comms/callback state;
- agent health changes;
- project lifecycle changes.

Initial in-app notification classes:

- task completed;
- task failed/incomplete/cancelled;
- callback waiting;
- Comms mention;
- agent unhealthy/missing;
- project started/stopped/offline;
- terminal disconnected.

Native push can come later. In the current native direction, the early app can
start with an in-app notification center and platform-local notifications;
server-hosted browser notifications remain only a gateway diagnostics option.

## Markdown And Formula Design

Add a content drawer that renders CC_BRIDGE message/artifact text.

Candidate client stack:

- Markdown parser with GitHub-flavored Markdown support;
- math extension for inline/block math;
- KaTeX or MathJax-style renderer;
- sanitizer with raw HTML disabled by default.

Required UI behavior:

- code block copy;
- table horizontal scroll and card/list mode;
- formula tap-to-expand or zoom;
- raw source toggle;
- artifact expansion through CC_BRIDGE validation;
- no automatic remote image loading;
- no arbitrary local file reads from Markdown links.

## Work Sequence

### Step 1: Fork Prep

- fork or vendor tmux-mobile separately from CC_BRIDGE core;
- keep upstream README/SECURITY/SPEC attribution and MIT license;
- keep test harness green.

### Step 2: Socket-Aware Terminal Attach

- change `PtyFactory.spawnTmuxAttach(session)` to accept socket path/name;
- pass the same socket prefix used by `TmuxCliExecutor`;
- add unit and real tmux smoke tests using explicit socket path.

This is the first required code change.

### Step 3: Project Registry

- add project registry API;
- replace session picker with project picker;
- add favorites/pinned ordering;
- show lifecycle/health from CC_BRIDGE records when available.

### Step 4: CC_BRIDGE Project Attach

- resolve selected project to `tmux_socket_path` and `tmux_session_name`;
- attach terminal to that socket/session;
- create a mobile grouped session if chosen;
- record mobile view-client state for cleanup.

### Step 5: ProjectView Side Data

- implement TypeScript `CcbdRpcClient`;
- fetch/poll `project_view`;
- show project/window/agent/Comms status;
- add agent/window quick switch.

### Step 6: Safety And Permissions

- replace all-or-nothing auth with device scopes;
- make terminal input part of a trusted-device profile;
- gate lifecycle/admin separately;
- remove destructive generic tmux controls from normal UI.

### Step 7: Lifecycle

- implement wake/open/close/stop;
- use CC_BRIDGE CLI for wake when the project daemon is not running;
- use `cc-bridge-daemon` for running project actions;
- add confirmation for stop/force stop.

### Step 8: Notifications

- detect ProjectView/Comms/queue deltas;
- add in-app notification center;
- add browser notification opt-in after in-app behavior is stable.

### Step 9: Markdown/Math Drawer

- add content endpoint;
- add Markdown renderer;
- support formulas, tables, code copy, raw source, artifact expansion.

## Test Plan

Reuse upstream tests and add CC_BRIDGE-specific fakes.

Backend unit/integration:

- socket-aware PTY attach passes `-S` or `-L`;
- project registry filters unrelated tmux sessions;
- selected project attaches to correct socket/session;
- stale namespace epoch rejects focus/input;
- agent focus calls `project_focus_agent`;
- window focus calls `project_focus_window`;
- lifecycle stop never calls raw `tmux kill-server`;
- notification deltas fire once and can be acknowledged;
- Markdown content endpoint validates artifact refs.

Frontend/e2e:

- project list opens terminal;
- favorites pin/reorder;
- agent switcher changes focused agent;
- stale input lock appears after simulated epoch change;
- completion notification deep-links to agent/project;
- Markdown drawer renders code/table/formula and raw source;
- destructive controls are absent for normal profile.

Real tmux smoke:

- explicit socket path attach;
- grouped mobile session cleanup;
- phone-size and iPad-size resize;
- desktop tmux client attached concurrently.

## Design Risks To Resolve Early

1. Does grouped session resize still perturb the desktop layout too much?
2. Should mobile grouped sessions be represented in `cc-bridge-daemon` runtime state from
   day one?
3. Is CC_BRIDGE CLI wake acceptable for stopped projects, or is a separate launcher
   service required?
4. Which notification source is reliable enough for "done" reminders?
5. Which Markdown/math renderer meets sanitizer and mobile layout needs?

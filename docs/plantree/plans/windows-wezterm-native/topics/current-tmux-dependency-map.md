# Current Tmux Dependency Map

Date: 2026-06-15

## Current Contract Anchors

Current v7 behavior is explicitly tmux-centered:

- [../../../../cc-bridge-daemon-startup-supervision-contract.md](../../../../cc-bridge-daemon-startup-supervision-contract.md)
  defines CC_BRIDGE-managed tmux servers as project-scoped backend resources.
- [../../../../cc-bridge-config-layout-contract.md](../../../../cc-bridge-config-layout-contract.md)
  defines compact and `[windows]` layout semantics in tmux terms.
- [../../../../cc-bridge-daemon-project-namespace-lifecycle-plan.md](../../../../cc-bridge-daemon-project-namespace-lifecycle-plan.md)
  models one project namespace as a dedicated tmux server/socket/session.
- [../../../baseline/runtime-flows.md](../../../baseline/runtime-flows.md)
  records startup as `cc-bridge-daemon` materializing a project tmux namespace.

## Code-Level Hotspots

The current codebase has a small `TerminalBackend` abstraction, but production
resolution returns only `TmuxBackend`:

- `lib/terminal_runtime/backend_types.py`
- `lib/terminal_runtime/api.py`
- `lib/terminal_runtime/api_selection.py`
- `lib/terminal_runtime/detect.py`
- `lib/terminal_runtime/tmux_backend.py`

The project namespace controller is tmux-specific:

- `lib/cc-bridge-daemon/services/project_namespace_runtime/backend.py`
- `lib/cc-bridge-daemon/services/project_namespace_runtime/controller.py`
- `lib/cc-bridge-daemon/services/project_namespace_runtime/materialize_topology.py`
- `lib/cc-bridge-daemon/services/project_namespace_runtime/topology_plan.py`
- `lib/cc-bridge-daemon/services/project_namespace_runtime/reflow.py`
- `lib/cc-bridge-daemon/services/project_namespace_runtime/destroy.py`

Runtime execution and diagnostics assume pane-backed terminal semantics:

- `lib/provider_execution/common_runtime/terminal.py`
- `lib/provider_execution/service_runtime/start.py`
- `lib/provider_execution/service_runtime/polling.py`
- `lib/cc-bridge-daemon/services/health_assessment/tmux.py`
- `lib/cc-bridge-daemon/services/health_assessment/tmux_runtime/`
- `lib/provider_core/tmux_ownership.py`
- `lib/provider_core/tmux_ownership_runtime/`

UI and foreground attach are tmux-specific:

- `config/tmux-cc-bridge.conf`
- `config/cc-bridge-tmux-on.sh`
- `config/cc-bridge-tmux-off.sh`
- `lib/cli/services/tmux_ui.py`
- `lib/cc-bridge-daemon/project_focus/tmux.py`

## Required Refactor Boundary

Before a production WezTerm backend, these names should stop leaking above the
backend layer:

- `tmux_socket_path`
- `tmux_socket_name`
- `tmux_session_name`
- `tmux_window_id`
- `tmux_window_name`
- raw `%pane` tmux pane ids
- tmux user options as the only identity store

They can remain in tmux-specific backend records, but the upper layers need
backend-neutral concepts:

- `mux_backend_kind`
- `namespace_ref`
- `window_ref`
- `pane_ref`
- `slot_ref`
- `backend_capabilities`
- `identity_evidence`

## Stable Semantics That Must Survive

- One `.cc-bridge` anchor owns one authoritative `cc-bridge-daemon`.
- Effective config is the desired-state authority.
- Mux facts are evidence, not authority.
- Pane death is supervised by `cc-bridge-daemon`.
- `cc-bridge kill` is project-level cleanup.
- `cc-bridge restart <agent>` restarts one slot without mutating unrelated slots.
- Provider-native completion remains provider-owned.
- Tool windows do not become agents.
- `cc-bridge_self` can read pane evidence but must not use raw destructive mux
  mutation.

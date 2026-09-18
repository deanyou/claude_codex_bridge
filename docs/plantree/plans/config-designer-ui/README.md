# Config Designer UI Plan

Date: 2026-06-06

## Purpose

Plan a focused CC_BRIDGE configuration experience that starts with a cleaner
`cc-bridge-config` skill, then adds an optional local browser editor for
`.cc-bridge/cc-bridge.config`, and finally exposes that editor from the native sidebar.

The plan keeps configuration authority in `.cc-bridge/cc-bridge.config`. It does not turn
the skill or UI into workflow-memory authoring or a second source of truth.
Hot reload is an explicit delegation to the existing mounted-daemon control
plane, not an independent runtime authority.

## File Map

- [roadmap.md](roadmap.md): staged sequence and gates.
- [open-questions.md](open-questions.md): unresolved product and implementation
  questions only.
- [topics/cc-bridge-config-skill-scope.md](topics/cc-bridge-config-skill-scope.md):
  required skill cleanup, menu-style configuration guidance, and boundaries.
- [topics/config-ui-design.md](topics/config-ui-design.md): local browser UI
  shape, API, safety model, and validation flow.
- [topics/sidebar-config-entry.md](topics/sidebar-config-entry.md): sidebar
  icon entry point and the decision to replace the prominent restart icon.
- [decisions/001-config-ui-is-local-config-editor.md](decisions/001-config-ui-is-local-config-editor.md):
  decision record for keeping the UI local, optional, and config-only.
- [decisions/002-config-single-authority.md](decisions/002-config-single-authority.md):
  decision record for canonical `.cc-bridge/cc-bridge.config` writing rules that keep
  topology authority in `[windows]` and use `[agents.<name>]` only as overlays.

## Related Sources

- [../../../cc-bridge-config-layout-contract.md](../../../cc-bridge-config-layout-contract.md)
- [../managed-tool-windows/README.md](../managed-tool-windows/README.md)
- [../sidebar-tips-layout/README.md](../sidebar-tips-layout/README.md)
- [../workspace-sharing/README.md](../workspace-sharing/README.md)

## Scope

In scope:

- Clean `cc-bridge-config` skill guidance so it edits config only.
- Present configurable fields as a clear menu/list grouped by user level.
- Generate and validate `version = 2` windows topology by default.
- Expose Rich as the only built-in non-agent pane choice. Do not generate or
  advertise removed editor-tool fields.
- Add a local browser config editor launched by a CLI command.
- Add a sidebar icon that launches the same config editor.

Out of scope:

- Editing `.cc-bridge/cc-bridge_memory.md` or per-agent memory.
- Designing workflow/role memory inside the config skill.
- Writing provider-state homes, installed roles, or runtime records.
- Replacing `cc-bridge reload` or project lifecycle commands.
- Hosting a remote web service or adding a persistent web daemon.

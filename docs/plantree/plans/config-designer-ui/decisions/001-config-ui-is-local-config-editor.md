# Config UI Is A Local Config Editor

Date: 2026-06-06

## Context

CC_BRIDGE configuration has grown enough that a menu-style skill and optional visual
editor would help users discover supported fields. At the same time, CC_BRIDGE already
has clear authority boundaries: `.cc-bridge/cc-bridge.config` owns project config, memory
files own workflow context, and `cc-bridge-daemon` owns runtime state.

## Decision

The config UI will be a local, optional editor for `.cc-bridge/cc-bridge.config`. It will be
launched by CLI, bind only to `127.0.0.1`, validate through the existing config
loader, and write only after preview and confirmation.

The UI and `cc-bridge-config` skill will not edit workflow memory, provider-state
homes, installed role stores, or runtime records during ordinary config work.

The panel may also expose the global CC_BRIDGE Appearance preference as a narrowly
scoped exception. That control writes only
`$XDG_CONFIG_HOME/cc-bridge/theme.json` through the same service as `cc-bridge theme`; it
does not add theme fields to project TOML and does not read or write user
terminal-emulator configuration.

The sidebar may expose a config icon, but that icon will launch the same config
UI command instead of becoming a second configuration authority.

## Consequences

- Config remains file-backed and reviewable.
- User appearance remains separately file-backed and global; it cannot drift
  into a project config slot.
- The browser UI can be added without making `cc-bridge-daemon` a web server.
- Sidebar integration can stay thin and optional.
- Workflow memory remains a separate explicit user request.
- Future remote or shared configuration tools would need a separate decision.

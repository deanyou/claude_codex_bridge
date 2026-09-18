# Standalone Ratatui Client And CC_BRIDGE_DAEMON Authority

Date: 2026-07-14

## Context

CC_BRIDGE already ships a Rust `ratatui`/`crossterm` sidebar with Unix-socket
transport, mouse handling, themes, release builds, and rendering tests. The
existing optional `cc-bridge-workbench` command instead names a Rich terminal bundle
for files and editors. Adding another Python TUI stack or extending the compact
sidebar application would increase packaging cost and mix responsibilities.

## Decision

Implement the workflow workbench as a separate Rust Ratatui client exposed by
`cc-bridge tui` and backed by versioned cc-bridge-daemon projection and command APIs. Reuse small
stable sidebar protocol/theme pieces where justified, but keep application
state and layout independent.

`cc-bridge-daemon` and scripted workflow services remain the sole authorities for tasks,
queueing, interactions, cancellation, result collection, and topology. The TUI
keeps only presentation preferences and unsent drafts.

## Consequences

- No new Python TUI runtime dependency is required.
- The rich file-workbench name and lifecycle remain unchanged.
- Backend state/API work precedes most interactive UI work.
- Closing or restarting the TUI cannot stop or complete workflow tasks.
- A future GUI can consume the same projection and command contracts.

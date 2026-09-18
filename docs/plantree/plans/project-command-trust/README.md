# Project Command Trust

Date: 2026-08-13

Status: Implemented, verified, and committed locally

## Scope

Close issue #299 without changing ordinary projects: gate only explicit
project-local `tool_windows.<name>.command` and
`agents.<name>.provider_command_template` fields. Store exact-value approval
outside the repository and enforce it at CLI startup, cc-bridge-daemon bootstrap/reload,
and the final shell-backed execution sinks.

## Authority

- [cc-bridge config/layout contract](../../../cc-bridge-config-layout-contract.md)
- [cc-bridge-daemon startup/supervision contract](../../../cc-bridge-daemon-startup-supervision-contract.md)
- [implementation status](implementation-status.md)

## Acceptance

- No command-bearing project fields: behavior remains unchanged.
- First interactive startup shows exact escaped fields and asks once.
- Unapproved non-interactive startup cannot execute a marker command.
- Approval survives unrelated config edits; command edits invalidate it.
- Receipt is owner-only and outside `.cc-bridge` on Linux/macOS/WSL and Windows.
- Daemon, reload, tool pane, and provider launch paths fail closed independently.

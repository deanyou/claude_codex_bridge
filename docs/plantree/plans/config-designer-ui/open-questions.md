# Open Questions

Date: 2026-06-06

## Product

- Should `cc-bridge config ui` write project config only in the first release, or also
  support editing the user-level `~/.cc-bridge/cc-bridge.config` behind an explicit mode?
- Should the first UI support compact/hybrid configs, or offer migration to
  windows topology before opening the full editor?
- Should advanced fields be hidden behind a single "Advanced" toggle, or grouped
  into separate Workspace, Model/API, Provider, and Runtime sections?

## Implementation

- Should `cc-bridge config ui` be implemented as a tiny stdlib HTTP server with inline
  HTML/JS, or should it use a bundled static asset folder?
- Should browser opening use Python's `webbrowser`, platform-specific commands,
  or both with clear fallback output?
- Should the sidebar launch the UI by spawning the sibling `cc-bridge` binary directly
  in the first slice, or should a daemon RPC own the launch and status result?

## Safety

- What TTL should the local UI token use?
- Should apply be blocked when the current worktree is a public Git repository
  and the draft contains likely secrets in `key`, `url`, or provider env fields?

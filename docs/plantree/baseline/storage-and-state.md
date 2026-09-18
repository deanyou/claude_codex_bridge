# Storage And State

Date: 2026-05-25

## User-Authored Project Files

- `.cc-bridge/cc-bridge.config`: highest-priority project config authority when present.
- `.cc-bridge/cc-bridge_memory.md`: shared project memory.
- `.cc-bridge/agents/<agent>/memory.md`: optional per-agent memory.

These are user-facing concepts and should be explained in README only at the
level needed for first setup and team customization.

## Runtime Evidence

- `.cc-bridge/cc-bridge-daemon/`: lifecycle, lease, namespace, diagnostics, and backend records.
- `.cc-bridge/agents/<agent>/runtime.json`: configured-agent runtime records.
- Provider session files and tmux facts are evidence, not public configuration
  authority.

The README should avoid asking users to edit runtime records manually.

## Public Assets

- Current media is under `assets/`.
- A README v7 refresh should use a dedicated subfolder such as
  `assets/readme_v7/` if new screenshots and animations are created.
- Large generated raw recordings should not be committed unless explicitly
  needed; only optimized public artifacts should be referenced from README.


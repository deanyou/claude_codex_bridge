# Isolated Managed Neovim Profile

Date: 2026-05-30

## Context

The Neovim tool-window feature should work after `cc-bridge update` or
`install.sh install`, but the official LazyVim starter installation normally
targets the user's default Neovim config path. CC_BRIDGE users may already have a
personal `~/.config/nvim`, plugin data, state, cache, and tmux settings.

Mutating those global files would violate CC_BRIDGE's isolation expectations and
would make install/update risky.

## Decision

CC_BRIDGE-managed Neovim/LazyVim installs into CC_BRIDGE-owned, isolated paths and launches
through a `cc-bridge-nvim` wrapper that sets XDG/NVIM environment variables.

The wrapper is the command used by managed Neovim tool windows. It may use a
CC_BRIDGE-downloaded Neovim binary or a verified compatible system `nvim`, but it
must not require or modify the user's default Neovim home.

tmux compatibility is applied only to CC_BRIDGE-managed tmux sessions, windows, or
panes.

## Consequences

- `cc-bridge update` and `install.sh install` can prepare Neovim/LazyVim without
  overwriting personal Neovim files.
- CC_BRIDGE can test a deterministic editor environment.
- Users who want their personal Neovim can still configure a tool window with a
  custom command such as `command = "nvim"`.
- LazyVim plugin data may take disk space under CC_BRIDGE-owned data/cache paths.
- The installer needs an explicit doctor/provisioning path and integrity checks
  instead of relying on whatever `nvim` happens to be on `PATH`.

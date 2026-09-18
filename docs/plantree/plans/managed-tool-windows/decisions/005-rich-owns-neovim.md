# Rich Owns Neovim

Date: 2026-06-15

## Context

The earlier managed-tool plan added a standalone CC_BRIDGE-managed Neovim/LazyVim
tool path. That was useful during exploration because it proved isolated
profiles, folder opening, Markdown rendering, opener behavior, and terminal
capability checks.

The product direction has changed: the richer editor/file/media surface is now
the optional rich workbench. Normal CC_BRIDGE should stay focused on the core
agent/tmux/sidebar runtime and should not install or update a standalone
Neovim tool.

## Decision

Neovim/LazyVim is no longer a normal CC_BRIDGE feature. It is an internal component of
the optional rich bundle.

User-facing consequences:

- `cc-bridge install` and ordinary `cc-bridge update` do not install, update, or repair
  Neovim/LazyVim.
- `cc-bridge update rich` is the explicit lifecycle entry for installing or updating
  the rich bundle, including its managed LazyVim/Neovim profile.
- `cc-bridge rich` may launch only when the rich bundle is installed and enabled; if
  it is missing, it should tell the user to run `cc-bridge update rich`.
- Existing lower-level Neovim commands are removed from the public normal CC_BRIDGE
  command surface.
- `cc-bridge rich-install` is removed; it is not kept as a compatibility alias.
- The `rich` layout alias remains a non-agent tool alias and must not create
  provider runtime, ask targets, completion records, or Comms rows.

Implementation consequences:

- Remove install/update post-hooks that call standalone Neovim provisioning.
- Remove or hide `cc-bridge tools install/update/doctor neovim` from the public
  normal CC_BRIDGE surface.
- Keep the isolated Neovim implementation reusable internally by rich until it
  is either renamed or absorbed into the workbench runtime.
- Update docs and tests so acceptance is based on `cc-bridge update rich`, not
  automatic Neovim provisioning.

## Compatibility

Existing generated `cc-bridge-nvim` files may remain on disk after upgrade. They are
treated as old optional tool artifacts, not as normal CC_BRIDGE runtime authority.
Rich install/update may reuse or regenerate them under CC_BRIDGE-owned tool paths.

## Follow-Up

- Add `cc-bridge update rich` parsing and route it to rich bundle provisioning.
- Make normal `cc-bridge update` skip rich and Neovim work unless a rich-specific
  target is provided.
- Remove `cc-bridge rich-install` routing and help text.

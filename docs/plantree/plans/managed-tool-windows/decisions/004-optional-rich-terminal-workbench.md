# Optional Rich Terminal Workbench

Date: 2026-06-15

## Context

Local experiments with Yazi, Poppler, FFmpeg, Rich Markdown rendering, Chafa,
WezTerm, and the managed LazyVim profile showed that a much richer terminal
workspace is possible:

- Yazi can browse projects and preview Markdown, PDF, and video surfaces.
- LazyVim can serve as the primary editor and Markdown authoring tool.
- WezTerm can be the recommended terminal for richer media preview.

The same experiments also showed that rich media support is terminal-sensitive.
Plain tmux or unknown terminals can render PDF/video image previews poorly or
fail terminal protocol checks.

## Decision

CC_BRIDGE will treat the rich terminal workbench as an optional recommended profile,
not a default hard dependency.

The default tool profile remains safe and broadly compatible:

- Markdown preview/rendering is enabled where dependencies are available.
- PDF and video default to text/metadata preview in unsafe terminal paths.
- Images and rich media fall back to external open/reveal behavior when inline
  rendering is unavailable.

The rich workbench profile may recommend WezTerm, Yazi, and CC_BRIDGE-managed
LazyVim, but it must still be gated by capability checks and must degrade
surface-by-surface.

CC_BRIDGE will model the rich workbench as one CC_BRIDGE-owned bundle and lifecycle unit,
not as unrelated per-tool dotfile changes. The bundle owns generated
configuration, wrappers, doctor output, enabled state, and launched tool-window
records for WezTerm, Yazi, LazyVim, Markdown preview, and rich preview helpers.

Bundle lifecycle is atomic at the product level:

- install prepares the CC_BRIDGE-owned profiles and helper wrappers;
- enable records the desired workbench profile;
- launch starts CC_BRIDGE-owned workbench windows;
- disable closes or detaches CC_BRIDGE-owned workbench surfaces together;
- uninstall removes only CC_BRIDGE-owned generated config and installed artifacts.

Preview features can still degrade independently inside the bundle. Missing PDF
image support should not break Markdown preview, and missing video thumbnails
should not prevent Yazi from opening.

## Consequences

- CC_BRIDGE can offer a polished recommended setup for users who want a rich terminal
  workspace without making WezTerm mandatory.
- Linux, macOS, WSL, SSH, and plain tmux users keep a working default path.
- `doctor` output becomes the authority for enabling image/PDF/video previews.
- Yazi and LazyVim should share the same terminal capability model rather than
  each optimistically enabling rich media.
- The implementation must keep generated tool profiles isolated from user
  dotfiles and must not overwrite `~/.config/yazi`, `~/.config/nvim`,
  `~/.config/wezterm`, or global tmux configuration.
- Disable/close behavior must target only CC_BRIDGE-launched workbench windows and
  must not kill provider panes, agent sessions, or unrelated user terminal
  windows.

## Follow-Up

- Add a terminal/workbench capability doctor.
- Define the workbench bundle manifest and lifecycle commands.
- Add CC_BRIDGE-owned safe and rich Yazi profiles.
- Add a recommended workbench preset that composes Yazi and Neovim tool
  windows without turning either into an agent.
- Extend the managed LazyVim rich-media policy to consume the shared terminal
  capability result.

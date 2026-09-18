# Neovim And LazyVim Provisioning

Date: 2026-05-30

## Status

Superseded for the normal CC_BRIDGE product surface. Neovim/LazyVim is now owned by
the optional rich bundle. See
[../decisions/005-rich-owns-neovim.md](../decisions/005-rich-owns-neovim.md).

This file remains as historical implementation context for the internal rich
LazyVim component.

The provisioning contract below is superseded for public CLI behavior. Do not
restore `cc-bridge tools doctor/install/update neovim`, `CC_BRIDGE_INSTALL_NEOVIM`, or
install/update hooks for ordinary CC_BRIDGE. Current public provisioning is
`cc-bridge update rich`; rich may continue to reuse the internal Neovim component.

## Goal

`cc-bridge update` and `install.sh install` should be able to prepare a CC_BRIDGE-managed
Neovim/LazyVim tool profile so a project can declare:

```toml
[tool_windows.neovim]
command = "cc-bridge-nvim"
label = "neovim"
```

and get a working Neovim window without requiring the user to manually install
Neovim, clone LazyVim, or tune tmux for common terminal behavior.

The install must be clean: CC_BRIDGE must not overwrite a user's existing Neovim
configuration or global tmux config.

## Source References

- Neovim publishes pre-built release packages for Linux and macOS on its
  GitHub releases page, including Linux AppImage/tarball and macOS arch
  tarballs.
- LazyVim's official installation uses the `LazyVim/starter` template and
  recommends running `:LazyHealth` after first start.
- LazyVim's starter uses `lazy.nvim` and defaults LazyVim/lazy.nvim to their
  latest stable release behavior unless the user changes plugin specs.

## Provisioning Contract

Add a reusable provisioning path shared by source install, release install, and
`cc-bridge update`:

```text
cc-bridge tools doctor neovim
cc-bridge tools install neovim
cc-bridge tools update neovim
```

Installer/update hooks should call the same internal implementation rather than
embedding Neovim-specific shell logic in multiple places.

Default policy:

- interactive install/update asks whether to install or refresh the
  CC_BRIDGE-managed Neovim/LazyVim bundle;
- non-interactive install/update skips provisioning and prints
  `cc-bridge tools install neovim` as the follow-up command;
- failures are warnings by default so CC_BRIDGE itself still installs;
- `CC_BRIDGE_INSTALL_NEOVIM=0` skips it without prompting;
- `CC_BRIDGE_INSTALL_NEOVIM=1` requires provisioning and fails install/update on
  error;
- `CC_BRIDGE_LAZYVIM_PROFILE=0` installs only the Neovim binary wrapper.

## Storage Layout

Do not store mutable Neovim profile state under the release install prefix if
that prefix is replaced on every update.

Preferred stable paths:

```text
~/.local/share/cc-bridge/tools/neovim/
  manifest.json
  bin/nvim -> versioned binary
  versions/<version>/
  lazyvim/profile/
  lazyvim/starter-template/

~/.local/state/cc-bridge/tools/neovim/
  xdg-state/

~/.cache/cc-bridge/tools/neovim/
  xdg-cache/
```

The `cc-bridge-nvim` wrapper should launch with isolated XDG paths:

```text
XDG_CONFIG_HOME=~/.local/share/cc-bridge/tools/neovim/lazyvim/profile/config
XDG_DATA_HOME=~/.local/share/cc-bridge/tools/neovim/lazyvim/profile/share
XDG_STATE_HOME=~/.local/state/cc-bridge/tools/neovim/xdg-state
XDG_CACHE_HOME=~/.cache/cc-bridge/tools/neovim/xdg-cache
NVIM_APPNAME=nvim
```

This makes Neovim read `.../profile/config/nvim` instead of
`~/.config/nvim`, and keeps LazyVim plugin data out of the user's normal
Neovim home.

## Binary Acquisition

Use a versioned manifest checked into CC_BRIDGE, for example:

```json
{
  "neovim_version": "0.11.x",
  "assets": {
    "linux-x86_64": {
      "url": "https://github.com/neovim/neovim/releases/download/...",
      "sha256": "..."
    },
    "macos-arm64": {
      "url": "https://github.com/neovim/neovim/releases/download/...",
      "sha256": "..."
    },
    "macos-x86_64": {
      "url": "https://github.com/neovim/neovim/releases/download/...",
      "sha256": "..."
    }
  },
  "lazyvim_starter_commit": "..."
}
```

Rules:

- Prefer official release tarballs over package-manager installs so CC_BRIDGE has a
  predictable binary path.
- Verify downloaded asset checksums before activation.
- Keep the previously working version until the new version verifies.
- On unsupported platforms, reuse system `nvim` if it satisfies the minimum
  version and report a clear warning otherwise.
- Do not require Rust for this feature.

## LazyVim Profile

LazyVim setup should clone or copy the `LazyVim/starter` template into the
managed profile, then remove `.git` from the managed profile to avoid treating
it as a user project repository.

First implementation note: CC_BRIDGE writes an isolated `init.lua` that bootstraps
`lazy.nvim` and loads `LazyVim/LazyVim` into the managed profile, then runs
`cc-bridge-nvim --headless +Lazy! sync +qa` during provisioning. A fuller
starter-template mirror can be added later without changing the wrapper path or
user config isolation contract.

The managed profile must not assume that the user's terminal font supports Nerd
Font glyphs. CC_BRIDGE writes a managed `lua/plugins/cc-bridge-terminal-compat.lua` overlay
that defaults `mini.icons` and LazyVim UI icon tables to ASCII-safe output.
Users who explicitly want glyphs can launch with
`CC_BRIDGE_LAZYVIM_ICON_STYLE=glyph cc-bridge-nvim`.

Profile update policy:

- first install creates the managed profile;
- update refreshes CC_BRIDGE-owned bootstrap files only when the profile still carries
  the CC_BRIDGE managed marker;
- user-local files under an explicit override folder are preserved;
- destructive profile reset requires an explicit command such as
  `cc-bridge tools reset neovim`.

## tmux Compatibility

Compatibility must be applied to CC_BRIDGE-managed tmux sessions, windows, or panes,
not user-global `~/.tmux.conf`.

First-slice tmux policy:

- set a true-color terminal feature for the CC_BRIDGE session when supported;
- enable focus events at the session level;
- keep mouse behavior aligned with the existing CC_BRIDGE session policy;
- keep escape-time low enough for Neovim key sequences without changing global
  tmux;
- prefer an OSC52 clipboard lane when no platform clipboard helper is present;
- set the tool pane environment so `TERM`, `COLORTERM`, and XDG paths are
  coherent for Neovim.

The exact tmux commands must use the existing project/session scoped tmux
backend helpers so the feature honors CC_BRIDGE's isolation rule.

## Install/Update Flow

`install.sh install`:

1. install CC_BRIDGE as today;
2. ask in an interactive terminal whether to provision Neovim/LazyVim, unless
   `CC_BRIDGE_INSTALL_NEOVIM` forces or skips it;
3. create or refresh the `cc-bridge-nvim` wrapper;
4. print `OK`, `WARN`, or `SKIP` with a short reason.

`cc-bridge update`:

1. update CC_BRIDGE as today;
2. run the same prompt/provisioner after the new package is installed;
3. preserve the last working Neovim profile if the new provisioning step fails;
4. report the tool status in the update summary.

`cc-bridge tools doctor neovim`:

- reports resolved binary path and version;
- reports LazyVim profile path and marker state;
- runs a headless health check and reports degraded when `lazy.nvim` or
  LazyVim plugin files are missing;
- reports tmux compatibility readiness;
- reports missing optional dependencies such as clipboard helpers;
- never mutates state.

## Failure Policy

Provisioning should fail closed for integrity and fail soft for optionality:

- checksum mismatch: do not activate the binary;
- partial download: keep old version;
- LazyVim bootstrap failure: remove partial plugin directories, retry once,
  fall back from `git clone` to the GitHub stable tarball, then warn if both
  fail;
- missing network in interactive/default soft mode: warn and continue CC_BRIDGE
  install/update;
- explicit `CC_BRIDGE_INSTALL_NEOVIM=1`: return non-zero on provisioning failure;
- unsupported OS/arch: skip with a clear diagnostic unless a compatible system
  `nvim` is available.

## Implementation Slices

1. Add `cc-bridge tools doctor/install/update neovim` with fake downloader tests.
2. Add official release metadata lookup, checksum verification, and stable
   storage paths.
3. Add `cc-bridge-nvim` wrapper and isolated XDG LazyVim profile.
4. Integrate provisioning into `install.sh install` and `cc-bridge update`.
5. Wire the Neovim tool-window preset to use `command = "cc-bridge-nvim"`.
6. Add CC_BRIDGE session-scoped tmux compatibility settings before launching the tool
   pane.

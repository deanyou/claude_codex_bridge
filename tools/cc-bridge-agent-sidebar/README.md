# cc-bridge-agent-sidebar

CC_BRIDGE-native tmux sidebar for rendering `cc-bridge-daemon` ProjectView.

This crate is intentionally not a generic tmux scanner. It talks to the project
`cc-bridge-daemon` Unix socket and treats `ProjectView` as the only UI authority.

Phase 1 launch shape:

```text
cc-bridge-agent-sidebar --cc-bridge-daemon-socket <path> --project-root <path> --pane-window <name>
```

Keyboard controls:

- `q` / `Esc`: exit the sidebar process only.
- `r`: restart every configured agent pane through cc-bridge-daemon without detaching the current tmux session.
- `Q`: run `cc-bridge kill` from the project root.

The top panel shows inline controls on the right side of the `Sidebar` title bar:

- `⚙`: open the current project's local `cc-bridge config ui` page
- `×`: kill project (`Q`)

The settings action launches the project-scoped CC_BRIDGE CLI without blocking the
sidebar. The Comms panel reports launch progress, the local URL, or a concrete
startup error. Keyboard `r` remains available for deliberate pane restart, but
restart is no longer exposed as a header icon.

Upstream inspiration and future UI component migration come from
`hiroppy/tmux-agent-sidebar`; its MIT license is retained in `LICENSE.upstream`.

# Tmux CC_BRIDGE Quickstart

This is user-facing tmux guidance for CC_BRIDGE-managed sessions.

Safe user actions:

- detach from tmux
- reattach to the CC_BRIDGE session
- navigate windows and panes
- zoom a pane
- enter copy/scroll mode
- resize panes interactively for local viewing

Unsafe maintenance actions for `cc-bridge_self`:

- `tmux kill-pane`
- `tmux kill-window`
- `tmux kill-server`
- `tmux respawn-pane`
- ad hoc `tmux send-keys`
- manual pane/window creation as a replacement for CC_BRIDGE recovery

`cc-bridge_self` may use read-only CC_BRIDGE-owned pane evidence: pane list, pane text
capture, activity sampling, and later bounded screenshots. Pane evidence does
not define configured-agent authority.

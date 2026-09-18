# CC_BRIDGE Mobile Plan Tree

Date: 2026-06-27

## Purpose

This is the planning entrypoint for the authoritative CC_BRIDGE Mobile subtree inside
the CC_BRIDGE monorepo.

## Authority Order

1. Active decisions under `docs/plantree/plans/mobile-tmux-control/decisions/`.
2. The mobile roadmap and execution plan under
   `docs/plantree/plans/mobile-tmux-control/`.
3. Baseline notes under `docs/plantree/baseline/`.
4. External CC_BRIDGE source contracts in `/home/bfly/yunwei/cc-bridge_source/docs/` when
   server-side CC_BRIDGE behavior is relevant.

## Baseline

- [baseline/README.md](baseline/README.md)

## Active Plans

| Plan | Status | Current Phase | Last Landed | Next Target |
| :--- | :--- | :--- | :--- | :--- |
| [mobile-tmux-control](plans/mobile-tmux-control/README.md) | In Progress | Phase 4G Per-Agent Terminal Mode | 2026-07-04 plan update added [agent-terminal-mode-remote-pane-control](plans/mobile-tmux-control/topics/agent-terminal-mode-remote-pane-control.md) as the executable package for direct per-agent pane control. | Implement per-agent `Chat / Terminal` mode in `/home/bfly/yunwei/cc-bridge_source`, then collect strict real Android Emulator screenshots/recording and gateway logs before acceptance. |

## How To Read

Start with the active plan root, then read roadmap, decisions, and the
specific topic file for the current task.

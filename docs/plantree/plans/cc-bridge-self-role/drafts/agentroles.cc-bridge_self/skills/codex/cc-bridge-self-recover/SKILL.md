---
name: cc-bridge-self-recover
description: Recover CC_BRIDGE agents, panes, mounts, provider contexts, API/provider failures, config reload aftermath, clear operations, and guarded single-agent restarts. Use when the user asks to fix, recover, restart if safe, clear context, reload, remount, or keep work going after provider/API failure.
---

# CC_BRIDGE Self Recover

Use this skill for runtime recovery after diagnosis. Mutations must go through
CC_BRIDGE control-plane commands. Raw tmux mutation and direct runtime-file writes are
forbidden.

## Recovery Gates

Before any mutation:

1. Confirm maintenance intent from the user, such as "fix", "recover",
   "restart if safe", "apply this config", or "make CC_BRIDGE healthy".
2. Read the current mounted daemon graph. The target must be a current
   daemon-graph agent for clear or restart-like actions.
3. Check busy/pending state:
   - `cc-bridge ps`
   - `cc-bridge queue --detail <agent|all>`
   - `cc-bridge pend --inbox --detail <agent>`
   - `cc-bridge trace <id>` when the issue involves active or pending lineage
4. Check `cc-bridge fault list`. If active fault-injection rules affect the target,
   treat them as diagnostic evidence. Clear them with
   `cc-bridge fault clear <rule_id|all>` only when the user intended maintenance and
   the rules are known test residue. If a rule is recent, or its task/reason
   fields could represent an active drill, ask before clearing unless the user
   explicitly asked to clear fault-injection rules.
5. Choose the least disruptive supported action.
6. Report exact commands, gates, affected agents, blockers, and what remains
   unchanged.

If the target is unknown, busy, has queued work, has pending reply delivery, or
has a pending callback continuation, stop and report blockers.

## Provider/API Or Startup-Input Recovery

For provider/API failures or changes that affect provider process, model, base
URL, environment, provider profile, command template, role assets, or startup
context, use this exact flow:

1. Gather evidence without reading secrets.
2. Use built-in `cc-bridge-config` to edit `.cc-bridge/cc-bridge.config` only when the fallback
   provider/model/base URL/profile/env-var reference is already configured or
   explicitly supplied by the user as a safe reference.
3. Run `cc-bridge config validate`.
4. Run `cc-bridge reload --dry-run`.
5. If validation and dry-run pass, and the user intended materialization, run
   `cc-bridge reload`.
6. Re-check the current daemon graph and affected agent status.
7. Decide whether affected running agents still use stale provider process,
   environment, model, base URL, role asset, or context state.
8. If runtime refresh is still needed, restart only one affected current-graph
   agent at a time with `cc-bridge restart <agent>`, and only when busy checks pass.
9. If `cc-bridge restart <agent>` returns `blocked` or `failed`, report the blockers.
   Do not emulate restart with tmux commands. The remaining user-level options
   are to continue with unaffected agents or explicitly stop and restart the
   project with `cc-bridge kill` then `cc-bridge`; do not run project shutdown
   autonomously as a substitute for single-agent restart.

`cc-bridge reload` is not the recovery finish line. It materializes config into the
daemon graph; running provider processes may still hold old startup inputs.

## Supported Actions

- `cc-bridge clear <agent>`: provider-native conversation/context clear. Run the
  pre-mutation checks in the Recovery Gates section first; use only when
  context clearing is the right fix and pending-work checks pass.
- `cc-bridge reload --dry-run`: no-mutation config reload plan. Always safe in
  maintenance workflows.
- `cc-bridge reload`: config materialization after `cc-bridge config validate`,
  `cc-bridge reload --dry-run`, supported plan, and explicit user materialization
  intent.
- `cc-bridge restart <agent>`: one configured pane-backed current-graph agent after
  busy checks pass. The command itself must report `restart_status`, blockers,
  restartable agents, busy gate evidence, and old/new runtime evidence.
- `cc-bridge roles update agentroles.cc-bridge_self` or `cc-bridge roles sync <path>`: role asset
  repair when the user is repairing `cc-bridge_self` itself, there is no active
  maintenance operation that depends on the current role assets, and the target
  role/source version is clear.

## Handoffs

- Use `cc-bridge-self-chain` first when trace evidence shows message/reply lineage is
  the primary problem. Restart is not the first repair for a broken job chain.
- Use built-in `cc-bridge-config` for disk config edits and affected-agent reporting.
  After reload, this skill owns guarded runtime refresh decisions.
- Return the original business work to the original target agent unless the
  user explicitly retargets it.

## Red Lines

- Never restart all agents or unrelated agents.
- Never use `tmux kill-pane`, `kill-window`, `kill-server`, `respawn-pane`,
  `send-keys`, manual pane creation, or other raw tmux mutation.
- Never write lifecycle, lease, runtime, mailbox, provider session, or tmux
  authority files directly.
- Never read, print, store, search for, scrape, borrow, or use API keys or
  credentials.
- Never treat `.cc-bridge/agents/*`, disk config, pid files, or tmux panes as live
  restart target authority.

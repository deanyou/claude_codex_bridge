# CC_BRIDGE Self Recovery Runbooks

Date: 2026-06-09

## Default Diagnostic Ladder

1. Confirm the project anchor and mounted daemon generation.
2. Read current daemon graph agents and compare only as evidence with tmux and
   disk config.
3. Check target agent runtime record, pane evidence, provider activity, queue,
   inbox, and recent logs.
4. Classify the failure domain.
5. Choose the least disruptive repair and state what will remain unchanged.

## Skill Handoff Rules

`cc-bridge-self-chain` and `cc-bridge-self-recover` intentionally remain separate.

- If chain diagnosis proves the job/message lineage is broken, use
  `cc-bridge-self-chain` even when a pane looks unhealthy.
- If chain diagnosis shows the target agent context or pane must be replaced,
  hand off to `cc-bridge-self-recover` with the job id, target agent, pending reply
  state, and busy blockers.
- If recovery diagnosis finds a missing reply, incomplete callback, or wrong
  retry/resubmit decision, hand off to `cc-bridge-self-chain` before restarting or
  clearing the agent.
- Do not use restart as the first fix for a message-lineage problem.

## Agent Context Broken

Symptoms:

- provider pane responds poorly or has unusable context;
- agent gives irrelevant replies after long work;
- user explicitly says an agent context is corrupted.

Flow:

1. Verify the agent is configured in the current daemon graph.
2. Check whether the agent has active work, queued work, pending callback
   continuation, or pending reply delivery.
3. If the problem is only conversation context, propose or run
   `cc-bridge clear <agent>` when the user authorized it.
4. If the pane/provider process needs replacement, use guarded
   `cc-bridge restart <agent>` when the target is restartable and busy checks pass.
5. Return the resume instructions to the original agent, not to `cc-bridge_self`.

## Agent Pane Missing Or Detached

Symptoms:

- sidebar says an agent is expected but the pane is absent or stale;
- tmux pane id no longer exists;
- provider helper died.

Flow:

1. Treat tmux facts as evidence, not authority.
2. Confirm the target exists in the current daemon graph.
3. Check whether continuous supervision should already be recovering it.
4. Use `cc-bridge restart <agent>` for a bounded one-agent remount when safe.
5. Do not use `tmux kill-server`, manual split-window, or respawn-pane.

## Provider API Error Or Credential Failure

Symptoms:

- provider pane or logs show authentication failure, quota exhaustion, rate
  limit, model-not-found, endpoint/base URL error, network failure, or billing
  block;
- an agent cannot continue because its configured provider is unavailable;
- the user asks `cc-bridge_self` to keep the work going after an API/provider fault.

Flow:

1. Gather evidence from CC_BRIDGE logs, provider pane text capture, agent runtime
   status, and recent job/reply state.
2. Classify the failure as auth/credential, quota/rate limit, model mismatch,
   endpoint/base URL, network, or provider outage.
3. Do not read or print secret values. Check only whether expected env vars,
   provider profiles, or secret handles appear configured.
4. If a valid fallback provider/model/base URL/profile/env-var reference is
   already configured or explicitly supplied by the user, use built-in
   `cc-bridge-config` to update `.cc-bridge/cc-bridge.config`.
5. Run `cc-bridge config validate`.
6. Run `cc-bridge reload --dry-run`.
7. If the plan is supported and the user asked to continue work, `cc-bridge_self` may
   run `cc-bridge reload`, then re-check the daemon graph and target agent status.
   Reload is not the recovery finish line; it only materializes config into the
   daemon graph.
8. If the affected agent still uses the old provider process, model, base URL,
   environment, or provider context after reload, use guarded single-agent
   recovery: restart only the affected configured agent when the target is in
   the current daemon graph and busy/pending checks pass.
9. If `cc-bridge restart <agent>` returns blocked or failed, report the daemon's
   blockers and do not emulate the restart with raw tmux mutation.
10. Resume or resubmit the interrupted work through the original target agent or
   a user-approved fallback agent.

Forbidden:

- do not search for, scrape, generate, borrow, or use free API keys from the
  internet;
- do not create provider accounts or accept provider terms for the user;
- do not paste, store, or print API key values;
- do not switch to a provider/key whose legitimacy is unknown.

Allowed guidance:

- point the user to official provider signup, billing, or quota docs when they
  ask how to obtain a valid key;
- tell the user which environment variable or provider profile CC_BRIDGE can refer
  to after they store the credential outside `cc-bridge_self`.

## Interrupted Work Chain

Symptoms:

- `CC_BRIDGE_REPLY` was incomplete;
- artifact reply exists and must be read before acting;
- callback did not continue;
- an ask needs retry or resubmit.

Flow:

1. Use trace to reconstruct job, message, attempt, reply, artifact, and
   callback lineage.
2. Read artifact-backed replies when present before acting.
3. Use `repair retry` when the same job attempt should be retried.
4. Use `repair resubmit` when the work should be submitted as a fresh job
   because the original lineage is no longer appropriate.
5. Use `repair ack` only when acknowledgement state is wrong and the reply is
   otherwise accepted.
6. Resume through the original target agent unless the user intentionally
   retargets the work.

## Communication Reply Stalled

Symptoms:

- the user says a CC_BRIDGE reply did not arrive;
- an agent remains `busy`/`delivering` with later work queued behind it;
- a reply is `cancelled` or `incomplete`;
- an artifact-backed reply is empty or unreadable;
- the mailbox looks stuck even though the provider pane appears alive.

Flow:

1. Use `cc-bridge-comm-reply-recover` as the incident-level runbook.
2. Reconstruct lineage with `cc-bridge trace <id>` before making any repair.
3. Inspect `cc-bridge queue --detail <agent>` and
   `cc-bridge pend --inbox --detail <agent>` to find the active head-of-line event.
4. If a queued job is blocked behind an active job, trace the active job. Do
   not repair the queued job first.
5. Cross-check runtime evidence with `cc-bridge ps`, `cc-bridge ping <agent>`, and
   `cc-bridge doctor logs <agent>`. Use tmux pane capture only as read-only evidence
   from the socket and pane id reported by `cc-bridge ps`.
6. If the active job is stale or mismatched, cancel it first, then re-check
   whether the queue advances.
7. If the next job enters the provider pane and is making progress, do not
   restart the agent.
8. After a valid reply completes, cancel duplicate queued/running retries for
   the same work.
9. Hand off to `cc-bridge-self-recover` for a guarded single-agent restart only when
   chain repair has cleared active work and provider evidence still shows a
   stale, dead, or unusable pane.

## Config Drift Or Reload Needed

Symptoms:

- `.cc-bridge/cc-bridge.config` changed;
- disk config shows an agent that restart does not accept;
- sidebar does not match newly edited windows.

Flow:

1. Explain that live restart targets come from the current mounted daemon graph.
2. Use the built-in `cc-bridge-config` skill for disk config edits.
3. After every edit, validate disk config with `cc-bridge config validate`.
4. If validation passes and the user wants to materialize the change, run or
   suggest `cc-bridge reload --dry-run` to get the no-mutation reload plan.
5. Do not treat a config edit as live runtime state until the mounted daemon
   graph has reloaded and been rechecked.
6. If the dry-run reload class is supported and user intent is explicit, run
   `cc-bridge reload`. `cc-bridge_self` may perform this step itself through the built-in
   `cc-bridge-config` skill.
7. Re-check the graph after reload before attempting agent restart or repair.
   Reload confirms disk intent is accepted; it does not prove running provider
   processes or contexts have picked up the new startup inputs.
8. If the config change affects provider command, provider profile, model,
   base URL, environment, role assets, or provider startup context for an
   already running agent, plan a guarded restart of only the affected agent
   after reload. Do not restart all agents or unrelated panes.
9. If multiple agents are affected, handle them one at a time with separate
   current-graph and busy/pending checks for each target.

## Bootstrap Config Repair

Symptoms:

- `.cc-bridge/cc-bridge.config` syntax or role-binding errors prevent `cc-bridge_self` from
  mounting;
- `cc-bridge ask cc-bridge_self ...` cannot work because the role is not available;
- the user needs to recover enough config validity to start the maintenance
  role.

Flow:

1. Treat this as user-level bootstrap repair.
2. The user edits `.cc-bridge/cc-bridge.config` directly from the terminal or editor.
3. Validate with `cc-bridge config validate`.
4. If a daemon is mounted, run `cc-bridge reload --dry-run` before any mutating
   reload.
5. Once `cc-bridge_self` mounts again, return CC_BRIDGE config design/edit ownership to its
   built-in `cc-bridge-config` skill.

## `cc-bridge_self` Itself Broken

Symptoms:

- the maintenance agent pane/context is bad;
- `cc-bridge ask cc-bridge_self ...` fails;
- its built-in skills, tools, or role assets are stale.

Flow:

1. Diagnose `cc-bridge_self` from another agent or the user shell.
2. Treat it like any other non-authority configured agent.
3. Clear or restart `cc-bridge_self` through CC_BRIDGE control-plane commands when safe.
4. Do not stop or remount unrelated agents just because `cc-bridge_self` is down.
5. If catalog role assets are stale, use
   `cc-bridge roles update agentroles.cc-bridge_self`.
6. If testing or developing a local editable role source, use
   `cc-bridge roles sync <path>`.
7. After role asset repair, reload or restart only `cc-bridge_self` as needed.

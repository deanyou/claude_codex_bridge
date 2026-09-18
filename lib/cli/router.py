from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from textwrap import dedent


AuxiliaryHandler = Callable[[Sequence[str]], int]
ManagementHandler = Callable[[argparse.Namespace], int]

_MANAGEMENT_COMMANDS = {"install", "update", "version", "uninstall", "reinstall"}


def dispatch_auxiliary_command(
    argv: Sequence[str],
    *,
    droid_handler: AuxiliaryHandler,
) -> int | None:
    tokens = list(argv)
    if tokens and tokens[0] == "droid" and len(tokens) > 1 and tokens[1] in {"setup-delegation", "test-delegation"}:
        return droid_handler(tokens[1:])
    return None


def dispatch_management_command(
    argv: Sequence[str],
    *,
    install_handler: ManagementHandler,
    update_handler: ManagementHandler,
    version_handler: ManagementHandler,
    uninstall_handler: ManagementHandler,
    reinstall_handler: ManagementHandler,
) -> int | None:
    tokens = list(argv)
    if not tokens or tokens[0] not in _MANAGEMENT_COMMANDS:
        return None

    parser = _build_management_parser()
    args = parser.parse_args(tokens)
    if args.command == "install":
        return install_handler(args)
    if args.command == "update":
        return update_handler(args)
    if args.command == "version":
        return version_handler(args)
    if args.command == "uninstall":
        return uninstall_handler(args)
    if args.command == "reinstall":
        return reinstall_handler(args)
    parser.print_help()
    return 1


def parse_start_args(argv: Sequence[str]) -> argparse.Namespace:
    return build_start_parser().parse_args(list(argv))


def print_start_help(*, file=None) -> None:
    print(
        dedent(
            """
            usage: cc_bridge [-s] [-n]

            Primary workflow:
              cc_bridge                  Start project agents from `.cc-bridge/cc_bridge.config`.
              cc_bridge -s               Safe start. Disable CLI auto-permission override.
              cc_bridge -n               Rebuild runtime state while preserving config and managed agent history.
              cc_bridge clear [agent...]  Send provider-native /clear to managed agent panes.
              cc_bridge compact [agent...] Compact context in managed agent panes using each provider's native command.
              cc_bridge restart <agent> Restart one idle configured agent pane through cc_bridge_daemon.
              cc_bridge reload            Apply a safe additive config reload, or reject with diagnostics.
              cc_bridge reload --dry-run  Validate and plan config reload without mutation.
              cc_bridge config ui        Open the local project configuration panel.
              cc_bridge maintenance status Show maintenance heartbeat config and stored status.
              cc_bridge maintenance tick   Run one maintenance heartbeat diagnosis tick.
              cc_bridge mobile serve       Start the CC_BRIDGE Mobile gateway for the current project.
              cc_bridge mobile devices     List paired mobile devices for the current project.
              cc_bridge mobile revoke <id> Revoke one paired mobile device locally.
              cc_bridge agent add NAME:PROVIDER --role ROLE [--window NAME|--window-class CLASS] --hidden --json
                                    Hot-load one runtime dynamic agent without rewriting cc_bridge.config.
              cc_bridge agent remove NAME|--agents a,b --policy park|unload --json
                                    Park or unload runtime dynamic agents.
              cc_bridge agent park NAME|--agents a,b --json
                                    Disable dispatch for dynamic agents while preserving panes.
              cc_bridge agent resume NAME|--agents a,b --json
                                    Re-enable dispatch for parked dynamic agents.
              cc_bridge agent release NAME --idle-only --json
                                    Safely release one dynamic agent through role policy.
              cc_bridge loop capacity ensure --loop-id ID --profile worker=1 --profile code_reviewer=1 --json
                                    Plan dynamic loop workers from configured loop.role_profiles.
              cc_bridge loop topology propose|commit|reconcile|status|release --loop-id ID --json
                                    Manage runtime workflow graph desired/observed topology.
              cc_bridge loop run-once --loop-id ID --task TEXT --json
                                    Run one worker/reviewer/orchestrator/round-checker round and write loop artifacts.
              cc_bridge kill             Stop the current project's background runtime.
              cc_bridge kill -f          Force cleanup project-owned runtime residue.
              cc_bridge cleanup          Prune safe provider rebuildable caches after cc_bridge_daemon is stopped.
              cc_bridge cleanup --legacy-provider-caches
                                    Also remove caches for project roots that no longer exist.
              cc_bridge theme [system|dark|light|+|-|PRESET]
                                    Set or show the global CC_BRIDGE UI theme.

            Core commands:
              cc_bridge ask <agent> [from <sender>] <message>
              cc_bridge followup <job_id> --message <text>
              cc_bridge doctor

            Diagnostics-only control-plane status:
              cc_bridge ping <agent|cc_bridge_daemon>

            Diagnostics-only observer:
              cc_bridge pend <agent|job_id> [N]
              cc_bridge pend --watch <agent|job_id>
              cc_bridge pend --inbox [--detail] <agent>
              cc_bridge pend --queue [--detail] <agent|all>

            Advanced views:
              cc_bridge queue [--detail] <agent|all>
              cc_bridge trace <id>

            Advanced recovery:
              cc_bridge repair <ack|retry|resubmit> ...

            Management:
              cc_bridge install mobile    Start the server-wide CC_BRIDGE Mobile gateway and pairing QR.
              cc_bridge version | cc_bridge update [rich|mobile|VERSION] [--providers prompt|check|all|none] [--no-cache-cleanup]
                          | cc_bridge uninstall [rich] | cc_bridge reinstall

            Tools:
              cc_bridge rich
              cc_bridge rich uninstall
              cc_bridge update rich
              cc_bridge update mobile

            Roles:
              cc_bridge roles list
              cc_bridge roles install agentroles.cc_bridge_self
              cc_bridge roles update agentroles.cc_bridge_self
              cc_bridge roles add agentroles.cc_bridge_self:codex
              cc_bridge roles install agentroles.archi
              cc_bridge roles update agentroles.archi
              cc_bridge roles sync [path]
              cc_bridge roles add agentroles.archi:codex
              cc_bridge roles doctor agentroles.archi
            """
        ).strip(),
        file=file,
    )


def print_kill_help(*, file=None) -> None:
    print(
        dedent(
            """
            usage: cc_bridge kill [-f]

            Project runtime cleanup:
              cc_bridge kill     Stop the current project's cc_bridge_daemon, agents, and tmux namespace.
              cc_bridge kill -f  Force cleanup project-owned runtime residue before `cc_bridge -n`.

            Notes:
              - `kill` is project-scoped. It does not bootstrap a missing `.cc-bridge`.
              - `kill` still works when `.cc-bridge` exists but `cc_bridge.config` is missing or stale.
              - Use `cc_bridge -n` after `cc_bridge kill` when you want to rebuild runtime state but keep config and managed agent history.
            """
        ).strip(),
        file=file,
    )


def print_command_help(command_name: str, *, file=None) -> bool:
    text = _COMMAND_HELP.get(command_name)
    if text is None:
        return False
    print(dedent(text).strip(), file=file)
    return True


_COMMAND_HELP = {
    "ping": """
        usage: cc_bridge ping <agent|all|cc_bridge_daemon>

        Diagnostics-only control-plane status:
          cc_bridge ping <agent>   Show cached runtime status for one named agent.
          cc_bridge ping all       Show cached mounted-agent status across the project.
          cc_bridge ping cc_bridge_daemon      Show cached project daemon status.
    """,
    "pend": """
        usage: cc_bridge pend [--watch|--inbox|--queue] [--detail] <agent|job_id|all> [N]

        Diagnostics-only weak observer surface:
          These commands are not part of normal ask workflows.
          Primary weak observer entrypoint:
            cc_bridge pend <agent>                    Show a non-authoritative observer snapshot for one agent.
            cc_bridge pend <job_id>                   Show a non-authoritative observer snapshot for one submitted job.
            cc_bridge pend --watch <agent|job_id>     Stream non-authoritative observer events via the converged observer entrypoint.
            cc_bridge pend --inbox <agent>            Show a non-authoritative inbox summary via the converged observer entrypoint.
            cc_bridge pend --inbox --detail <agent>   Expand inbox-item detail via the converged observer entrypoint.
            cc_bridge pend --queue <agent|all>        Show the same non-authoritative backlog summary exposed by `cc_bridge queue`.
            cc_bridge pend --queue --detail <agent>   Expand queued-event detail through the observer entrypoint.
            cc_bridge pend <target> N                 Show the latest N observer snapshot items.
          Use `cc_bridge trace <id>` for lineage when needed.
    """,
    "watch": """
        usage: cc_bridge watch <agent|job_id>

        Diagnostics-only weak observer compatibility entrypoint:
          cc_bridge watch <agent>   Stream non-authoritative observer events for one agent.
          cc_bridge watch <job_id>  Stream non-authoritative observer events for one job until terminal completion or timeout.
          This is not part of normal ask workflows.
          Prefer `cc_bridge pend --watch <agent|job_id>` as the converged observer entrypoint.
          Do not treat non-terminal watch output as authoritative completion.
          Use `cc_bridge trace <id>` for lineage when needed.
    """,
    "queue": """
        usage: cc_bridge queue [--detail] <agent_name|all>

        Advanced backlog view:
          cc_bridge queue <agent_name>            Show a non-authoritative observer summary for one agent.
          cc_bridge queue --detail <agent_name>   Expand queued-event details for one agent.
          cc_bridge queue all                     Show non-authoritative observer backlog state across the project.
          `cc_bridge pend --queue [--detail] <agent|all>` remains the equivalent weak-observer form.
          Use `cc_bridge trace <id>` for lineage when needed.
    """,
    "trace": """
        usage: cc_bridge trace <submission_id|message_id|attempt_id|reply_id|job_id>

        Advanced lineage view:
          cc_bridge trace <id>   Show the full job/message/reply lineage for one id.
    """,
    "followup": """
        usage: cc_bridge followup <job_id> --message <text>

        Exact active-job correction:
          Targets one running job and its exact provider turn.
          Unsupported or stale provider transports fail closed and do not
          create a queued job, send pane keys, substitute providers, or retry.
    """,
    "theme": """
        usage: cc_bridge theme [system|dark|light|+|-|solarized|tokyo|gruvbox|rose-pine]

        CC_BRIDGE UI theme:
          cc_bridge theme          Show current CC_BRIDGE theme preference.
          cc_bridge theme +        Switch to the next CC_BRIDGE theme.
          cc_bridge theme -        Switch to the previous CC_BRIDGE theme.
          cc_bridge theme system   Follow the operating-system light/dark appearance.
          cc_bridge theme light    Use a light CC_BRIDGE tmux/sidebar theme.
          cc_bridge theme dark     Use the dark CC_BRIDGE tmux/sidebar theme.

        Notes:
          - Ordinary terminals keep their own terminal theme; CC_BRIDGE only updates
            CC_BRIDGE-owned tmux/sidebar colors.
          - CC_BRIDGE-owned rich WezTerm follows this preference through its
            generated config.
          - The same preference is available under Appearance in `cc_bridge config ui`.
    """,
    "agent": """
        usage:
          cc_bridge agent status [--class CLASS] [--json]
          cc_bridge agent show <agent> [--json]
          cc_bridge agent add <name[:provider]> (--profile PROFILE | --role ROLE) [--window NAME|--window-class CLASS] [--hidden|--visible|--parked] [--json]
          cc_bridge agent move <agent>|--agents a,b (--window NAME|--window-class CLASS|--loop-id LOOP --node-id NODE) [--json]
          cc_bridge agent hide <agent>|--agents a,b [--json]
          cc_bridge agent park <agent>|--agents a,b [--json]
          cc_bridge agent resume <agent>|--agents a,b [--visible|--hidden] [--json]
          cc_bridge agent remove <agent>|--agents a,b [--policy auto|hide|park|unload|kill] [--idle-only] [--force --reason TEXT] [--json]
          cc_bridge agent release <agent>|--agents a,b [--policy auto|hide|park|unload] [--idle-only] [--reason TEXT] [--json]

        Dynamic agent lifecycle:
          cc_bridge agent add helper:codex --role agentroles.general --hidden --json
              Write a runtime lifecycle record and project the agent into the active config overlay.
          cc_bridge agent add reviewer --profile code_reviewer --hidden --json
              Add from [loop.role_profiles.<profile>] in cc_bridge.config.
          cc_bridge agent add planner2:codex --role agentroles.planner --window-class plan-orchestrate --hidden --json
              Hot-load into an existing class window or create that window through reload.
          cc_bridge agent add worker1:codex --profile worker --loop-id round1 --node-id node1 --hidden --json
              Place execution agents in node-<loop-id>-<node-id> windows.
          cc_bridge agent move planner2 --window review --json
              Move a dynamic session agent to an existing target window when mounted.
          cc_bridge agent move --agents worker1,checker1 --window archive --json
          cc_bridge agent move --agents worker1,checker1 --window-class execution-node --json
              Move multiple dynamic session agents through one reload transaction.
          cc_bridge agent park planner2 --json
              Keep the pane and context but reject new dispatches until resumed.
          cc_bridge agent park --agents planner2,broker1 --json
              Park a long-lived group through one config-only reload transaction.
          cc_bridge agent resume planner2 --hidden --json
              Re-enable dispatch without changing pane ownership.
          cc_bridge agent resume --agents planner2,broker1 --hidden --json
              Resume a parked group while preserving pane ownership.
          cc_bridge agent remove helper --policy park --json
              Keep long-lived context discoverable while removing it from visible active work.
          cc_bridge agent remove helper --policy unload --idle-only --json
              Remove the dynamic overlay when the agent is idle.
          cc_bridge agent remove --agents worker1,checker1 --policy unload --idle-only --json
              Unload a dynamic worker/checker group through one reload transaction.
          cc_bridge agent release reviewer --idle-only --json
              Apply role policy without exposing the destructive kill path.
          cc_bridge agent release --agents worker1,checker1 --idle-only --json
              Apply role policies to a dynamic group as one all-or-nothing lifecycle update.
          cc_bridge agent remove helper --policy kill --force --reason "operator reset" --json
              Force destructive removal; requires an explicit reason.
    """,
    "inbox": """
        usage: cc_bridge inbox [--detail] <agent_name>

        Weak observer compatibility entrypoint:
          cc_bridge inbox <agent_name>            Show a non-authoritative observer summary for one agent.
          cc_bridge inbox --detail <agent_name>   Expand inbox-item detail for one agent.
          Prefer `cc_bridge pend --inbox [--detail] <agent>` as the converged observer entrypoint.
          Use `cc_bridge trace <id>` for lineage when needed.
    """,
    "logs": """
        usage: cc_bridge logs <agent>

        Runtime diagnostics compatibility view:
          cc_bridge logs <agent>   Tail the current runtime/session log for one agent.
          Prefer `cc_bridge doctor logs <agent>` as the converged diagnostics entrypoint.
    """,
    "doctor-logs": """
        usage: cc_bridge doctor logs <agent>

        Runtime log diagnostics subview:
          cc_bridge doctor logs <agent>   Tail the current runtime/session log for one agent through the primary diagnostics entrypoint.
          `cc_bridge logs <agent>` remains a compatibility alias.
    """,
    "ps": """
        usage: cc_bridge ps

        Runtime diagnostics compatibility view:
          cc_bridge ps   Show known runtime/session/workspace bindings.
          Prefer `cc_bridge doctor ps` as the converged diagnostics entrypoint.
    """,
    "doctor-ps": """
        usage: cc_bridge doctor ps

        Runtime diagnostics subview:
          cc_bridge doctor ps   Show known runtime/session/workspace bindings through the primary diagnostics entrypoint.
          `cc_bridge ps` remains a compatibility alias.
    """,
    "doctor-storage": """
        usage: cc_bridge doctor storage [--json]

        Storage diagnostics subview:
          cc_bridge doctor storage        Show .cc-bridge storage class totals and largest entries.
          cc_bridge doctor storage --json Emit full storage classification payload.
    """,
    "cleanup": """
        usage: cc_bridge cleanup [--legacy-provider-caches]

        Storage cleanup:
          cc_bridge cleanup   Prune safe rebuildable caches for the stopped current project.
          cc_bridge cleanup --legacy-provider-caches
                        Also remove legacy provider caches whose recorded project roots no longer exist.

        Safety:
          - Refuses to run while cc_bridge_daemon is active or ask jobs are pending/running.
          - Detaches only CC_BRIDGE-owned legacy Claude cache links.
          - Cross-project cleanup requires the explicit legacy cache flag and a valid CC_BRIDGE manifest.
          - Does not remove provider sessions, auth, plugin bundles, mailbox data, or runtime authority.
          - Use `cc_bridge doctor storage` before cleanup to inspect storage classes.
    """,
    "clear": """
        usage: cc_bridge clear [agent_name|all]...

        Agent context reset:
          cc_bridge clear             Send /clear to every configured mounted agent pane.
          cc_bridge clear agent1      Send /clear to one agent pane.
          cc_bridge clear agent1 agent2
                                Send /clear to multiple agent panes.

        Notes:
          - This sends the provider-native /clear command into each pane.
          - It does not delete .cc-bridge state, workspaces, auth, sessions, or logs.
          - Use `cc_bridge kill` or the sidebar restart control when you need process restart.
    """,
    "compact": """
        usage: cc_bridge compact [agent_name|all]...

        Agent context compaction:
          cc_bridge compact             Compact every configured mounted agent pane.
          cc_bridge compact agent1      Compact one agent pane.
          cc_bridge compact agent1 agent2
                                  Compact multiple agent panes.

        Notes:
          - This sends the provider-native context compaction command.
          - It does not delete .cc-bridge state, workspaces, auth, sessions, or logs.
          - Providers without a verified native compaction command are reported as unsupported.
    """,
    "restart": """
        usage: cc_bridge restart <agent_name>

        Guarded single-agent runtime restart:
          cc_bridge restart agent1   Restart one configured mounted agent pane through cc_bridge_daemon.

        Safety:
          - Target authority comes from the current mounted daemon graph.
          - Refuses when the agent is busy, queued, delivering a reply, or waiting on result-chain continuation.
          - Does not support `restart all`, window-level restart, or raw tmux mutation.
    """,
    "maintenance": """
        usage: cc_bridge maintenance <status|tick|schedule>

        Maintenance heartbeat diagnostics:
          cc_bridge maintenance status   Show configured heartbeat policy plus stored schedule/status state.
          cc_bridge maintenance tick     Run one diagnosis tick, update heartbeat status/schedule when enabled.
          cc_bridge maintenance schedule --after 5m [--reason TEXT]
                                   Schedule the next heartbeat follow-up.

        Safety:
          - tick reads cc_bridge_daemon/project-view evidence and may write only maintenance-heartbeat status/schedule/activation records.
          - non-healthy tick may submit one silent ask to the configured assessor, default cc_bridge_self.
          - tick does not run repairs or start providers.
          - runner is an internal project-scoped schedule consumer used by startup ensure.
          - enable and disable are config-authority in v1; edit [maintenance.heartbeat].enabled.
          - Status reads `.cc-bridge/cc_bridge_daemon/maintenance-heartbeat/`, not `.cc-bridge/cc_bridge_daemon/heartbeats/`.
    """,
    "mobile": """
        usage: cc_bridge mobile <serve|devices|revoke>

        CC_BRIDGE Mobile gateway:
          cc_bridge mobile serve
              Start the current-project HTTP gateway on loopback by default
              and emit a short-lived pairing code.
          cc_bridge mobile serve --listen 127.0.0.1:0
              Start on a dynamic loopback port.
          cc_bridge mobile serve --listen 192.168.31.155:8787 --route-provider lan
              Bind one specific private interface for direct LAN access and
              infer the pairing URL from the listen address.
          cc_bridge mobile serve --listen 127.0.0.1:8787 --public-url https://mobile.example.com --route-provider cloudflare_tunnel
              Keep the gateway loopback-bound but emit Cloudflare route
              metadata in the pairing payload.
          cc_bridge mobile devices
              List paired devices from the current project's local mobile
              state.
          cc_bridge mobile revoke dev_1234
              Revoke a paired device locally, without exposing a public admin
              route.

        Endpoints:
          GET /v1/health
          GET /v1/projects
          GET /v1/mobile/notifications  Server-sent task completion notifications
          GET /v1/projects/{project_id}/view
          POST /v1/pairing/claim
          GET /v1/devices/me
          POST /v1/devices/{device_id}/revoke
          POST /v1/projects/{project_id}/lifecycle
          POST /v1/projects/{project_id}/focus-agent
          POST /v1/projects/{project_id}/focus-window
          POST /v1/projects/{project_id}/terminals
          GET /v1/terminals/{terminal_id}  WebSocket terminal frames

        Safety:
          - The gateway still only accepts loopback listen addresses.
          - --public-url changes pairing metadata only; it does not bind a
            public listener.
          - Device listing and host-side revocation are local CLI actions,
            not public HTTP endpoints.
          - Revoking a device also revokes its still-open terminal handles.
          - It exposes current-project data only.
          - Pairing and device tokens are hashed under `.cc-bridge/cc_bridge_daemon/mobile`.
          - Lifecycle stop requests go through cc_bridge_daemon `stop-all`, not raw tmux.
          - Lifecycle routes require a valid device token with `lifecycle` scope.
          - Focus routes require a valid device token with `focus` scope.
          - Notification streams require a valid device token with `notify`
            scope and publish low-sensitivity task completion metadata only.
          - Terminal-open routes require `terminal_input` scope and mint
            short-lived terminal tokens.
          - Terminal WebSocket streams validate terminal tokens and monotonic
            input sequence numbers before forwarding input to a tmux attach
            client.
          - It does not configure Cloudflare Tunnel, lifecycle, or
            multi-project registry.
          - Stopping the gateway does not stop cc_bridge_daemon, provider panes, or tmux.
    """,
    "relay": """
        usage: cc_bridge relay <invite|host> <issue|activate|status|list|revoke>

        Host activation:
          cc_bridge relay host activate --mode official --invitation-file /path/to/one-time-invitation
              Use the CC_BRIDGE Official Relay. Request one one-time invitation from
              the CC_BRIDGE Relay operator; the invitation is consumed on success.
          cc_bridge relay host activate --mode self-hosted --relay-origin wss://relay.example.com --invitation-file /path/to/one-time-invitation
              Use an operator-managed Relay with a trusted TLS endpoint.
          Omitting --mode preserves compatibility: an explicit --relay-origin
          selects self-hosted mode; otherwise official mode is selected.

        CC_BRIDGE hosted relay operator-local admission:
          cc_bridge relay invite issue --db /path/to/relay-admission.sqlite3 --secrets /path/to/relay-secrets.json --ttl-seconds 900 --json
              Create one one-time host invitation. This is the only command
              that prints the raw invitation, exactly once, to explicit
              operator output.
          cc_bridge relay invite status --db /path/to/relay-admission.sqlite3 --secrets /path/to/relay-secrets.json <invite_id> [--json]
          cc_bridge relay invite list --db /path/to/relay-admission.sqlite3 --secrets /path/to/relay-secrets.json [--json]
          cc_bridge relay invite revoke --db /path/to/relay-admission.sqlite3 --secrets /path/to/relay-secrets.json <invite_id> [--reason TEXT] [--json]
          cc_bridge relay host status --db /path/to/relay-admission.sqlite3 --secrets /path/to/relay-secrets.json <host_id> [--json]
          cc_bridge relay host list --db /path/to/relay-admission.sqlite3 --secrets /path/to/relay-secrets.json [--json]
          cc_bridge relay host revoke --db /path/to/relay-admission.sqlite3 --secrets /path/to/relay-secrets.json <host_id> [--reason TEXT] [--json]

        Safety:
          - This is not a public HTTP/admin route.
          - Raw invitation secrets are not stored in logs, audit records, or
            the SQLite admission database.
          - Admission HMAC keys must come from --secrets,
            CC_BRIDGE_RELAY_ADMISSION_SECRETS, or both
            CC_BRIDGE_RELAY_VERIFIER_KEY_B64 and CC_BRIDGE_RELAY_CAPABILITY_KEY_B64; the
            same key material is required after restart.
          - Status/list/revoke output is redacted and never prints an
            invitation value.
    """,
    "loop": """
        usage:
          cc_bridge loop capacity <ensure|status|release> ...
          cc_bridge loop run-once --loop-id ID --task TEXT [--json]

        Loop capacity:
          cc_bridge loop capacity ensure --loop-id round1 --profile worker=1 --profile code_reviewer=1 --json
              Write a deterministic dynamic-node plan from configured loop.role_profiles.
          cc_bridge loop capacity status --loop-id round1 --json
              Read the stored loop capacity plan.
          cc_bridge loop capacity release --loop-id round1 --policy auto --json
              Release idle loop-owned dynamic nodes and retain busy nodes.

        One-round execution:
          cc_bridge loop run-once --loop-id round1 --task "Implement task" --json
              Ensure one worker and one code_reviewer, submit work, collect review,
              ask orchestrator for aggregation, release idle dynamic nodes, and
              write `.cc-bridge/runtime/loops/<loop-id>/` artifacts.
    """,
    "doctor": """
        usage: cc_bridge doctor [ps|logs <agent>|storage] [--output [PATH]]

        Deep diagnostics:
          cc_bridge doctor               Print project diagnostic summary.
          cc_bridge doctor ps            Show the runtime/session/workspace diagnostics subview.
          cc_bridge doctor logs <agent>  Tail the runtime/session log diagnostics subview for one agent.
          cc_bridge doctor storage       Show .cc-bridge storage class totals.
          cc_bridge doctor --output      Export a support bundle to the default path.
          cc_bridge doctor --output PATH Export a support bundle to PATH.
          `cc_bridge ps` and `cc_bridge logs <agent>` remain compatibility entrypoints.
    """,
    "cancel": """
        usage: cc_bridge cancel <job_id>

        Job control view:
          cc_bridge cancel <job_id>   Request cancellation for one submitted job.
    """,
    "ack": """
        usage: cc_bridge ack <agent_name> [inbound_event_id]

        Advanced recovery compatibility entrypoint:
          cc_bridge ack <agent_name> [inbound_event_id]   Acknowledge reply/inbox progress for one agent.
          Prefer `cc_bridge repair ack <agent_name> [inbound_event_id]` as the converged recovery entrypoint.
    """,
    "repair-ack": """
        usage: cc_bridge repair ack <agent_name> [inbound_event_id]

        Advanced recovery subcommand:
          cc_bridge repair ack <agent_name> [inbound_event_id]   Acknowledge reply/inbox progress for one agent.
          `cc_bridge ack <agent_name> [inbound_event_id]` remains a compatibility alias.
    """,
    "retry": """
        usage: cc_bridge retry <job_id|attempt_id>

        Advanced recovery compatibility entrypoint:
          cc_bridge retry <job_id|attempt_id>   Retry one failed or incomplete job/attempt lineage.
          Prefer `cc_bridge repair retry <job_id|attempt_id>` as the converged recovery entrypoint.
    """,
    "repair-retry": """
        usage: cc_bridge repair retry <job_id|attempt_id>

        Advanced recovery subcommand:
          cc_bridge repair retry <job_id|attempt_id>   Retry one failed or incomplete job/attempt lineage.
          `cc_bridge retry <job_id|attempt_id>` remains a compatibility alias.
    """,
    "resubmit": """
        usage: cc_bridge resubmit <message_id>

        Advanced recovery compatibility entrypoint:
          cc_bridge resubmit <message_id>   Create a fresh submission from one prior message lineage.
          Prefer `cc_bridge repair resubmit <message_id>` as the converged recovery entrypoint.
    """,
    "repair-resubmit": """
        usage: cc_bridge repair resubmit <message_id>

        Advanced recovery subcommand:
          cc_bridge repair resubmit <message_id>   Create a fresh submission from one prior message lineage.
          `cc_bridge resubmit <message_id>` remains a compatibility alias.
    """,
    "repair": """
        usage: cc_bridge repair <ack|retry|resubmit> ...

        Advanced recovery:
          cc_bridge repair ack <agent_name> [inbound_event_id]   Acknowledge reply/inbox progress for one agent.
          cc_bridge repair retry <job_id|attempt_id>             Retry one failed or incomplete job/attempt lineage.
          cc_bridge repair resubmit <message_id>                 Create a fresh submission from one prior message lineage.
          Legacy `ack` / `retry` / `resubmit` commands remain compatibility entrypoints.
    """,
    "config": """
        usage: cc_bridge config <validate|effective|migrate|approve-commands|ui> ...

        Config:
          cc_bridge config validate [--json]                 Validate `.cc-bridge/cc_bridge.config` for the current project.
          cc_bridge config effective --json                  Show sanitized effective config authority.
          cc_bridge config approve-commands                  Review and approve project command fields.
          cc_bridge config migrate --to 3 --dry-run [--json] Preview V2-to-V3 mappings without writing.
          cc_bridge config ui         Open the local-only project configuration panel.
          cc_bridge config ui --no-open [--port PORT]
                                Serve the panel without opening a browser.
    """,
    "reload": """
        usage: cc_bridge reload [--dry-run]

        Reload:
          cc_bridge reload             Apply safe explicit changes: view-only, append-only add_agent/add_window, idle remove_agent, or idle same-slot replace_agent.
          cc_bridge reload --dry-run   Ask the mounted daemon to validate `.cc-bridge/cc_bridge.config` and return a no-mutation reload plan.

        Explicit reload boundary:
          - Busy remove_agent and replace_agent record bounded drain state and stop before mutation.
          - move_agent and arbitrary layout changes are rejected unless routed through guarded agent move commands.
          - No config watch is started; full arbitrary kill/reflow of existing panes is not implemented.
          - Non-dry-run output includes stage, plan_class, graph version, diagnostics, and any residue.
    """,
    "tools": """
        usage: cc_bridge tools <doctor|install|update|enable|disable|launch|uninstall> workbench [--profile rich]

        Managed tool provisioning:
          cc_bridge update rich                               Install/update and enable the rich workbench bundle.
          cc_bridge uninstall rich                            Remove the rich workbench and return normal `cc_bridge` startup.
          cc_bridge rich                                      Launch the installed rich workbench.
          cc_bridge rich uninstall                            Remove the rich workbench and return normal `cc_bridge` startup.
          cc_bridge tools doctor workbench --profile rich     Inspect the CC_BRIDGE-owned rich workbench bundle.
          cc_bridge tools install workbench --profile rich    Generate isolated WezTerm/Yazi/Markdown config.
          cc_bridge tools enable workbench --profile rich     Mark the bundle enabled for CC_BRIDGE-owned tool usage.
          cc_bridge tools launch workbench --profile rich     Launch the generated workbench wrapper.
          cc_bridge tools launch workbench --dry-run          Print launch commands without starting a terminal.
          cc_bridge tools disable workbench                  Disable and close recorded CC_BRIDGE-owned workbench surfaces.
          cc_bridge tools uninstall workbench                Remove generated workbench config and wrappers.
    """,
    "roles": """
        usage: cc_bridge roles <list|show|install|update|sync|add|doctor> ...

        Role Pack management:
          cc_bridge roles list
          cc_bridge roles show agentroles.cc_bridge_self
          cc_bridge roles install agentroles.cc_bridge_self
          cc_bridge roles update agentroles.cc_bridge_self
          cc_bridge roles add agentroles.cc_bridge_self:codex
          cc_bridge roles show agentroles.archi
          cc_bridge roles install agentroles.archi
          cc_bridge roles update agentroles.archi
          cc_bridge roles sync [path]
          cc_bridge roles add agentroles.archi:codex
          cc_bridge roles doctor agentroles.archi
    """,
}


def _build_management_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cc_bridge", description="Claude AI unified launcher", add_help=True)
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    install_parser = subparsers.add_parser("install", help="Install or activate optional CC_BRIDGE capabilities")
    install_parser.add_argument("target", nargs="?", help="'mobile' to start the server-wide CC_BRIDGE Mobile gateway")
    install_parser.add_argument(
        "--listen",
        default="127.0.0.1:8787",
        help="HOST:PORT; route-provider lan also accepts a specific private interface IP",
    )
    install_parser.add_argument("--public-url", default=None)
    install_parser.add_argument(
        "--route-provider",
        default="lan",
        choices=("lan", "tailnet", "cloudflare_tunnel", "relay"),
    )

    update_parser = subparsers.add_parser("update", help="Update CC_BRIDGE or an optional bundle")
    update_parser.add_argument("target", nargs="?", help="version like '4', '4.1', '4.1.3', or optional bundle 'rich'/'mobile'")
    update_parser.add_argument("--listen", default=None)
    update_parser.add_argument("--public-url", default=None)
    update_parser.add_argument(
        "--route-provider",
        default=None,
        choices=("lan", "tailnet", "cloudflare_tunnel", "relay"),
        help=(
            "mobile route; omit in an interactive terminal to choose Tailscale, "
            "LAN, official Relay, or self-hosted Relay"
        ),
    )
    update_parser.add_argument(
        "--providers",
        choices=("prompt", "check", "all", "none"),
        default=None,
        help="provider CLI handling after the CC_BRIDGE update (default: prompt on a TTY)",
    )
    update_parser.add_argument(
        "--no-cache-cleanup",
        "--no-cleanup",
        dest="cache_cleanup",
        action="store_false",
        default=True,
        help="skip the safe post-update migration of retired project Provider caches",
    )

    subparsers.add_parser("version", help="Show version and check for updates")
    uninstall_parser = subparsers.add_parser("uninstall", help="Uninstall cc_bridge, or uninstall the optional rich bundle")
    uninstall_parser.add_argument("target", nargs="?", help="'rich' to uninstall only the optional rich bundle")
    subparsers.add_parser("reinstall", help="Reinstall cc_bridge and refresh configs")
    return parser


def build_start_parser() -> argparse.ArgumentParser:
    start_parser = argparse.ArgumentParser(
        prog="cc_bridge",
        description="Claude AI unified launcher",
        add_help=False,
    )
    start_parser.add_argument("-s", "--safe", action="store_true", default=False, help=argparse.SUPPRESS)
    start_parser.add_argument(
        "-n",
        "--new-context",
        dest="new_context",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return start_parser

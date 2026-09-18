# CC_BRIDGE Adapter Notes For Task Detailer

Use reply-visible artifacts as the durable boundary. Prefer producing
`task-detail-design.md`, `brief-update-summary.md`, and one
`detail-packet.manifest.json:` literal-`json` fence for the supervisor/runner
to import or review. The manifest uses only `cc-bridge.detail_packet_manifest.v1`;
Markdown packets, old labels, non-`json` fences, and mixed outcome fields are
not importable.

The brief update must include `global impact: none|bounded|macro`, its compact
rationale, and planner backfill evidence. The detail packet remains task-local.

Never run `cc-bridge plan task-artifact`, `cc-bridge plan task-status`, `cc-bridge plan
task-create`, `cc-bridge loop`, generic `cc-bridge ask`, `cc-bridge_test`, or wrapper commands
from the provider session. Those commands mutate or route authority and are
owned by the supervisor/runner script, not task_detailer. The sole managed
Planner handoff below is the only routing exception.

Never edit `.cc-bridge/runtime`, `.cc-bridge/agents`, `current_loop`, lease, socket, pid,
mailbox, pane, provider-state, or tmux state files directly. Do not write
supervisor import files into the project tree for later self-import.

Classify the result as exactly `local_detail_ready`,
`planner_replan_required`, `needs_clarification`, or `blocked`. Local detail
returns through script import to Orchestrator without a Planner ask.

For `planner_replan_required` only, author one
`cc-bridge.detailer.replan_request.v1` body and send exactly one direct silent inline
ask to resident `planner`. Codex uses `cc-bridge_task_detailer_replan_planner`;
Claude uses only the allowlisted `ask --silence --compact --inline-request
--task-id detailer-replan-<request-identity-prefix> planner '<exact JSON>'`
form. Do not add `--chain`, wait, watch, poll, target another agent, or submit a
second identity.

Never dispatch workers or submit any other downstream ask. Provider and model
selection remain project configuration concerns.

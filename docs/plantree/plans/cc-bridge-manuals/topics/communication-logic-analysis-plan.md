# Communication Logic Analysis Plan

Date: 2026-06-10

## Goal

Produce the developer manual's communication chapter from source-backed flow
analysis, not from command names alone.

## Core Questions

1. What happens when a user or agent submits `/ask <target> <message>`?
2. How does the CLI parse route syntax and map flags to request payloads?
3. What does cc-bridge-daemon persist as message, job, attempt, reply, callback edge, and
   artifact state?
4. How does the dispatcher choose when to run a provider-backed attempt?
5. How does CC_BRIDGE detect provider completion across Codex, Claude, Gemini, and
   OpenCode?
6. How are callback continuations submitted and linked back to the parent task?
7. How do `watch`, `pend`, `queue`, `inbox`, `ack`, `trace`, `retry`,
   `resubmit`, and `cancel` read or mutate the same state?
8. What failures are terminal, retryable, degraded, or merely observable?

## Source Entry Points

CLI parsing and submission:

- `lib/cli/parser.py`
- `lib/cli/parser_runtime/ask.py`
- `lib/cli/parser_runtime/commands.py`
- `lib/cli/services/ask.py`
- `lib/cli/services/ask_runtime/`
- `lib/cli/services/watch.py`
- `lib/cli/services/wait_runtime/`
- `lib/cli/services/queue.py`
- `lib/cli/services/inbox.py`
- `lib/cli/services/ack.py`
- `lib/cli/services/trace.py`
- `lib/cli/services/retry.py`
- `lib/cli/services/resubmit.py`
- `lib/cli/services/cancel.py`

Daemon handlers and API models:

- `lib/cc-bridge-daemon/api_models.py`
- `lib/cc-bridge-daemon/api_models_runtime/`
- `lib/cc-bridge-daemon/app_runtime/handlers.py`
- `lib/cc-bridge-daemon/handlers/submit.py`
- `lib/cc-bridge-daemon/handlers/watch.py`
- `lib/cc-bridge-daemon/handlers/queue.py`
- `lib/cc-bridge-daemon/handlers/inbox.py`
- `lib/cc-bridge-daemon/handlers/ack.py`
- `lib/cc-bridge-daemon/handlers/trace.py`
- `lib/cc-bridge-daemon/handlers/retry.py`
- `lib/cc-bridge-daemon/handlers/resubmit.py`
- `lib/cc-bridge-daemon/handlers/cancel.py`

Mailbox, queue, trace, callback, and artifacts:

- `lib/mailbox_kernel/`
- `lib/mailbox_runtime/`
- `lib/message_bureau/`
- `lib/message_bureau/control_queue.py`
- `lib/message_bureau/control_queue_runtime/`
- `lib/message_bureau/control_trace_runtime/`
- `lib/message_bureau/callback_edges.py`
- `lib/provider_hooks/artifacts_runtime/`

Dispatch and provider execution:

- `lib/cc-bridge-daemon/services/dispatcher_runtime/`
- `lib/provider_execution/`
- `lib/provider_core/protocol_runtime/`
- `lib/provider_backends/*/execution_runtime/`
- `lib/provider_backends/*/comm_runtime/`
- `lib/provider_backends/opencode/runtime/`

Provider completion and reliability contracts:

- `docs/managed-provider-completion-reliability-plan.md`
- `docs/codex-session-isolation-contract.md`
- `docs/claude-session-isolation-contract.md`
- `docs/gemini-session-isolation-contract.md`
- `docs/opencode-completion-contract.md`

## Flow Diagrams Needed

1. Submit-only ask:
   CLI -> socket client -> cc-bridge-daemon submit handler -> message/job records ->
   dispatcher -> provider execution -> reply record.
2. Callback ask:
   parent job -> child message -> callback edge -> child reply -> parent
   continuation.
3. Artifact ask:
   request/reply artifact storage -> payload references -> rendering/watch
   views.
4. Watch/pend/queue:
   read-only or mostly read-only views over the same underlying message/job
   state.
5. Retry/resubmit/cancel:
   controlled mutation paths and their boundaries.

## Analysis Deliverables

- A source map table with files, classes/functions, and chapter subsection.
- A state model table for message, job, attempt, reply, callback edge, and
  artifact records.
- Sequence diagrams in LaTeX/TikZ or generated image form.
- A failure taxonomy table.
- A command-to-state-effect table for user manual reuse.

## Validation

- Compare chapter flow against `test/test_v2_ask_service.py`,
  `test/test_rolepacks.py` where roles affect ask targets, and focused mailbox
  or dispatcher tests discovered during inventory.
- Run parser/help inventory before publishing command examples.
- Use external `cc-bridge_test` only from `/home/bfly/yunwei/test_ccb2` when runtime
  examples need live evidence.


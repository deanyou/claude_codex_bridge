# CC_BRIDGE Clear Epoch Probe Design

Date: 2026-07-06

Status: design complete for planning; implementation pending. No source
behavior changed by this note.

## Purpose

Use `cc-bridge_clear` as the provider-neutral continuity boundary for CC_BRIDGE-managed
agent sessions.

Provider session formats differ:

- Codex primarily exposes JSONL session logs and request-anchor evidence.
- Claude exposes transcript/session events plus hook artifacts.
- Other providers may expose different files, hooks, panes, or storage layouts.

CC_BRIDGE should not make reply correctness depend on each provider's raw session file
shape. Raw provider sessions remain evidence, but CC_BRIDGE owns the continuity model:
agent, provider, epoch, request anchor, accepted turn, compact evidence, and
reply delivery.

## Terminology

- `cc-bridge_clear`: the managed workflow or skill behavior around clearing context,
  preserving task lineage, creating a CC_BRIDGE epoch barrier, and optionally proving
  a fresh provider session.
- `provider_epoch`: CC_BRIDGE-owned evidence interval for one agent/provider runtime.
  Completion evidence from another epoch cannot complete the current job.
- `provider_stream`: provider-specific raw evidence surface such as a Codex
  JSONL file, Claude transcript path, hook event path, provider session id, or
  another provider's equivalent.
- `post_clear_probe`: optional short internal CC_BRIDGE request sent after clear to
  bind the new epoch to a fresh provider stream and prove input/output delivery.

## Invocation Semantics

`cc-bridge_clear` should use agent-centric defaults:

- `cc-bridge_clear`: clear the current agent itself.
- `cc-bridge_clear <agent>`: clear the named peer agent.
- `cc-bridge_clear <agent1> <agent2>`: clear the named peer agents one by one.
- `cc-bridge_clear all`: explicitly clear every mounted agent in the current CC_BRIDGE
  project.

Bare `cc-bridge_clear` is self-clear. Bulk clear is only `cc-bridge_clear all`.

## Design Goal

After `cc-bridge_clear`, CC_BRIDGE should be able to answer these questions without scanning
large provider sessions as the normal path:

1. Which provider epoch is current for this agent?
2. Which provider stream belongs to that epoch?
3. Which epoch accepted this ask?
4. Did a terminal reply come from the same accepted epoch?
5. If an agent clears itself, who is responsible for proving the new session and
   resuming work?

The answer must be provider-neutral. Provider-specific parsers can populate
facts, but they should not define the global continuity semantics.

## High-Level Flow

### Clear Current Agent

Caller or control plane starts bare `cc-bridge_clear` from the current agent:

1. Resolve the current CC_BRIDGE actor to a mounted agent.
2. Run the self-clear flow below.
3. Do not expand an empty target list to all agents.

### Clear Another Agent

Caller or control plane starts `cc-bridge_clear <agent>` with an explicit target:

1. Capture a compact pre-clear snapshot:
   - agent name
   - provider
   - pane id
   - current epoch id
   - current provider stream id/path if known
   - active job ids and accepted-state summary
2. Write a CC_BRIDGE-owned epoch barrier:
   - `old_epoch_id`
   - `new_epoch_id`
   - `reason=cc-bridge_clear`
   - `created_at`
3. Resolve active jobs for the target agent:
   - no provider acceptance yet -> `incomplete(clear_before_provider_acceptance)`
   - accepted but no terminal evidence before the barrier ->
     `incomplete(clear_during_provider_turn)`
4. Submit provider-native `/clear` to the pane.
5. Send a post-clear probe in the new epoch.
6. Mark the target agent `ready` only when the probe binds fresh stream evidence
   or fails with explicit diagnostics.
7. Resume real work only after the probe result is known.

### Self-Clear

Self-clear is allowed, but it must be treated as a last action from the clearing
agent's current provider context.

The clearing agent can:

1. create or request the `cc-bridge_clear` intent;
2. write a compact resume packet if work must continue;
3. submit the clear request.

After `/clear` reaches the provider pane, the same agent should not be trusted
to continue the current turn from old provider memory. The control plane, caller,
or supervising agent owns:

- post-clear probe dispatch;
- new provider stream binding;
- resume packet replay or fresh ask;
- final reporting to the original caller.

This keeps self-clear useful without depending on the exact behavior of a
provider after it erases conversation context.

### Clear All

`cc-bridge_clear all` may exist, but only as an explicit target. It should be modeled
as repeated per-agent clear workflows, not one global provider state. Each agent
gets its own epoch barrier, probe, and diagnostics.

Bare `cc-bridge_clear` must never mean `all`.

## Post-Clear Probe

The probe is not a task. It is a continuity check.

Required properties:

- short and deterministic;
- no file edits;
- no project work;
- no user task content;
- includes one CC_BRIDGE probe anchor and epoch id;
- expects an exact reply;
- can be hidden from normal user-facing task history except diagnostics.

Suggested prompt shape:

```text
CC_BRIDGE_INTERNAL_POST_CLEAR_PROBE
agent=<agent>
epoch=<epoch_id>
project_root=<project_root>

You are a CC_BRIDGE-managed agent in this project. Treat AGENTS.md and mounted role
memory as authority. Do not edit files or start work.

Reply exactly:
CC_BRIDGE_CLEAR_READY epoch=<epoch_id>
```

The prompt intentionally carries only project identity and authority reminder.
It should not inject a large project summary. Its job is to force the provider
to create or expose a fresh stream and to prove that replies can be attributed
to the new epoch.

## Probe Result States

Keep probe states minimal.

`ready`:

- exact probe reply was received;
- provider stream evidence is bound to `new_epoch_id`.

`probe_failed`:

- provider returned empty, wrong, incomplete, timed out, or produced no usable
  stream evidence.

There is no half-success state. Without stream proof, the probe failed. The next
real ask may also serve as practical post-clear proof because same-epoch
terminal predicates will reject stale evidence.

## State Record

The first implementation should keep the record small. Candidate fields:

```text
agent_name
provider
epoch_id
prior_epoch_id
epoch_reason
epoch_created_at
pane_id
old_provider_stream
new_provider_stream
clear_request_id
clear_submitted_at
probe_job_id
probe_anchor
probe_status
probe_reply
ready_at
diagnostics
```

Storage should be CC_BRIDGE-owned runtime evidence, not provider-owned transcript
state. The exact path can be decided in the implementation slice, but the
consumer model should be stable: dispatcher and provider completion logic read
the current epoch and reject cross-epoch completion evidence.

## Provider Integration

Provider-specific code should only answer adapter questions:

- What stream id/path is current?
- Did the probe anchor appear in the stream?
- Did an exact probe reply appear?
- Did a session rotate, truncate, or offset rollback occur?
- Does this terminal item belong to the accepted epoch?

Provider-specific code should not decide global job semantics such as whether an
old job survives clear. That belongs to the CC_BRIDGE dispatcher/epoch layer.

## Relationship To Large Session Files

The probe helps response time because it creates compact fresh evidence before a
real user task arrives.

Normal path after clear:

1. clear creates a new epoch;
2. probe creates fresh compact evidence;
3. next ask starts from known epoch and stream cursor;
4. completion checks compact epoch evidence first.

Large raw sessions remain available for diagnostics and recovery, but successful
normal replies should not require repeated full-session scans. Existing provider
polling should keep the new epoch stream cursor warm after the probe; a
persistent tailer can be promoted later only if benchmarks show polling is still
too slow.

## Relationship To Existing Clear-Resume

`cc-bridge-clear-resume` remains the operator workflow for preserving work across bad
provider context.

This design gives it a stable substrate:

- before clear: build resume packet from durable CC_BRIDGE evidence;
- during clear: create epoch barrier and resolve active jobs;
- after clear: run probe and bind new stream;
- after probe: resubmit or ask with compact recovered context.

The resume packet is still separate from the probe. The probe proves continuity;
it does not carry the recovered task.

## Non-Goals

- Do not make probe prompts a hidden memory-injection channel.
- Do not keep active user jobs alive across clear by default.
- Do not make every provider implement identical session file logic.
- Do not add infinite retry loops around failed probes.
- Do not make the tailer a hidden memory-injection or full-transcript storage
  path.

## Acceptance Criteria

- `cc-bridge_clear <agent>` creates a new CC_BRIDGE-owned epoch before post-clear evidence
  can complete jobs.
- Active jobs cannot remain ambiguous across the barrier.
- Self-clear does not rely on the old provider context continuing after `/clear`.
- A post-clear probe can bind a new provider stream or report explicit failure.
- Codex, Claude, and future providers can plug into the same epoch/probe model
  while keeping provider-specific stream readers.
- Large provider session files are diagnostic evidence, not the normal
  coordination surface for the next reply.

## Decision

Adopt `cc-bridge_clear` as the provider session continuity manager:

- Clear advances a CC_BRIDGE-owned epoch.
- The post-clear probe proves the new epoch and stream before real work resumes.
- Provider-specific session logic supplies evidence, but CC_BRIDGE owns continuity and
  reply correctness.

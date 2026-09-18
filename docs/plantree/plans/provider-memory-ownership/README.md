# Provider Memory Ownership Plan

Date: 2026-06-07

## Purpose

Define one source-ownership model for generated provider memory so managed
Claude, Codex, and OpenCode do not receive duplicated project instructions,
provider-native memory, or CC_BRIDGE install blocks. The plan replaces text-level
deduplication with an explicit manifest that decides inclusion and filtering by
source kind.

## File Map

- [roadmap.md](roadmap.md): current planning and implementation sequence.
- [implementation-status.md](implementation-status.md): current implementation
  handoff, validation evidence, and remaining runtime checks.
- [open-questions.md](open-questions.md): unresolved provider behavior and
  rollout questions.
- [topics/source-ownership-manifest.md](topics/source-ownership-manifest.md):
  provider memory source kinds, include/exclude policy, filter policy,
  acceptance criteria, and implementation notes.
- [topics/implementation-sequence.md](topics/implementation-sequence.md):
  phase-gated implementation plan, code touch list, contract updates, tests,
  and validation gates.
- [decisions/001-source-ownership-not-text-dedup.md](decisions/001-source-ownership-not-text-dedup.md):
  decision to govern memory by source ownership rather than fuzzy rendered-text
  deduplication.
- [history/agent3-review-2026-06-07.md](history/agent3-review-2026-06-07.md):
  read-only review confirming the ownership manifest as the main solution and
  identifying implementation-readiness gaps.
- [history/reviewer1-alignment-2026-06-07.md](history/reviewer1-alignment-2026-06-07.md):
  implementation-readiness alignment and required phase/test ordering.
- [history/first-implementation-2026-06-07.md](history/first-implementation-2026-06-07.md):
  first policy/filter/provider-wiring implementation checkpoint.

## Related Sources

- [../../../cc-bridge-project-shared-memory-plan.md](../../../cc-bridge-project-shared-memory-plan.md)
- [../../../claude-session-isolation-contract.md](../../../claude-session-isolation-contract.md)
- [../../../codex-session-isolation-contract.md](../../../codex-session-isolation-contract.md)
- [../../../opencode-completion-contract.md](../../../opencode-completion-contract.md)
- [../../../cc-bridge-provider-state-storage-boundary-plan.md](../../../cc-bridge-provider-state-storage-boundary-plan.md)
- [../../../cc-bridge-daemon-startup-supervision-contract.md](../../../cc-bridge-daemon-startup-supervision-contract.md)

## Scope

In scope:

- A provider memory source ownership manifest used by Claude, Codex, OpenCode,
  and audited future provider rows such as Gemini.
- Filtering CC_BRIDGE install blocks and legacy CC_BRIDGE ask protocol text from inherited
  provider user memory.
- Keeping CC_BRIDGE runtime coordination rules as one canonical renderer-owned
  section.
- Removing duplicated ask guidance from the default `.cc-bridge/cc-bridge_memory.md`
  template without overwriting user-edited project memory.
- Updating Claude, Codex, and OpenCode contracts so they describe the same
  ownership model as the implementation.
- Regression tests for source inclusion, filtering, and rendered bundle
  content.

Out of scope:

- Sharing provider sessions, auth, or account homes across agents.
- Changing provider completion detection or reply matching semantics.
- Rewriting user-authored `CLAUDE.md`, `AGENTS.md`, `opencode.json`, or
  `.cc-bridge/cc-bridge_memory.md`.
- Fuzzy or semantic deduplication of user memory content.
- Installing Claude rules as a substitute for managed memory projection.

## Guiding Model

CC_BRIDGE should decide memory projection from source ownership:

```text
source kind -> native loaded? -> CC_BRIDGE bundle included? -> filter policy
```

The renderer renders selected sources; it does not guess whether two rendered
paragraphs are duplicates.

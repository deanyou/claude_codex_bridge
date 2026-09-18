# Expert Knowledge Database

Date: 2026-06-11

## Context

The user wants `cc-bridge_self` to be a CC_BRIDGE expert, not only a runtime repair agent.
That means its memory and skill database must include more CC_BRIDGE project
knowledge: public GitHub location, source-analysis routes, command/config
knowledge, and talk1's CC_BRIDGE developer manual, user manual, and role-facing
`cc-bridge_self` expert guide.

At the same time, `cc-bridge_self` should not become slow or brittle by loading the
whole source tree, full PDFs, or long manual chapters into session memory.
The role also should not fragment into a separate skill for every CC_BRIDGE
subsystem.

## Decision

Make `cc-bridge_self` a CC_BRIDGE expert through layered knowledge packaging:

1. Keep role `memory.md` compact. It should carry identity, boundaries,
   authority hierarchy, source/manual routing rules, and skill selection.
2. Add one broad v1 expert skill named `cc-bridge-expert-reference`.
3. Store durable CC_BRIDGE knowledge in role references, treated as the role's
   searchable "database".
4. Seed those references from talk1's manuals and current source-backed
   inventories.
5. Include the public upstream source URL:
   `https://github.com/SeemSeam/claude_codex_bridge`.
6. Prefer local source, docs, tests, and plan-tree evidence for exact answers;
   use GitHub only as a public anchor or host-enabled freshness fallback.

The initial reference package should include:

- `references/cc-bridge-project-index.md`
- `references/cc-bridge-manuals-index.md`
- `references/cc-bridge-source-map.md`
- `references/cc-bridge-command-surface.md`
- `references/cc-bridge-runtime-flows.md`
- `references/cc-bridge-role-and-config-system.md`
- `references/cc-bridge-release-and-test-gates.md`
- `references/cc-bridge-knowledge-refresh.md`

The full talk1 manuals remain canonical project docs under `docs/manuals/`.
The role may carry concise chapter maps and selected role-facing excerpts, but
should not embed full PDFs or the entire manual source unless a later packaging
decision proves that necessary.

## Consequences

- `cc-bridge_self` can answer architecture, usage, config, communication, release,
  and source-location questions with file-backed evidence.
- Session memory remains small and stable; detailed knowledge lives in
  references and source-backed lookup.
- The skill surface stays broad: maintenance skills remain separate, and
  expert lookup starts as one skill instead of several scattered skills.
- The role can work offline against a local CC_BRIDGE checkout while still knowing
  the public upstream URL.
- Future CC_BRIDGE changes need a knowledge-refresh step that updates references,
  not just role memory.

## Validation

The expert upgrade should be accepted only after prompt-style checks prove
that a fresh `cc-bridge_self` session can:

- report the CC_BRIDGE GitHub URL and local source lookup rule;
- choose the developer manual, user manual, or expert guide for a given
  question;
- locate a CLI command implementation and related tests;
- explain config validate, reload, and restart boundaries;
- explain ask/reply lineage and point to communication references;
- distinguish implemented, planned, released, and dirty-local behavior.

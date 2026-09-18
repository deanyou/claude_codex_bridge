# CC_BRIDGE Expert Knowledge Role

Date: 2026-06-10

## Direction

`cc-bridge_self` should become the project-local CC_BRIDGE expert, not only a runtime
maintenance operator.

The role should be able to quickly answer or resolve CC_BRIDGE-related questions
across:

- runtime health, mailbox, pane, provider, config, and recovery;
- CC_BRIDGE source architecture and module ownership;
- command usage, config grammar, role binding, and common workflows;
- new feature behavior, release status, validation gates, and plan-to-code
  traceability;
- CC_BRIDGE-owned pane text/visual state when self-supervision needs to see the real
  provider/tool UI, not only control-plane summaries.

This expands knowledge and guidance authority. It does not make `cc-bridge_self`
daemon authority, lifecycle authority, or business-task owner.

## Gap Before V1 Expert Upgrade

Before the 2026-06-11 v1 expert upgrade, the Role Pack was strong at
maintenance:

- `cc-bridge-self-diagnose`
- `cc-bridge-self-recover`
- `cc-bridge-self-chain`
- `cc-bridge-comm-reply-recover`
- `cc-bridge-config`

It was weak at expert CC_BRIDGE knowledge:

- no source/module navigation skill;
- no command/usage explanation skill;
- no new-feature/release-awareness workflow;
- no compact CC_BRIDGE architecture reference package;
- no role-facing index for talk1's CC_BRIDGE developer manual, user manual, and
  `cc-bridge_self` expert guide;
- no explicit GitHub/source lookup anchor for source-backed analysis;
- no dedicated CC_BRIDGE-owned pane-view self-supervision skill;
- no knowledge-refresh discipline after features land.

## V1 Materialized State

The 2026-06-11 local `agent-roles-spec` Role source now includes the first
expert upgrade:

- role version `0.2.0`;
- compact expert routing in `memory.md`;
- `cc-bridge-expert-reference` as the broad source/manual/command/release lookup
  skill;
- `references/cc-bridge-project-index.md` with the public GitHub URL and local
  checkout rules;
- `references/cc-bridge-manuals-index.md` for talk1's developer manual, user manual,
  and `cc-bridge_self` expert guide;
- `references/cc-bridge-source-map.md`;
- `references/cc-bridge-command-surface.md`;
- `references/cc-bridge-runtime-flows.md`;
- `references/cc-bridge-role-and-config-system.md`;
- `references/cc-bridge-release-and-test-gates.md`;
- `references/cc-bridge-knowledge-refresh.md`.

The v1 upgrade does not yet implement a dedicated pane-view diagnosis skill or
structured MCP source/diagnostic helpers.

## Manual And Source Inputs

`cc-bridge_self` expert knowledge should be seeded from the current local CC_BRIDGE source
tree and talk1's manual outputs:

- public source URL:
  `https://github.com/SeemSeam/claude_codex_bridge`;
- local development source root:
  `/home/bfly/yunwei/cc-bridge_source`;
- developer manual source:
  `docs/manuals/developer-guide/`;
- developer manual local PDF:
  `docs/manuals/developer-guide/build/main.pdf`;
- user manual source:
  `docs/manuals/user-guide/`;
- user manual local PDF:
  `docs/manuals/user-guide/build/main.pdf`;
- role-facing expert guide:
  `docs/manuals/cc-bridge-self-expert-guide.md`;
- manual plan and evidence:
  `docs/plantree/plans/cc-bridge-manuals/`.

The role should prefer local source, local docs, and tests for exact behavior.
The GitHub URL is a public upstream anchor and fallback for host-enabled
freshness checks; it should not make network access mandatory for normal
diagnosis or usage answers.

Do not copy the whole source tree or full manuals into role memory. The
distributable role should carry compact indexes and selected role-facing
excerpts, then route to local source/docs when they exist.

## Capability Model

### Maintenance Skills

Keep the existing maintenance skills. They own repair workflows and should not
be diluted with broad product documentation.

### Expert Skill

Add one broad v1 expert skill instead of several small knowledge skills:

- `cc-bridge-expert-reference`: answer "how do I use this", "where is this
  implemented", "which contract governs this", "what test proves it", "what
  changed", and "is this released or only planned" by routing through role
  references, talk1 manuals, plan-tree, git history, docs, source, and tests.

Do not create a separate skill for every CC_BRIDGE subsystem. Architecture
navigation, command usage, release/update awareness, and source lookup are
workflows inside this one skill until evidence shows that the skill is too
large or too slow.

Pane-view diagnosis remains runtime evidence handling. In v1 it can stay under
`cc-bridge-self-diagnose` or a later dedicated pane-view skill after text-capture and
screenshot MCP helpers are stable.

### Expert References

Add concise reference indexes to the Role Pack. They should point to canonical
source files, docs, and tests instead of copying long implementation detail.

Recommended references:

- `references/cc-bridge-project-index.md`: public GitHub URL, local source root,
  branch/release lookup hints, docs/manuals paths, and source-first answering
  rules.
- `references/cc-bridge-manuals-index.md`: talk1 developer manual, user manual,
  `cc-bridge_self` expert guide, chapter map, and which manual to consult for each
  user/developer/runtime question.
- `references/cc-bridge-source-map.md`: repo module map and ownership boundaries.
- `references/cc-bridge-command-surface.md`: CLI command groups, config surfaces,
  and usage evidence paths.
- `references/cc-bridge-runtime-flows.md`: cc-bridge-daemon, keeper, ask/reply, mailbox,
  provider, pane, heartbeat, restart, and reload flows.
- `references/cc-bridge-role-and-config-system.md`: role packs, projection,
  `.cc-bridge/cc-bridge.config`, reload, restart impact, and config authority.
- `references/cc-bridge-release-and-test-gates.md`: release phases, CI gates,
  source `cc-bridge_test` discipline, and real-runtime validation paths.
- `references/cc-bridge-knowledge-refresh.md`: how the role refreshes expert
  references after source changes land.

Reference files are the role's durable "database". They should be concise,
searchable, and source-backed. Role memory should only carry the routing rules
and hard boundaries needed at session start.

### Memory Routing

Update role memory to say that `cc-bridge_self` is both CC_BRIDGE maintainer and CC_BRIDGE
expert. Keep it compact:

- identity and non-goals;
- authority hierarchy and no-secret boundaries;
- public GitHub URL and local source root when available;
- manual/source routing rules;
- which built-in skill owns each class of request;
- reminder that local source/docs/tests beat memory for exact behavior.

Memory should not duplicate long manual chapters. If memory grows because it
is carrying facts that belong in indexes, move those facts to references.

## Answering Rules

When acting as a CC_BRIDGE expert, `cc-bridge_self` should:

- inspect local source/docs/tests before answering unstable or specific CC_BRIDGE
  behavior questions;
- cite concrete files and commands when giving architecture, usage, or release
  answers;
- distinguish live runtime authority, source implementation, documented
  contract, plan-tree intent, and stale residue;
- say when a feature is planned, implemented, tested, released, or merely
  present in a dirty local branch;
- prefer local repo evidence over memory;
- avoid broad refactors or implementation takeover unless the user explicitly
  asks for coding work.

## Knowledge Refresh

Refresh should be explicit and cheap in v1.

Triggers:

- user asks `cc-bridge_self` to refresh CC_BRIDGE knowledge;
- a CC_BRIDGE feature lands or is pushed;
- release validation completes;
- heartbeat or maintenance diagnosis reveals a new recurring failure class;
- role assets are updated.

Inputs:

- `git diff`, `git log`, changed files, and commit ids;
- docs and plan-tree status;
- tests added or changed;
- release/check output;
- runtime incident artifacts when relevant.

Outputs:

- updated expert reference indexes;
- updated role memory only when identity or hard boundaries change;
- updated skills only when the workflow itself changes;
- a short evidence note with commit/test references.

## V1 Slice

Implemented as the first narrow expert upgrade:

1. Update Role identity wording from pure "maintenance operator" to
   "CC_BRIDGE runtime and architecture expert".
2. Add `cc-bridge-expert-reference`.
3. Add `cc-bridge-project-index.md` and `cc-bridge-manuals-index.md`.
4. Add `cc-bridge-source-map.md` and `cc-bridge-command-surface.md`.
5. Update tests so the Role manifests the new skill/references and
   distributable text stays free of local source paths.
6. Validate with prompt-style checks:
   - locate a CLI command implementation and tests;
   - explain an ask/reply failure path;
   - explain a config reload versus restart impact;
   - identify whether a newly landed feature is implemented and tested;
   - find the GitHub URL and select the right talk1 manual chapter for a user
     or developer question.

## Later Slices

- Add `cc-bridge-feature-usage`.
- Add `cc-bridge-release-update-awareness`.
- Add `cc-bridge-knowledge-refresh` as either a skill or helper command.
- Add `cc-bridge-pane-view-diagnose` after text capture and screenshot helpers have
  a stable contract.
- Add structured MCP helpers for source/command lookup after the manual
  reference model proves useful.
- Consider a compact local generated index only after manual references become
  too slow or too stale.

## Risks

- Context bloat: mitigate with reference indexes and progressive disclosure.
- Stale expert docs: mitigate with explicit knowledge-refresh triggers and
  validation checks.
- Authority confusion: keep runtime/source/plan/release distinctions explicit.
- Overreach into business work: keep "CC_BRIDGE expert" scoped to CC_BRIDGE itself and
  require explicit user intent for feature implementation.
- Screenshot privacy: restrict fallback screenshot/visual inspection to
  CC_BRIDGE-owned panes/windows, prefer text capture when it is enough, and avoid
  quoting sensitive UI text.

## Acceptance Criteria

- A fresh `cc-bridge_self` session can answer common CC_BRIDGE architecture and usage
  questions with file-backed evidence.
- The Role Pack has a clear expert knowledge package without duplicating the
  whole repo into memory.
- New CC_BRIDGE functionality has a documented refresh path into `cc-bridge_self` expert
  references.
- Maintenance repair skills remain separate and usable.
- Later pane-view diagnosis remains bounded to CC_BRIDGE-owned surfaces and keeps
  evidence-only semantics.

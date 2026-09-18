# CC_BRIDGE Project Shared Memory Plan

## Planning Note

Provider-native project memory inclusion in this older plan is superseded by
the source ownership manifest work in
[docs/plantree/plans/provider-memory-ownership/README.md](plantree/plans/provider-memory-ownership/README.md).
The shared `.cc-bridge/cc-bridge_memory.md` source remains valid; the newer plan governs
whether provider-native project files such as `CLAUDE.md` or `AGENTS.md` are
also included in generated provider bundles.

## Purpose

CC_BRIDGE should provide a small project-level shared memory file that helps all
configured agents understand they are part of the same visible CC_BRIDGE agent team.

The primary purpose is agent awareness and agent-to-agent communication:

- agents should know that other configured project agents may exist
- agents should prefer CC_BRIDGE `ask` for visible cross-agent collaboration
- agents should avoid silently defaulting to provider-native hidden subagents
  when the work belongs to another CC_BRIDGE-managed project agent

This feature is not a full user manual, not a provider configuration system,
and not a replacement for provider-native memory files.

## Goals

- Create a project-level shared memory source at `project_root/.cc-bridge/cc-bridge_memory.md`.
- Keep the default `.cc-bridge/cc-bridge_memory.md` template minimal and English-only.
- Materialize shared memory into each managed agent on every startup.
- Preserve provider isolation and avoid mutating user global provider state.
- Work correctly when an agent workspace is not the original project root.
- Keep `.cc-bridge` generated state and private memory out of git by default.

## Non-Goals

- Do not inject long CLI command documentation into agent memory.
- Do not automatically edit `project_root/CLAUDE.md`, `project_root/AGENTS.md`,
  `project_root/GEMINI.md`, or other user-authored provider memory files.
- Do not edit `~/.claude`, `~/.codex`, `~/.gemini`, or OpenCode global config
  as part of this feature.
- Do not promise a universal provider-internal memory load order. CC_BRIDGE only
  controls the generated bundle content and provider-specific projection path.

## Project Files

Recommended project layout:

```text
project_root/
  .cc-bridge/
    cc-bridge_memory.md
    agents/
      agent1/
        memory.md
        provider-state/
          claude/
          codex/
          gemini/
          opencode/
<runtime_state_root>/
  state/
    memory.seed.json
  runtime/
    memory/
      agent1.md
      agent2.md
```

### User-Editable Files

- `.cc-bridge/cc-bridge_memory.md`
  - shared CC_BRIDGE project memory
  - safe to whitelist and commit when the team wants common agent collaboration rules
  - created automatically only when missing

- `.cc-bridge/agents/<agent>/memory.md`
  - optional agent-private memory
  - user data, but local/private by default
  - anchored under the project `.cc-bridge/` directory, not relocated runtime state
  - never deleted or rewritten automatically by normal startup

### Generated Files

- `<runtime_state_root>/state/memory.seed.json`
  - records template version and seed hash for the original generated `.cc-bridge/cc-bridge_memory.md`

- `<runtime_state_root>/runtime/memory/<agent>.md`
  - generated bundle for providers that need a stable project-relative memory
    path, especially OpenCode

- `.cc-bridge/agents/<agent>/provider-state/<provider>/...`
  - managed provider projection files
  - generated runtime state, not user-editable source

## Git Ignore Policy

`.cc-bridge` should be ignored by default because it contains runtime state,
provider-state, generated bundles, local config, session data, auth/config
projections, and optional agent-private memory.

Recommended default:

```gitignore
.cc-bridge/*
```

`.cc-bridge/cc-bridge_memory.md` is local by default under the project anchor. Teams that
want to share it can whitelist that specific file.

If a team explicitly wants to share `.cc-bridge/cc-bridge.config`, they can add their own
project-specific whitelist:

```gitignore
.cc-bridge/*
!.cc-bridge/
!.cc-bridge/cc-bridge_memory.md
!.cc-bridge/cc-bridge.config
```

CC_BRIDGE should not force this whitelist because `.cc-bridge/cc-bridge.config` may contain local
provider routing, model, URL, or key material.

## .cc-bridge/cc-bridge_memory.md Creation Semantics

Startup may create `project_root/.cc-bridge/cc-bridge_memory.md` only when the file is missing.

Requirements:

- Use atomic create-if-missing semantics.
- Do not create, import, or otherwise rely on project-root `CC_BRIDGE.md`.
- Never overwrite a user-edited `.cc-bridge/cc-bridge_memory.md`.
- Record seed metadata in `<runtime_state_root>/state/memory.seed.json`.
- If a future template version changes and the current `.cc-bridge/cc-bridge_memory.md`
  still matches the hash recorded in seed metadata, CC_BRIDGE may update it.
- If seed metadata is missing but the current `.cc-bridge/cc-bridge_memory.md` exactly
  matches a known generated legacy template, CC_BRIDGE may update it.
- If a future template version changes and the user has edited
  `.cc-bridge/cc-bridge_memory.md`, CC_BRIDGE must leave it untouched.
- If the project root is read-only, startup should continue without shared
  memory and record a warning.

## Minimal .cc-bridge/cc-bridge_memory.md Template

The default template should stay focused on agent awareness and CC_BRIDGE `ask`
communication.

````md
# CC_BRIDGE Project Memory

This project uses CC_BRIDGE for visible multi-agent collaboration.

## Collaboration

- You are one agent in a CC_BRIDGE-managed project team.
- Use CC_BRIDGE `ask` for project-level collaboration with configured agents.
- Delegate with the goal, scope/files, assumptions, expected output, and verification needs.
- Reply concisely with findings, changes, verification, blockers, and risks when relevant.

## Ask Communication

Preferred form:

```text
/ask <agent> <message>
```

Shell fallback:

```bash
command ask "$TARGET" <<'EOF'
$MESSAGE
EOF
```

- Submit once, then stop. Do not wait, poll, or run `pend`/`watch`/`ping` unless diagnostics were requested.
- During an active CC_BRIDGE ask task, use `ask --chain` when a child result is needed to finish the current task; use `ask --silence` only for independent no-result-needed work.
- Plain nested `ask` from an active task is rejected by CC_BRIDGE.
````

## Memory Bundle Model

CC_BRIDGE should generate a provider-facing memory bundle per agent. The bundle is a
single markdown document with explicit source sections.

CC_BRIDGE should not claim that every provider loads memory in the same order.
Instead, CC_BRIDGE controls the generated bundle order:

```md
# CC_BRIDGE Managed Agent Memory

<!-- generated by cc-bridge; do not edit this file directly -->

## CC_BRIDGE Runtime Coordination Rules

CC_BRIDGE-owned provider-facing runtime rules, including the submit-only ask
handoff contract and the non-destructive `cc-bridge clear` context-reset contract.
These rules are generated by CC_BRIDGE so old user-edited `.cc-bridge/cc-bridge_memory.md` files
do not keep reintroducing weak control guidance.

## CC_BRIDGE Shared Project Memory
source: project_root/.cc-bridge/cc-bridge_memory.md

## Provider-Native Project Memory
source: provider policy decides whether project_root/CLAUDE.md, AGENTS.md,
GEMINI.md, or equivalent enters the generated bundle

## Agent Private Memory
source: .cc-bridge/agents/<agent>/memory.md
```

The provider/system/account memory layer remains provider-owned and outside
this generated bundle unless explicitly inherited through a provider profile
field.

## Source Resolution

Memory source resolution must use `project_root`, not the agent workspace, for
project-level memory files.

This matters because configured agents may run in:

- `project_root`
- a copy workspace
- a git worktree
- a custom workspace root

Therefore, CC_BRIDGE must explicitly read:

- `project_root/.cc-bridge/cc-bridge_memory.md`
- provider-native project memory only when the provider memory ownership policy
  says CC_BRIDGE owns loading that source
- filtered provider user memory when inherited through a provider profile
- `project_root/.cc-bridge/agents/<agent>/memory.md`

Provider-native project memory should not be discovered only from the agent
runtime cwd.

Agent-private memory is anchored at `project_root/.cc-bridge/agents/<agent>/memory.md`
even when provider runtime state is relocated. This intentionally separates
user-editable memory from generated provider runtime directories.

## Provider Strategy

### Claude Code

Claude Code should receive the generated bundle through the managed Claude home:

```text
.cc-bridge/agents/<agent>/provider-state/claude/home/.claude/CLAUDE.md
```

The existing path that syncs `source_home/.claude/CLAUDE.md` into the same
managed file must be merged into the new memory pipeline or disabled for memory
projection. Otherwise, two startup steps can write the same target file and the
last writer wins.

Recommended profile model:

- add `inherit_memory`, default `true`
- keep `inherit_memory` independent from `inherit_skills`
- keep skill and command projection behavior unchanged

### Codex

Codex should receive the generated bundle through its managed `CODEX_HOME`:

```text
.cc-bridge/agents/<agent>/provider-state/codex/home/AGENTS.md
```

Do not rely on workspace discovery alone because the agent workspace may not be
the original project root.

Provider-native project `AGENTS.md` inclusion is now governed by the provider
memory ownership policy. Current Codex managed memory excludes project
`AGENTS.md` from `CODEX_HOME/AGENTS.md` because Codex owns native project-memory
loading.

Codex launcher integration must mirror Claude's launch-context contract:
declare `prepare_launch_context`, put `project_root`, `workspace_path`, and
`agent_events_path` into `prepared_state`, and read those values during memory
projection instead of inferring project identity from provider runtime paths.

Codex startup must write `codex_memory_projection_{ok,skipped,failed}` events
with the same marker-dedup semantics as Claude. Missing launch context is a
startup contract violation and should fail fast before launching the provider.

### Gemini

Gemini should receive the generated bundle through its managed Gemini home:

```text
.cc-bridge/agents/<agent>/provider-state/gemini/home/.gemini/GEMINI.md
```

The implementation uses the managed `.gemini/settings.json` `contextFileName`
field to point Gemini at `GEMINI.md`. `inherit_memory = false` removes the
generated file and clears that managed `contextFileName` value. Gemini CLI
0.41.2 was smoke-tested with `HOME`, `GEMINI_CLI_HOME`, and `GEMINI_ROOT`
pointing at the managed home; a token present only in managed
`.gemini/GEMINI.md` was available to `gemini --prompt`. Re-run this smoke when
upgrading Gemini CLI versions so the loading mechanism does not drift.

### OpenCode

OpenCode should use its config `instructions` mechanism. CC_BRIDGE must not modify
`project_root/AGENTS.md` or `project_root/opencode.json`.

Generate the canonical runtime memory bundle under runtime state, then expose a
project-relative bridge path for OpenCode versions that resolve instructions
relative to the project:

```text
<runtime_state_root>/runtime/memory/<agent>.md
project_root/.cc-bridge/runtime/memory/<agent>.md
```

Generate an agent-local OpenCode config:

```text
.cc-bridge/agents/<agent>/provider-state/opencode/opencode.json
```

Example:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    ".cc-bridge/runtime/memory/agent3.md",
    ".cc-bridge/runtime/skills/agent3/opencode/ask.md"
  ]
}
```

Launch OpenCode with an absolute `OPENCODE_CONFIG` pointing to the generated
config file. The generated config must merge `project_root/opencode.json` when
present:

- user keys win for all fields except `instructions`
- `instructions` is a stable union of user entries plus CC_BRIDGE bridge entries for
  inherited memory and inherited ask skill guidance
- invalid project config degrades by writing the minimal CC_BRIDGE config and
  recording `opencode_config_merge_failed`
- `inherit_memory = false` removes only the memory bridge; generated
  `OPENCODE_CONFIG` is removed only when inherited memory and inherited skills
  are both disabled

This avoids treating `OPENCODE_CONFIG` as a replacement that silently discards
project provider, model, MCP, permission, or instruction settings.

## Runtime Integration

Recommended new module:

```text
lib/project_memory/
  template.py
  loader.py
  renderer.py
  materializer.py
```

Responsibilities:

- ensure `.cc-bridge/cc-bridge_memory.md` exists when safe
- load shared, provider-native, and agent-private memory sources
- render deterministic generated bundles
- materialize provider-specific memory files/config
- report path, hash, mtime, source list, and warnings for diagnostics

The startup flow should call project memory materialization before launching the
provider process and after the provider runtime directory/home is known.
`prepare_provider_workspace` is the preferred single writer for generated
provider memory/config projections; command builders should read prepared
paths/env only unless a provider explicitly documents a different lifecycle.

Memory materialization should be idempotent. Failure to write generated memory
should not prevent agent startup unless the provider requires the generated file
to start correctly. Prefer warning and degraded startup.

## Diagnostics

Diagnostics should include metadata, not memory body text:

- shared memory path
- generated bundle path
- provider projection path
- sha256
- mtime
- source files
- missing-source warnings
- read/write warnings

Support bundles must avoid exporting sensitive generated provider-state content
unless the diagnostics policy explicitly allows a redacted form.

## Cleanup Semantics

- `.cc-bridge/cc-bridge_memory.md` is user data and must not be deleted automatically.
- `.cc-bridge/agents/<agent>/memory.md` is user data and must not be deleted by normal
  startup.
- `.cc-bridge/runtime/memory/<agent>.md` is generated runtime state and may be removed
  during runtime cleanup.
- Provider-state memory projections are generated runtime state and may be
  removed with the corresponding provider-state.

## Contract Updates Required

Implementation should update these documents in the same patch set:

- `docs/cc-bridge-config-layout-contract.md`
  - define `.cc-bridge/cc-bridge_memory.md` and `.cc-bridge/agents/<agent>/memory.md`
  - state that `.cc-bridge` is ignored/local by default

- `docs/cc-bridge-daemon-startup-supervision-contract.md`
  - add project memory materialization as an idempotent startup step
  - define failure downgrade behavior

- `docs/claude-session-isolation-contract.md`
  - define managed `.claude/CLAUDE.md` as a CC_BRIDGE-generated projection
  - clarify `inherit_memory` versus `inherit_skills`

- `docs/codex-session-isolation-contract.md`
  - define managed `CODEX_HOME/AGENTS.md` projection

- `docs/gemini-session-isolation-contract.md`
  - define managed `.gemini/GEMINI.md` projection and loading mechanism

- OpenCode contract coverage
  - update `docs/opencode-completion-contract.md` only if completion behavior is
    affected
  - otherwise add or update an OpenCode isolation/config contract for generated
    `opencode.json`

## Tests Required

- Missing `.cc-bridge/cc-bridge_memory.md` is created once.
- Edited `.cc-bridge/cc-bridge_memory.md` is not overwritten.
- Read-only project root degrades with a warning.
- Concurrent startup does not corrupt `.cc-bridge/cc-bridge_memory.md`.
- Claude has no double-write conflict for managed `.claude/CLAUDE.md`.
- Codex receives `CODEX_HOME/AGENTS.md`.
- Gemini generated memory is actually loaded by the current CLI mechanism.
- OpenCode receives generated `opencode.json` and project-relative
  `instructions`.
- Copy workspace and git-worktree agents still inherit `project_root/.cc-bridge/cc-bridge_memory.md`.
- Agent-private memory enters the generated bundle.
- Diagnostics expose metadata only, not memory body text.

## Implementation Sequence

1. Add `inherit_memory` to provider profile models, defaulting to `true`.
2. Add project memory template, seed metadata, loader, renderer, and diagnostics
   metadata.
3. Integrate Claude first and remove the existing double-write risk.
4. Integrate Codex.
5. Verify and integrate Gemini memory loading.
6. Verify and integrate OpenCode config instructions.
7. Update contracts and diagnostics.
8. Add focused regression tests for startup, workspace isolation, and generated
   provider projections.

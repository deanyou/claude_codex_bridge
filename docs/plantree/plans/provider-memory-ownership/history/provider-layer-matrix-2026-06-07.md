# Provider Layer Matrix Validation

Date: 2026-06-07

Project: `/home/bfly/yunwei/test_cc-bridge_provider_memory_matrix`

## Purpose

Validate real source-runtime context assembly for every managed provider with
multiple memory layers present:

- provider user memory
- project-native provider memory files
- CC_BRIDGE shared project memory
- agent-private memory

## Setup

Configured agents:

- `codexer:codex`
- `clauder:claude`
- `opencoder:opencode`
- `geminier:gemini`

Sentinel sources:

- project `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md`
- `.cc-bridge/cc-bridge_memory.md`
- `.cc-bridge/agents/<agent>/memory.md`
- fake provider source home under `source_home/`

The first attempt used `CC_BRIDGE_SOURCE_HOME`, but provider home materialization in
the source-runtime startup path did not retain that variable through the project
control-plane environment. The successful run used:

```bash
HOME=/home/bfly/yunwei/test_cc-bridge_provider_memory_matrix/source_home \
  /home/bfly/yunwei/cc-bridge_source/cc-bridge_test
```

Codex provider-user memory in real startup is read from
`<source_home>/.codex/AGENTS.md`.

## Result

Source start succeeded:

```text
start_status: ok
cc-bridge-daemon_started: true
agents: codexer, clauder, opencoder, geminier
```

Opt-in matrix assertion:

```bash
CC_BRIDGE_PROVIDER_MEMORY_MATRIX_CHECK=1 \
CC_BRIDGE_PROVIDER_MEMORY_MATRIX_PROJECT=/home/bfly/yunwei/test_cc-bridge_provider_memory_matrix \
pytest -q test/test_provider_memory_external_matrix.py
```

Result: 1 passed.

## Verified Composition

- Codex generated `AGENTS.md` includes provider user, shared, and agent-private
  memory; project `AGENTS.md` is excluded; old CC_BRIDGE roles block is filtered.
- Claude generated `.claude/CLAUDE.md` includes provider user, shared, and
  agent-private memory; project `CLAUDE.md` is excluded; old CC_BRIDGE config block is
  filtered.
- OpenCode generated `.cc-bridge/runtime/memory/opencoder.md` includes shared and
  agent-private memory; project `AGENTS.md` is excluded from the generated CC_BRIDGE
  bundle; generated `opencode.json` still includes native `AGENTS.md` and the
  CC_BRIDGE memory bridge.
- Gemini generated `.gemini/GEMINI.md` includes provider user, shared, project
  `GEMINI.md`, and agent-private memory; old Gemini inspiration block is
  filtered; managed `settings.json` uses `contextFileName = GEMINI.md`.
- Every generated bundle has exactly one `CC_BRIDGE Runtime Coordination Rules`
  section and one `command ask "$TARGET"` shell fallback.

# Worker1 Real `test_ccb2` Four-Provider Review

Date: 2026-06-07

## Scope

`worker1` was cleared, then authorized to modify only the external test project
`/home/bfly/yunwei/test_ccb2` so that the real project covers Codex, Claude,
OpenCode, and Gemini provider memory generation. Source files under
`/home/bfly/yunwei/cc-bridge_source` were not modified by the worker.

## Test Project Changes

The original config was backed up inside the test project:

- `/home/bfly/yunwei/test_ccb2/.cc-bridge/cc-bridge.config.worker1-backup-20260607-204510`

Files modified or created under `/home/bfly/yunwei/test_ccb2`:

- `.cc-bridge/cc-bridge.config`
- `.cc-bridge/cc-bridge_memory.md`
- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
- `opencode.json`
- `.cc-bridge/agents/{codexer,clauder,opencoder,geminier}/memory.md`
- `source_home/.codex/AGENTS.md`
- `source_home/.claude/CLAUDE.md`
- `source_home/.gemini/GEMINI.md`
- `source_home/.gemini/settings.json`

## Commands Reported

All runtime commands were run from `/home/bfly/yunwei/test_ccb2` with source
`cc-bridge_test`:

```bash
CC_BRIDGE_SOURCE_HOME=/home/bfly/yunwei/test_ccb2/source_home HOME=/home/bfly/yunwei/test_ccb2/source_home /home/bfly/yunwei/cc-bridge_source/cc-bridge_test clear
CC_BRIDGE_SOURCE_HOME=/home/bfly/yunwei/test_ccb2/source_home HOME=/home/bfly/yunwei/test_ccb2/source_home /home/bfly/yunwei/cc-bridge_source/cc-bridge_test doctor
CC_BRIDGE_SOURCE_HOME=/home/bfly/yunwei/test_ccb2/source_home HOME=/home/bfly/yunwei/test_ccb2/source_home /home/bfly/yunwei/cc-bridge_source/cc-bridge_test
CC_BRIDGE_SOURCE_HOME=/home/bfly/yunwei/test_ccb2/source_home HOME=/home/bfly/yunwei/test_ccb2/source_home /home/bfly/yunwei/cc-bridge_source/cc-bridge_test reload --dry-run
CC_BRIDGE_SOURCE_HOME=/home/bfly/yunwei/test_ccb2/source_home HOME=/home/bfly/yunwei/test_ccb2/source_home /home/bfly/yunwei/cc-bridge_source/cc-bridge_test kill
CC_BRIDGE_SOURCE_HOME=/home/bfly/yunwei/test_ccb2/source_home HOME=/home/bfly/yunwei/test_ccb2/source_home /home/bfly/yunwei/cc-bridge_source/cc-bridge_test -n
CC_BRIDGE_SOURCE_HOME=/home/bfly/yunwei/test_ccb2/source_home HOME=/home/bfly/yunwei/test_ccb2/source_home /home/bfly/yunwei/cc-bridge_source/cc-bridge_test
```

`cc-bridge_test -n` failed only because non-interactive stdin could not satisfy the
confirmation prompt. After `kill`, a plain source `cc-bridge_test` start succeeded.

The opt-in external context check was run from `/home/bfly/yunwei/cc-bridge_source`:

```bash
CC_BRIDGE_REAL_PROJECT_MEMORY_CHECK=1 CC_BRIDGE_REAL_TEST_PROJECT=/home/bfly/yunwei/test_ccb2 pytest -q test/test_provider_memory_external_context.py
```

Result: `1 passed in 0.04s`.

## Runtime Result

`doctor` reported a mounted, healthy source runtime with generation 2. Codex,
Claude, OpenCode, and Gemini provider CLIs were available; agents `codexer`,
`clauder`, `opencoder`, and `geminier` launched healthy.

## Generated Context Evidence

Codex:

- File:
  `/home/bfly/yunwei/test_ccb2/.cc-bridge/agents/codexer/provider-state/codex/home/AGENTS.md`
- `CC_BRIDGE Runtime Coordination Rules`: 1
- `CC_BRIDGE Shared Project Memory`: 1
- `Provider User Memory`: 1
- `Provider-Native Project Memory`: 0
- private memory: 1
- shared, provider-user, and private sentinels present
- project `AGENTS.md` sentinel absent
- legacy CC_BRIDGE blocks absent

Claude:

- File:
  `/home/bfly/yunwei/test_ccb2/.cc-bridge/agents/clauder/provider-state/claude/home/.claude/CLAUDE.md`
- `CC_BRIDGE Runtime Coordination Rules`: 1
- `CC_BRIDGE Shared Project Memory`: 1
- `Provider User Memory`: 1
- `Provider-Native Project Memory`: 0
- private memory: 1
- shared, provider-user, and private sentinels present
- project `CLAUDE.md` sentinel absent
- legacy CC_BRIDGE blocks absent

OpenCode:

- Runtime memory:
  `/home/bfly/yunwei/test_ccb2/.cc-bridge/runtime/memory/opencoder.md`
- Generated config:
  `/home/bfly/yunwei/test_ccb2/.cc-bridge/agents/opencoder/provider-state/opencode/opencode.json`
- `CC_BRIDGE Runtime Coordination Rules`: 1
- `CC_BRIDGE Shared Project Memory`: 1
- `Provider User Memory`: 0
- `Provider-Native Project Memory`: 0
- private memory: 1
- shared and private sentinels present
- project `AGENTS.md` sentinel absent from memory bridge
- generated config instructions:
  `["AGENTS.md", ".cc-bridge/runtime/memory/opencoder.md"]`

Gemini:

- File:
  `/home/bfly/yunwei/test_ccb2/.cc-bridge/agents/geminier/provider-state/gemini/home/.gemini/GEMINI.md`
- Settings:
  `/home/bfly/yunwei/test_ccb2/.cc-bridge/agents/geminier/provider-state/gemini/home/.gemini/settings.json`
- `CC_BRIDGE Runtime Coordination Rules`: 1
- `CC_BRIDGE Shared Project Memory`: 1
- `Provider User Memory`: 1
- `Provider-Native Project Memory`: 1
- private memory: 1
- shared, provider-user, project, and private sentinels present
- project `GEMINI.md` sentinel present, matching the current pending-audit
  policy
- legacy CC_BRIDGE blocks absent
- `contextFileName`: `GEMINI.md`

## Findings

HIGH: none.

MEDIUM: none for provider memory ownership.

LOW:

- Existing mounted topology could not be safely replaced by plain `cc-bridge_test`;
  `reload --dry-run` reported the non-safe remove/add plan. The worker used
  `cc-bridge_test kill` and then a plain source start.
- `cc-bridge_test -n` is not usable non-interactively because it requires TTY
  confirmation.
- Real OpenCode startup rewrote root `opencode.json` and dropped the temporary
  `theme` fixture, but generated provider-state config still preserved native
  `AGENTS.md` plus the CC_BRIDGE memory bridge instruction.

## Recommendation

Mergeable for provider memory ownership. The real modified `test_ccb2`
four-provider run validates the intended behavior. Gemini remains explicitly
pending audit, but current policy and runtime output are consistent.

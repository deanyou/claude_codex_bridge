# Provider Memory Ownership Open Questions

Date: 2026-06-07

## Open Questions

1. Should Gemini follow the Claude/Codex `provider_native_project = exclude`
   rule, or does its managed `contextFileName` projection make CC_BRIDGE the only
   reliable loader for project `GEMINI.md`?
2. Which exact legacy install-block markers exist in released CC_BRIDGE versions and
   must be stripped from provider user memory? Current candidates are
   `CC_BRIDGE_CONFIG_START`, `CC_BRIDGE_ROLES_START`, `CODEX_REVIEW_START`,
   `GEMINI_INSPIRATION_START`, and older unmarked collaboration-rule sections,
   but older release variants may still need a wider inventory.
3. Should filtering events be recorded only in agent events, or should
   diagnostics also include a compact source manifest summary?
## Closed Questions

1. OpenCode project `AGENTS.md` ownership is no longer conditional for the
   current implementation. OpenCode 1.16.2 natively discovers project
   `AGENTS.md` while also loading configured `instructions`, so CC_BRIDGE excludes
   project `AGENTS.md` from the generated runtime memory bundle and keeps the
   `.cc-bridge/runtime/memory/<agent>.md` bridge as CC_BRIDGE-only shared/private memory.
2. Old generated `.cc-bridge/cc-bridge_memory.md` upgrade policy is exact-match based. If
   `memory.seed.json` records an older template version and the current file
   hash still matches that seed hash, CC_BRIDGE upgrades the file to the current
   template. If seed metadata is missing, CC_BRIDGE may still upgrade exact known
   generated legacy templates. If the file was edited, CC_BRIDGE leaves it untouched.

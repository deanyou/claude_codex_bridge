# Role Pack System Open Questions

Date: 2026-06-01

## Open

1. Should the first schema be authored only as `role.toml`, or should a JSON
   Schema artifact be published in parallel for non-Python hosts?
2. What minimum trust gate is required before running a third-party role
   installer: explicit prompt, allowlist, digest pin, signature, or all of
   these?
3. How should a host resolve conflicts when two roles want to install the same
   provider skill name?
4. Should role tool dependencies be allowed to install into user-level
   language package managers, or must the first CC_BRIDGE implementation always use
   CC_BRIDGE-owned venv/cache roots?
5. Should role ids use `publisher.role` only, or should the spec also reserve a
   URI-like form such as `rolepack://publisher/role`?
6. When a required role tool hook fails during install, update, or sync, should
   CC_BRIDGE roll back `current` and metadata, or record an installed-but-degraded
   state that doctor and reload can surface?
7. What transaction model should protect role install/update/sync and project
   config writes from concurrent or partial failures?
8. Should GitHub catalog clone/pull failures be represented as explicit
   catalog diagnostics instead of silently returning no default catalog?
9. What exact store path should the spec-owned package manager use by default:
    `~/.roles`, an XDG data path, or a configurable path with `~/.roles` as a
    user-facing alias?
10. Should CC_BRIDGE call the spec-owned package manager through a subprocess JSON
    protocol, a Python library, or both?
11. What user-facing doctor/cleanup command should report and optionally remove
    legacy `.cc-bridge/role-lock.json` files after locks become non-authoritative?

## Resolved

- Fixed role identity and user-facing agent names are separate. See
  [decisions/001-role-id-separate-from-agent-name.md](decisions/001-role-id-separate-from-agent-name.md).
- Role assets are installed once and projected into agents. See
  [decisions/002-system-role-store-project-locks.md](decisions/002-system-role-store-project-locks.md).
- Role Packs should be host-neutral with adapters. See
  [decisions/003-rolepacks-are-host-neutral-with-adapters.md](decisions/003-rolepacks-are-host-neutral-with-adapters.md).
- CC_BRIDGE role-id shorthand resolves to a project-local agent name, and sidebar
  rows use that local name. See
  [decisions/004-role-id-shorthand-resolves-to-agent-name.md](decisions/004-role-id-shorthand-resolves-to-agent-name.md).
- Production role package content should live in `agent-roles-spec`, not in
  the CC_BRIDGE source tree. The first CC_BRIDGE slice consumes the catalog and owns local
  installation, projection, update prompts, and diagnostics. See
  [decisions/005-agent-roles-spec-is-catalog-authority.md](decisions/005-agent-roles-spec-is-catalog-authority.md).
- Long term, `agent-roles-spec` should own the `.roles` package store and role
  payload install/update semantics, while CC_BRIDGE owns project/runtime integration.
  See
  [decisions/006-agent-roles-spec-owns-roles-store.md](decisions/006-agent-roles-spec-owns-roles-store.md).
- `.roles` should keep one current installed package per role id, projects
  should follow installed current, and live agents should adopt role changes
  through guarded restart rather than provider-native clear or project-lock
  refresh. See
  [decisions/007-single-current-store-and-restart-adoption.md](decisions/007-single-current-store-and-restart-adoption.md).
- CC_BRIDGE may manage a consumption-only GitHub cache of `agent-roles-spec` under
  `$XDG_CACHE_HOME/cc-bridge/role-catalogs/agent-roles-spec` when no local catalog is
  available. User-level system role sources and local env/path catalogs still
  take precedence, and role content changes go to upstream `agent-roles-spec`
  by pull request. See
  [decisions/005-agent-roles-spec-is-catalog-authority.md](decisions/005-agent-roles-spec-is-catalog-authority.md)
  and [topics/distribution-and-trust.md](topics/distribution-and-trust.md).
- User-level system role sources at `~/.cc-bridge/roles` and `~/.roles` are the
  first local editable role library. They are visible in `cc-bridge roles list` and
  can be snapshotted into the installed store by `cc-bridge roles add`; project-level
  `.roles` directories are deferred.
- During `cc-bridge update`, CC_BRIDGE reports newly available catalog roles, prompts
  interactively before installing them into the local role store, and prints
  follow-up install commands in non-interactive runs. See
  [topics/catalog-update-flow.md](topics/catalog-update-flow.md).

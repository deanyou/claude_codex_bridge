# Spec-Owned Roles Store Boundary

Date: 2026-06-04

## Objective

Define the target split where `agent-roles-spec` owns reusable role package
management and CC_BRIDGE consumes resolved role packages for project runtime
integration.

This topic refines the earlier CC_BRIDGE-first implementation without deleting the
current implementation snapshot in
[current-roles-management-scheme.md](current-roles-management-scheme.md).

## Target Authority Split

`agent-roles-spec` owns role package state:

- the system-level `.roles` store or equivalent XDG-backed store
- catalog clone/cache state for `https://github.com/SeemSeam/agent-roles-spec`
- role package list, install, update, sync, doctor, repair, and metadata
- content digest, version, provenance, and source records
- role id aliases and migrations such as `cc-bridge.archi -> agentroles.archi`
- package validation, schema compatibility, and contribution gates

CC_BRIDGE owns CC_BRIDGE runtime state:

- `.cc-bridge/cc-bridge.config`
- provider home projection and cleanup
- legacy role-lock diagnostics and cleanup for old projects
- CC_BRIDGE adapter policy for tool hooks, prompts, i18n output, and required
  failure semantics
- CC_BRIDGE update sequencing around old and new entrypoints
- ask/sidebar/reload/diagnostic behavior for mounted agents
- role-aware restart behavior for running agents

The practical rule is: `.roles` is package-manager state; `.cc-bridge` is project
runtime state.

## Store Model

The target store should be described by `agent-roles-spec`, not CC_BRIDGE:

```text
~/.roles/
  catalogs/
    agent-roles-spec/
      .git/
      roles/
      reference_roles/
  installed/
    agentroles.archi/
      install.json
      current/
        role.toml
        memory.md
        adapters/
        skills/
        tools/
```

The package manager may choose `current/` or a flat role directory, but the
target runtime contract is one installed package per role id. `install.json`
keeps version, digest, source, and provenance metadata for catalog comparison
and runtime freshness diagnostics. The digest is not a project lock target.

CC_BRIDGE may keep a compatibility bridge from the current
`$XDG_DATA_HOME/cc-bridge/roles/` store while the spec-owned store is introduced.
Old multi-version stores should resolve through their `current` pointer during
migration, then be rewritten into the single-current store on the next
install/update.

The current CC_BRIDGE bridge uses `.roles/installed` as the preferred installed-role
store. Earlier bridge slices copied legacy installed snapshots into
`.roles/installed` so project locks could resolve the same version/digest.
That lock-preserving requirement is superseded by
[../decisions/007-single-current-store-and-restart-adoption.md](../decisions/007-single-current-store-and-restart-adoption.md):
runtime lookup should follow installed current, and old role locks should be
treated as legacy diagnostics instead of adoption authority.

## Agent Roles Tool Contract

The spec project should expose a stable tool or library boundary. CC_BRIDGE should be
able to call it without importing CC_BRIDGE runtime modules.

Minimum operations:

```bash
agent-roles sync .
agent-roles list --json
agent-roles install agentroles.archi --json
agent-roles update agentroles.archi --json
agent-roles doctor agentroles.archi --json
agent-roles resolve agentroles.archi --json
```

The JSON contract should include:

- canonical role id
- accepted legacy aliases
- version and digest
- installed path
- source kind and source path
- adapter compatibility
- declared tool hooks and permissions
- warning and failure diagnostics with stable codes

CC_BRIDGE should treat this as a package-manager API. It should not parse human
output or depend on transient filesystem implementation details beyond the
resolved installed path and metadata.

## CC_BRIDGE Wrapper Behavior

CC_BRIDGE keeps user-facing commands where they are already part of CC_BRIDGE workflows:

```bash
cc-bridge roles list
cc-bridge roles sync
cc-bridge roles install agentroles.archi
cc-bridge roles update agentroles.archi
cc-bridge roles doctor agentroles.archi
cc-bridge roles add agentroles.archi:codex
```

For package operations, CC_BRIDGE delegates to the spec-owned package manager and
then adds CC_BRIDGE-specific behavior:

- enforce CC_BRIDGE post-update required/optional failure policy
- run or validate CC_BRIDGE adapter hooks according to CC_BRIDGE policy
- write project config for `roles add`
- project role memory, skills, prompts, and plugins into provider homes
- report role install/current/freshness diagnostics
- restart idle agents to adopt changed role assets when requested

`cc-bridge roles add` remains CC_BRIDGE-owned because it mutates `.cc-bridge/cc-bridge.config`.

Delegation is unconditional in CC_BRIDGE. The CC_BRIDGE-private installed-role writer and
`CC_BRIDGE_AGENT_ROLES_MANAGER` rollback switch are removed so role payload writes have
one owner: `agent-roles`.

## Migration Sequence

1. Done: specify the `agent-roles` package-manager CLI/API and `.roles`
   metadata in `agent-roles-spec`.
2. Done: add CC_BRIDGE compatibility reads for `.roles/installed`.
3. Done: make `cc-bridge roles install/update/sync` call `agent-roles` for package
   payload operations while preserving CC_BRIDGE output and tool-hook policy.
4. Done: copy legacy installed role snapshots into `.roles/installed` at CC_BRIDGE
   management boundaries, including legacy `cc-bridge.archi` aliases.
5. Done: remove the CC_BRIDGE-private installed role writer, remove the rollback
   switch, and make runtime lookup use `.roles/installed` as the only installed
   role store.
6. Next: simplify `agent-roles` installed store writes to one current package
   per role id.
7. Next: remove CC_BRIDGE role-lock resolution and make old `.cc-bridge/role-lock.json`
   files diagnostic residue.
8. Next: add provider launch role digest evidence and role-aware restart
   adoption.
9. Next: validate old-version upgrades with existing multi-version stores,
   existing project locks, and stale `source_path` metadata.
10. Next: move migration ownership from the CC_BRIDGE compatibility bridge into
   `agent-roles` once the package manager exposes a stable migration command.

## Non-Goals

- Do not move `.cc-bridge/cc-bridge.config` into `agent-roles-spec`.
- Do not let `agent-roles-spec` manage provider sessions, auth, tmux panes,
  mailbox state, or CC_BRIDGE lifecycle files.
- Do not make CC_BRIDGE startup depend on network access to resolve a mounted role.
- Do not hot-replace role memory/skills inside a running provider conversation
  without guarded restart.

## Risks

- A subprocess-only package manager may make errors harder to type-check unless
  the JSON protocol is strict and versioned.
- A library API may tempt CC_BRIDGE runtime paths to import management code; import
  boundary tests remain required.
- Legacy migration can confuse users unless diagnostics clearly distinguish
  migration input from the active `.roles/installed` store.
- Tool hook ownership must stay explicit: role packages declare hooks, but CC_BRIDGE
  decides whether running them is allowed or required in a CC_BRIDGE update/install
  context.
- Existing `.cc-bridge/role-lock.json` files must become harmless residue; otherwise
  old projects may keep suppressing role memory or skills after the single-current
  model lands.
- CC_BRIDGE currently owns the compatibility migration bridge. Long term, migration
  should be a first-class `agent-roles` operation because `.roles` package state
  belongs to `agent-roles-spec`.
- Development-only source checkout discovery must not become a stable production
  dependency. Released CC_BRIDGE should prefer `AGENT_ROLES_CLI`, `agent-roles` on
  `PATH`, an installed Python package, or an explicit `AGENT_ROLES_SPEC_HOME`.

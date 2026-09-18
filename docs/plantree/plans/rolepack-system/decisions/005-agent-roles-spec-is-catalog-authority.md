# Agent Roles Spec Is Catalog Authority

Date: 2026-06-03

Status: Partially superseded by
[006-agent-roles-spec-owns-roles-store.md](006-agent-roles-spec-owns-roles-store.md).
This decision remains authority that production role content and catalog
governance live in `agent-roles-spec`, not `cc-bridge_source`. Decision 006 changes
the long-term owner of the local `.roles` package store and role payload
install/update semantics from CC_BRIDGE to `agent-roles-spec`.

## Context

The first CC_BRIDGE Role Pack slice placed a role package under the CC_BRIDGE source tree
as `roles/cc-bridge.archi`. That was useful for proving manifest parsing, install,
project binding, role memory, skill projection, and tool hooks, but it makes
CC_BRIDGE itself the role library.

That is the wrong long-term boundary. `agent-roles-spec` is the RolePack
specification and role-library project. CC_BRIDGE should be one host that consumes
that library through a CC_BRIDGE adapter. CC_BRIDGE should not vendor role package content
inside its own source tree.

## Decision

`agent-roles-spec` is the catalog authority for CC_BRIDGE role packages.

CC_BRIDGE owns:

- role catalog discovery and refresh
- install/update commands
- the local installed-role store
- project role locks
- CC_BRIDGE config binding
- provider-home projection
- ask alias, sidebar, diagnostics, reload, and refresh behavior

`agent-roles-spec` owns:

- role package source content
- role ids, versions, README files, memory, skills, prompts, tools, plugins,
  and host adapter metadata
- role contribution governance
- spec, schema, templates, reference roles, and production-ready role catalog

The CC_BRIDGE source tree must not contain installable role package directories such
as `roles/<role-id>`. Existing CC_BRIDGE source-tree roles are temporary migration
artifacts and should be removed after CC_BRIDGE can install from
`agent-roles-spec`.

## Update Semantics

During `cc-bridge update`, CC_BRIDGE should refresh the `agent-roles-spec` catalog before
role update decisions.

If an installed role has a newer version or digest in `agent-roles-spec`, CC_BRIDGE
should update that installed role as part of the CC_BRIDGE update flow, subject to
the same trust and tool-policy rules as `cc-bridge roles update`.

If `agent-roles-spec` contains roles that are not installed locally, CC_BRIDGE should
show the newly available role ids, versions, and short descriptions, then ask
whether to install them into the local CC_BRIDGE role store.

Project locks must not silently float just because the installed store is
updated. Updating the user-level installed role store may make a project lock
stale; adopting the new role version in a project remains an explicit project
operation such as `cc-bridge roles refresh --apply-lock` or a future project role
update command.

## Catalog Location

The first CC_BRIDGE implementation may resolve the catalog from:

1. user-level system role libraries at `~/.cc-bridge/roles` and `~/.roles`
2. `CC_BRIDGE_AGENT_ROLES_SPEC_HOME` or `AGENT_ROLES_SPEC_HOME`
3. a default local clone such as `~/yunwei/agent-roles-spec`
4. a CC_BRIDGE-owned GitHub cache cloned from
   `https://github.com/SeemSeam/agent-roles-spec` under
   `$XDG_CACHE_HOME/cc-bridge/role-catalogs/agent-roles-spec`

Additional configured local sources in the CC_BRIDGE role source registry are loaded
after the default sources and must not silently shadow earlier role ids.

The catalog resolver should report the chosen path and whether it is current,
missing, stale, or unreadable. It should not silently fall back to CC_BRIDGE
source-tree roles.

The CC_BRIDGE-owned GitHub cache is a read-only consumption cache from CC_BRIDGE's point of
view. Users who want to modify production role content should submit changes to
the upstream `agent-roles-spec` GitHub repository by pull request, then let CC_BRIDGE
refresh or reinstall from the accepted catalog content.

User-level system role libraries are local editable sources. When such a role
is added to a project, CC_BRIDGE snapshots it into the installed role store and locks
the project to that digest; project-level `.roles` directories are deferred for
the first implementation slice.

## Consequences

- CC_BRIDGE releases do not carry role package content.
- New roles can appear in `agent-roles-spec` without changing CC_BRIDGE source.
- CC_BRIDGE update can make installed roles current and can prompt users to install
  newly published roles.
- Role package governance moves to `agent-roles-spec`.
- CC_BRIDGE tests need fixtures for role packages, but those fixtures must be test
  fixtures or generated temporary directories, not the production role catalog.
- Built-in role fallback should be replaced by catalog lookup and installed
  role store lookup.

# Role Packs Are Host Neutral With Adapters

Date: 2026-06-01

## Context

The roles concept should grow beyond CC_BRIDGE. If the manifest directly assumes
tmux, `.cc-bridge`, Codex home paths, or CC_BRIDGE reload behavior, other hosts cannot
reuse the package. At the same time, CC_BRIDGE needs concrete adapter behavior for
config, projection, and diagnostics.

## Decision

Role Packs have a host-neutral core manifest and optional host/provider
adapters. The core defines identity, responsibilities, assets, compatibility,
permissions, and tool lifecycle hooks. CC_BRIDGE-specific behavior belongs in CC_BRIDGE
adapter fields or files.

## Consequences

- Other hosts can implement the same Role Pack model.
- CC_BRIDGE can still provide first-class commands and projection behavior.
- Provider-specific skill formats remain isolated under provider directories.
- The spec must clearly separate core required fields from adapter-specific
  extensions.


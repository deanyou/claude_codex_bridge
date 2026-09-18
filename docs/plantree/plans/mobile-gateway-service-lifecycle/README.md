# Mobile Gateway Service Lifecycle Plan

Date: 2026-07-01

## Purpose

Make CC_BRIDGE Mobile gateway startup idempotent and host-owned. Re-running
`cc-bridge update mobile` should refresh or replace the single CC_BRIDGE-managed background
mobile gateway instead of failing because the previous gateway still owns
`127.0.0.1:8787`.

The gateway must remain loopback-only. Public exposure through Tailscale Serve,
Cloudflare Tunnel, or another route provider remains a separate route layer.

## File Map

- [roadmap.md](roadmap.md): implementation phases and release gate.
- [topics/unique-background-service.md](topics/unique-background-service.md):
  observed issue, target lifecycle contract, state files, replacement flow,
  command changes, and validation plan.

## Related Sources

- [../../../mobile-cloudflare-alpha.md](../../../mobile-cloudflare-alpha.md)
- [../../../mobile-cloudflare-alpha.zh.md](../../../mobile-cloudflare-alpha.zh.md)
- [../../baseline/runtime-flows.md](../../baseline/runtime-flows.md)
- [../../baseline/storage-and-state.md](../../baseline/storage-and-state.md)

## Scope

In scope:

- A host-wide CC_BRIDGE-owned mobile gateway service manager.
- Exactly one CC_BRIDGE-managed server-wide mobile gateway per host state directory.
- Idempotent `cc-bridge update mobile` behavior that stops/replaces the previous
  managed gateway and waits for the new one to become healthy.
- Stale pid/state cleanup.
- Clear refusal when `127.0.0.1:8787` is occupied by a non-CC_BRIDGE process.
- Tests for replacement, stale state, external port occupancy, and lock
  behavior.

Out of scope for the first slice:

- Managing Tailscale Serve or Cloudflare Tunnel processes.
- Killing unknown processes that happen to use the same port.
- Changing CC_BRIDGE Mobile API routes or pairing/token semantics.
- Replacing project-scoped `cc-bridge mobile serve` as a foreground debugging command.

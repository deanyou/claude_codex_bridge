# Decision 020: Source Monorepo Authority For Mobile Code

Date: 2026-07-02
Status: Accepted

## Context

CC_BRIDGE Mobile was being maintained in two editable locations:

- `/home/bfly/yunwei/cc-bridge_mobile/app` plus its local mobile docs/tools;
- `/home/bfly/yunwei/cc-bridge_source/mobile/app` plus source-side mobile gateway
  code under `/home/bfly/yunwei/cc-bridge_source/lib/mobile_gateway`.

That split repeatedly caused drift:

- scanner fixes landed in the standalone mobile checkout but were missing from
  source-built release APKs;
- app-side chat, notification, and transcript changes had to be copied between
  trees by hand;
- emulator validation and release packaging could accidentally use different
  code from the code that was just fixed.

The user explicitly chose the monorepo direction over continuing dual-repo
development.

## Decision

`/home/bfly/yunwei/cc-bridge_source/mobile/` is the only authoritative mobile code
surface.

Boundaries:

- Flutter app source lives at `cc-bridge_source/mobile/app/`;
- mobile docs/plan tree live at `cc-bridge_source/mobile/docs/`;
- mobile helper tools live at `cc-bridge_source/mobile/tools/`;
- gateway/runtime source continues to live at `cc-bridge_source/lib/mobile_gateway/`
  and related source modules.

The legacy `/home/bfly/yunwei/cc-bridge_mobile` checkout is retired as an
implementation surface. It may keep only migration notes or thin
compatibility shims, but it must not remain a second editable copy of the
mobile app/docs/tools.

## Consequences

- APK builds, emulator validation, and release packaging must run from
  `cc-bridge_source/mobile/app`.
- Any change made first in the retired standalone checkout is incomplete until
  it is moved into `cc-bridge_source/mobile/`; the preferred workflow is to stop
  editing there altogether.
- Historical evidence that mentions the old standalone path remains valid as
  historical evidence and does not need backfilled rewriting.

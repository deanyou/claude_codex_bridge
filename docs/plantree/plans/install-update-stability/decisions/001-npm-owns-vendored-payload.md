# Decision 001: npm Owns Its Vendored Payload

Date: 2026-07-22

Status: accepted

## Context

The npm runner pins `.cc-bridge-release` to the outer `@seemseam/cc-bridge` manifest and
checks exact version equality on every invocation. The Python tarball updater
previously treated that inner release like a standalone install. Updating it
in place changed the inner `VERSION` but not the npm manifest, so the next
runner invocation restored the older manifest-pinned payload and the startup
update prompt repeated.

## Decision

- npm is the only writer of an npm package's `.cc-bridge-release` payload.
- The runner explicitly attests package name, package root, and manifest
  version to the Python child.
- Python validates the outer manifest and requires its executing root to be
  below the attested `.cc-bridge-release` directory before accepting npm ownership.
- Ordinary `cc-bridge update` in that context prints
  `npm install -g @seemseam/cc-bridge@<target>` and exits successfully without
  mutating the payload.
- Startup update acceptance displays the same command, defers the current
  version prompt window, and does not relaunch.
- The npm runner keeps strict manifest/payload version equality. It must not
  accept a newer inner payload or maintain a second mutable version stamp.
- `cc-bridge update rich` and `cc-bridge update mobile` remain separate explicit feature
  lifecycle commands and are not redirected.

## Consequences

There is one update authority per install mode. npm installations use npm;
release-package and source/dev installations retain the transactional CC_BRIDGE
tarball updater. A forged or stale environment marker cannot claim another
install because provenance validation fails closed to the normal path.

This decision supersedes the README v7 rule that every post-install update
uses the same `cc-bridge update` mutation path.

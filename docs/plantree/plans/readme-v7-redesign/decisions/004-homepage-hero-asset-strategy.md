# Homepage Hero Asset Strategy

Date: 2026-06-12

## Context

The homepage polish pass introduced `assets/cc-bridge-promo.png`, a generated
annotated promotional screenshot. Reviewer1 identified this as a blocking
pre-implementation choice because the current asset was larger than the
existing README screenshots, contained embedded annotations, and did not fit
cleanly with the existing language-specific README media pattern.

Maintainer follow-up on 2026-06-13 changed the visual direction: the public
README should use the newer generated promo composition, not the older
`cc-bridge-test2-terminal-annotated*.png` copy. The language-specific canonical asset
policy still applies.

Relevant files:

- `assets/cc-bridge-promo.png`
- `assets/readme_v7/cc-bridge-test2-terminal-annotated.png`
- `assets/readme_v7/cc-bridge-test2-terminal-annotated-en.png`
- [../topics/homepage-showcase-polish.md](../topics/homepage-showcase-polish.md)
- [../history/reviewer1-homepage-polish-2026-06-12.md](../history/reviewer1-homepage-polish-2026-06-12.md)

## Decision

Public READMEs should use canonical language-specific hero assets under
`assets/readme_v7/`.

Planned names:

- `assets/readme_v7/cc-bridge-hero-zh.png` for `README_zh.md`
- `assets/readme_v7/cc-bridge-hero-en.png` for `README.md`

The current canonical pair should be derived from the newer generated promo
composition:

- `assets/readme_v7/cc-bridge-hero-zh.png`: Chinese promo-style hero
- `assets/readme_v7/cc-bridge-hero-en.png`: English promo-style hero

`assets/cc-bridge-promo.png` remains the source/reference/social asset. Public
READMEs should continue to reference the language-specific canonical assets
under `assets/readme_v7/`, not `assets/cc-bridge-promo.png` directly.

## Consequences

- README implementation patches must generate or optimize the canonical hero
  images before changing README references.
- The first-screen hero may reuse the `assets/cc-bridge-promo.png` composition, but
  final assets must live under `assets/readme_v7/` and handle Chinese/English
  parity explicitly.
- Existing `cc-bridge-test2-terminal-annotated*.png` assets remain fallback/history
  assets, not the homepage hero default.
- README headers should reduce the current badge set to at most four visible
  badges, preferably version, platform, and providers.
- If the hero is strongly annotated, the UI Tour should avoid repeating another
  large screenshot before Quick Start.

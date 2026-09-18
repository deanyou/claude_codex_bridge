# CC_BRIDGE Development Tools

This directory contains maintainer-only tools for developing and releasing CC_BRIDGE.

`dev_tools/` is intentionally excluded from official release artifacts by
`scripts/build_release.py`. The exclusion is covered by
`test/test_build_linux_release_script.py`, so these files can be versioned in
git without being shipped to users.

Keep user-facing runtime code, installer code, and packaged assets outside this
directory. Tools here may support release, CI, documentation, or repository
maintenance work only.

Current tools:

- `skills/cc-bridge-github/`: local Codex skill for release and GitHub surface audits.
  The skill may guide the agent through commit, push, default-branch merge,
  tag, release, workflow, and artifact verification steps. Its bundled checker
  remains read-only.

## Using Local Skills

To make a development skill available to Codex, copy or symlink it into the
active Codex skills directory:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
ln -sfn "$PWD/dev_tools/skills/cc-bridge-github" "${CODEX_HOME:-$HOME/.codex}/skills/cc-bridge-github"
```

The `cc-bridge-github` checker can also be run directly from the repo root:

```bash
python dev_tools/skills/cc-bridge-github/scripts/check_release_state.py --phase dev --wait-seconds 900
python dev_tools/skills/cc-bridge-github/scripts/check_release_state.py --phase prepare
python dev_tools/skills/cc-bridge-github/scripts/check_release_state.py --phase published
```

## Maintenance Rules

- Keep development tools read-only by default.
- Document any tool that can mutate git, GitHub releases, or user-visible files.
- Add or update release-exclusion tests when adding top-level development-only directories.
- Do not depend on `.cc-bridge/` for versioned developer tooling; `.cc-bridge/` is project runtime state.

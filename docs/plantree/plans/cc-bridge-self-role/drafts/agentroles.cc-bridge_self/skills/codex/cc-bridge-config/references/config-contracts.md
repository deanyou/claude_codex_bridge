# CC_BRIDGE Config Contracts

Use this reference for private `agentroles.cc-bridge_self` config work.

## Authority

- Config precedence is built-in default, then user `~/.cc-bridge/cc-bridge.config`, then
  project `.cc-bridge/cc-bridge.config`.
- `.cc-bridge/cc-bridge.config` is the normal project topology/config authority on disk.
- Disk config is intent, not live graph. The mounted daemon graph becomes live
  authority only after a successful reload/start and recheck.
- `.cc-bridge_config/cc-bridge.config` is legacy migration evidence only.

## Validation And Reload

Every edit requires:

```bash
cc-bridge config validate
```

Every reload requires a preceding no-mutation plan:

```bash
cc-bridge reload --dry-run
```

`cc-bridge reload` may run only after validation passes, dry-run is reviewed, the plan
is supported, and the user asked to materialize the change. Reload does not
prove already running provider processes picked up new startup inputs.

## Windows Topology

Prefer:

```toml
version = 2
entry_window = "main"

[windows]
main = "main:codex, rich"
ops = "agentroles.cc-bridge_self:codex"
```

Rules:

- `[windows]` defines the configured-agent set.
- `[windows]` is the authority for provider and default workspace mode.
- Each agent leaf appears exactly once.
- `cmd` is not valid inside `[windows]` topology.
- `[agents.<name>]` tables are overlays for names referenced in `[windows]`;
  do not repeat `provider`, `workspace_mode = "inplace"`, or
  `workspace_mode = "git-worktree"` there.
- Stale `[agents.<name>]` tables are residue when the name is no longer in
  `[windows]`; `cc-bridge config validate` reports them as style warnings.

## Role Bindings

- Use canonical role ids such as `agentroles.archi` and
  `agentroles.cc-bridge_self`.
- Shorthand `agentroles.cc-bridge_self:codex` resolves to the role manifest default
  agent name when installed.
- Explicit binding may use a local name:

```toml
[windows]
ops = "cc-bridge_self:codex"

[agents.cc-bridge_self]
role = "agentroles.cc-bridge_self"
```

If the role is missing, tell the user to run `cc-bridge roles install <role-id>`.
Do not copy role assets into `.cc-bridge` by hand.

## Provider/API Fallbacks

Use only existing configured fallbacks or user-supplied safe references such as
environment variable names, provider profiles, model names, or base URLs.
Never read, print, store, obtain, scrape, borrow, or use credential values.

Provider/startup-affecting changes require post-reload affected-agent recheck.
If a running provider process still reflects old inputs, hand the target to
`cc-bridge-self-recover` for guarded single-agent restart when supported.

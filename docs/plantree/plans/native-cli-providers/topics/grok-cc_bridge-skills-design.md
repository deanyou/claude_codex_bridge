# Grok CC_BRIDGE Skills Design

Date: 2026-07-11

## Goal

Give every CC_BRIDGE-managed Grok instance native, instance-local `ask` and
`cc-bridge-clear` skills that work in visible TUI and managed ask execution without
sharing another provider's home. Normal CC_BRIDGE startup follows the shared
auto-permission policy; safe startup remains interactive.

The design covers skill content, projection ownership, caller identity,
permission policy, failure behavior, and acceptance. It does not change Grok's
provider-native completion authority.

## Package Shape

Add exactly two Grok-native skill packages:

```text
inherit_skills/grok_skills/
  ask/
    SKILL.md
  cc-bridge-clear/
    SKILL.md
```

Do not add scripts, references, assets, or `agents/openai.yaml`. Both workflows
are short CLI contracts; the CC_BRIDGE commands already own parsing, validation,
artifacts, routing, and clear behavior. Grok ignores Codex UI metadata, so it
must not be copied into the Grok package.

Each `SKILL.md` frontmatter contains only `name` and `description`. Runtime
permission is CC_BRIDGE launcher policy, not skill metadata.

## Ask Skill Contract

Name and trigger description:

```yaml
---
name: ask
description: Delegate work or request information from another CC_BRIDGE-managed agent using ask. Use when the user asks Grok to ask, delegate to, hand off to, consult, or send work to a named CC_BRIDGE agent, or when project memory requires CC_BRIDGE collaboration.
---
```

Body requirements:

1. Decide whether delegation is actually required.
2. Select result intent before invoking the command:
   `--silence`, `--compact`, plain `ask`, or `--chain`, with artifact flags
   remaining orthogonal.
3. Use `--chain` when the current active CC_BRIDGE task needs the child result; use
   `--silence` for independent no-result work. Do not issue a plain nested ask
   from an active task.
4. Send the request body through a quoted heredoc:

   ```bash
   command ask [FLAGS...] "$TARGET" <<'EOF'
   $MESSAGE
   EOF
   ```

5. Submit once, then stop. Do not run `ask get`, `pend`, `watch`, or `ping`
   unless the user explicitly requested diagnostics.
6. Do not append completion markers or output-policy text. CC_BRIDGE owns reply
   guidance, artifacts, continuation routing, and Grok native completion.
7. If terminal permission is denied or cancelled, report the request as not
   submitted. Do not toggle always-approve, edit Grok permission config, or
   claim success.
8. If `--chain` is rejected because no active parent exists, retry once with
   plain `ask` only when the user requested independent delegation.

The Grok template should preserve the shared ask decision-card assertions in
`test/test_ask_skill_templates.py`; provider-specific wording may be added only
for permission failure and native completion boundaries.

## CC_BRIDGE Clear Skill Contract

Name and trigger description:

```yaml
---
name: cc-bridge-clear
description: Clear conversation context for one or more mounted CC_BRIDGE agents using cc-bridge clear. Use when the user invokes /cc-bridge-clear, $cc-bridge-clear, or $cc-bridge_clear, or asks Grok to clear or reset CC_BRIDGE agent context without restarting agents or deleting project state.
---
```

Body requirements:

1. Preserve explicit scope:
   - bare `/cc-bridge-clear`, `$cc-bridge-clear`, or `$cc-bridge_clear`, and explicit all-agents
     requests: `command cc-bridge clear`;
   - named agents: pass only those names as separately shell-quoted arguments;
   - ambiguous natural-language scope without a direct skill invocation: ask
     for the target instead of clearing every agent.
2. Explain only operationally relevant behavior: clear sends provider-native
   clear input to mounted target panes and does not delete `.cc-bridge`, auth,
   sessions, logs, workspaces, or memory files.
3. Never substitute `cc-bridge kill`, `cc-bridge -n`, `restart`, direct tmux input, or file
   deletion.
4. Run once, report the command output, then stop. Do not poll.
5. On permission denial or cancellation, report that no clear was performed.
   Do not change Grok permission mode.
6. In the `cc-bridge_source` checkout, retain the existing source/runtime isolation
   warning: installed `cc-bridge` is for the active collaboration environment;
   source validation uses the absolute external `cc-bridge_test` wrapper.

## Native Projection Contract

For agent `<agent>`, project the packages to:

```text
.cc-bridge/agents/<agent>/provider-state/grok/home/.grok/skills/ask/SKILL.md
.cc-bridge/agents/<agent>/provider-state/grok/home/.grok/skills/cc-bridge-clear/SKILL.md
```

Projection rules:

- Project each skill directory independently. Do not replace or symlink the
  entire `.grok/skills` directory because Grok owns bundled skills there.
- Use CC_BRIDGE projection markers beside each managed skill directory so refresh
  and removal are idempotent and ownership is inspectable.
- Refresh during provider workspace preparation, visible launcher command
  construction, and per-job headless environment construction.
- `inherit_skills = false` removes only the two CC_BRIDGE-owned skill directories and
  markers. Preserve auth, config, sessions, logs, bundled skills, and unrelated
  user-created skills.
- A conflicting unmarked `ask` or `cc-bridge-clear` directory in the managed home is
  a diagnostic conflict. Do not silently delete unknown content.
- Storage inventory classifies the two managed skill paths and markers as
  projected configuration; other `.grok/skills` content keeps its provider
  state classification.

## Caller Identity Contract

Visible Grok already receives caller context from the launcher. Headless Grok
must receive an equivalent per-agent caller environment built from its session
payload:

```text
CC_BRIDGE_CALLER_ACTOR=<agent>
CC_BRIDGE_CALLER_RUNTIME_DIR=<agent grok runtime dir>
CC_BRIDGE_CALLER_PROJECT_ROOT=<project root>
CC_BRIDGE_CALLER_PROJECT_ID=<project id>
CC_BRIDGE_SESSION_ID=<agent launch session id>
```

Source-test PATH routing from `caller_context_env()` must also be preserved so
skill commands use the external project's source wrapper rather than the
installed release. Do not inherit caller identity from the `cc-bridge-daemon` parent
process; that can attribute Grok delegation to the wrong agent or project.

## Permission Contract

Skill discovery does not grant terminal permission. CC_BRIDGE must keep permission
policy separate from skill content.

Normal start with auto permission enabled:

- Add Grok CLI `--permission-mode bypassPermissions`, matching the native
  highest-permission startup used for other auto-permission providers.
- When `inherit_skills = true`, also add allow rules matching the exact skill
  command prefixes:
  - `Bash(command ask *)`
  - `Bash(command cc-bridge clear*)`
- Persist the effective skill-command permission bit in the Grok session
  payload, together with the auto-permission bit, so daemon recovery retains
  the same start policy.

Safe start with auto permission disabled:

- Do not append bypass mode or either allow rule.
- Visible TUI asks the user for approval.
- Tool execution may be cancelled; CC_BRIDGE must not pretend the skill command ran.

Additional rules:

- `inherit_skills = false` disables projection and CC_BRIDGE-added allow rules, but
  does not override the normal auto-permission startup policy.
- User/enterprise deny rules and hooks always win.
- Do not add a general `Bash` allow or rewrite permission files.
- Skill instructions cannot override permission policy.

## Runtime And Completion Behavior

- The skill command's exit status determines whether submission or clear was
  accepted; skill prose is not execution evidence.
- For `ask`, the child CC_BRIDGE job follows normal CC_BRIDGE async/chain semantics.
- The outer Grok job still completes only from provider-native Grok terminal
  evidence. Skill output, child completion, process exit, `CC_BRIDGE_DONE`, and CC_BRIDGE
  turn text are not Grok completion authority.
- `cc-bridge-clear` does not wait for semantic provider output beyond the CC_BRIDGE command
  result. It reports the returned per-target clear status and stops.

## Failure Behavior

| Condition | Required result |
| :--- | :--- |
| Skill source missing | Remove stale managed projection; report projection unavailable in diagnostics. |
| Unmarked conflicting skill directory | Preserve it and report ownership conflict. |
| Terminal permission denied/cancelled | No success claim; outer Grok result is blocked/incomplete according to native end reason. |
| Wrong or missing caller context | Reject acceptance; do not fall back to another project or agent identity. |
| Unknown ask/clear target | Return CC_BRIDGE validation error; do not retarget automatically. |
| `cc-bridge -s` headless command | Permission remains interactive/unavailable; do not bypass safe-start policy. |
| Child ask submitted | Stop; do not poll unless diagnostics were explicitly requested. |

## Test Matrix

Skill content:

- Grok `ask` participates in the shared ask-template contract.
- Both files have valid Grok frontmatter, concise descriptions, ASCII content,
  quoted command examples, and no broad permission instructions.
- `cc-bridge-clear` contains all/named/ambiguous scope rules and forbids kill,
  restart, direct tmux input, and state deletion.

Projection and storage:

- Enabled projection creates both instance-local paths and markers.
- Repeated materialization is idempotent.
- Disabled inheritance removes only marked CC_BRIDGE skill paths.
- Conflicting unmarked paths are preserved and diagnosed.
- Bundled Grok skills, auth, config, sessions, and logs survive enable/disable.
- Storage classification distinguishes CC_BRIDGE-managed skill paths from Grok-owned
  bundled skills.

Launcher and execution:

- Normal start adds bypass mode exactly once and each skill allow rule exactly
  once when projection is enabled.
- Safe start adds neither bypass mode nor skill rules; `inherit_skills = false`
  suppresses the skill rules without suppressing normal bypass mode.
- Headless env binds the correct agent, runtime, project, session, and
  source-test PATH.
- `grok1` and `grok2` never share skill paths, caller identity, or completion
  artifacts.

Real acceptance in `/home/bfly/yunwei/test_ccb2`:

1. `grok inspect --json` reports both skills from each managed home.
2. Normal-start headless `grok1` uses `ask --silence` to submit to `grok2`
   without an interactive permission prompt; target and sender are exact.
3. Safe-start headless invocation is cancelled/incomplete without executing
   the child command.
4. Visible safe-start invocation succeeds only after explicit approval.
5. Grok invokes `cc-bridge-clear` for one named test agent; no other pane receives
   clear input, and post-clear asks still route correctly.
6. `inherit_skills = false` removes both discoveries and both CC_BRIDGE-added allow
   rules while preserving unrelated Grok state.
7. Restart one Grok instance and repeat ask plus clear attribution checks.

## Non-Goals

- Do not create a combined `cc-bridge` skill.
- Do not expose diagnostics polling as normal ask behavior.
- Do not let skill content toggle or rewrite Grok permission policy.
- Do not use global Claude/Codex skill compatibility as Grok's CC_BRIDGE skill
  source.
- Do not change Grok provider-native result collection or turn-end authority.

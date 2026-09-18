# CC_BRIDGE Adapter Notes For Coder

Use only the assigned project workspace and CC_BRIDGE-visible instructions. Do not
edit task indexes, status, `current_loop`, runtime topology, provider state, or
tmux state directly.

Do not run `cc-bridge`, `cc-bridge_test`, `cc-bridge plan`, `cc-bridge loop`, plain `cc-bridge ask`, or
workflow wrappers. The sole exception is exactly one literal assigned-review
chain per bounded review hop: `command ask --chain --artifact-reply <assigned-reviewer>`.
It may only target the same assigned Reviewer and must carry node id, workgroup id, visible
workspace identity, allowed paths, acceptance refs, verification refs/results,
changed paths, and blockers. Never use `--silence`, another target, polling,
controller commits, integration, authority writes, or agent release. The
supervisor/runner owns task authority, artifact import, runtime capacity, and
cleanup. Return implementation evidence for script-owned import or reviewer
inspection.

The only Coder terminal status enum is `done|blocked|needs_rework`.

The canonical node work packet and declared refs are the complete semantic
input. Do not inspect sibling packets, change allowed paths, submit downstream
asks, create authority commits, or integrate results. Provider and model
selection remain project configuration concerns. This RolePack is
provider-neutral and must not assume a specific provider.

# CC_BRIDGE Sidebar Review Request

Please review the current CC_BRIDGE sidebar changes. Do not edit files.

Scope:
- Window tree: one sidebar per managed window, stable across window switches.
- Agent status: symbol plus color for active, pending, idle, failed, offline.
- Comms feed: business ask rows, not raw job rows.
- Reply delivery jobs are folded into the source ask row.
- Comms shows original ask preview through `body_preview`.
- Comms short labels: `send`, `work`, `back`, `done`, `fail`.
- Sidebar colors only the short status label.
- Normal terminal rows hide routine reasons like `hook_stop` and `task_complete`.
- Phase 1 is single-project only and deeply coupled to `cc-bridge-daemon`.

Return only the top 5 practical improvements.

For each item include:
- priority
- reason
- implementation hint
- risk or boundary

Focus on:
- narrow sidebar readability
- Comms information density
- color/status semantics
- cross-window behavior
- ProjectView field design

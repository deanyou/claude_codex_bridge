# Capacity Boundary

This file is a historical design reference, not an active provider command
surface. It is not projected as an active provider skill. Do not run CC_BRIDGE commands
from this reference.

The orchestrator is reply-only. It may describe capacity intent, route choice,
blocking reason, and evidence. The runner owns command execution, capacity
changes, task status, artifact imports, runtime files, and cleanup.

Any capacity facts shown to the orchestrator are evidence only. The
orchestrator must not treat evidence as permission to mutate project authority,
invoke CC_BRIDGE wrappers, invoke provider commands, choose placement, call tmux, or
create/release agents directly.

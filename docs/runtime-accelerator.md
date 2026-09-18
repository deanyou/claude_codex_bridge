# Runtime accelerator switches

This repository keeps the Python `.cc-bridge` runtime as the owner of public CLI, socket protocol, dispatcher, mailbox, lifecycle, and Codex hooks. The Rust `cc-bridge-runtime-accelerator` is a local sidecar for hot paths only.

Official release artifacts build and include `bin/cc-bridge-runtime-accelerator`.
Source checkouts can build it with `bin/build-cc-bridge-runtime-accelerator`; when
the binary is missing, Python falls back to the legacy Codex observation path.
When cc-bridge-daemon starts the sidecar, it records exact PID, cwd, argv, executable,
socket, and process-start-token ownership. Linux resolves that evidence through
`/proc`; macOS uses `ps` plus the executable and cwd mappings reported by
`lsof` while retaining the same fail-closed identity checks.
Socket arguments are compared by canonical path so platform aliases such as
macOS `/tmp` and `/private/tmp` identify the same owned Unix socket.

## Python/Rust switch controls

| Variable | Default | Effect | Review note |
| --- | --- | --- | --- |
| `CC_BRIDGE_RUNTIME_ACCELERATOR_CODEX` | enabled when unset | Set `0`, `false`, `no`, `off`, or `disabled` to force the legacy Python Codex polling path. | Main Python/Rust module switch. |
| `CC_BRIDGE_RUNTIME_ACCELERATOR_BIN` | `cc-bridge-runtime-accelerator` lookup | Override the Rust sidecar binary path. | Packaging can wire this to an installed binary. |
| `CC_BRIDGE_RUNTIME_ACCELERATOR_SOCKET` | `<project>/.cc-bridge/runtime-accelerator/accelerator.sock`, or a short runtime socket root when the project path is too long for Unix sockets | Override sidecar Unix socket. | Useful for smoke tests and staged rollout. |
| `CC_BRIDGE_RUNTIME_ACCELERATOR_TIMEOUT_S` | `0.2` | Sidecar RPC timeout before falling back to Python polling. | Failure is non-fatal. |
| `CC_BRIDGE_RUNTIME_ACCELERATOR_STARTUP_TIMEOUT_S` | `0.5` | Startup wait for cc-bridge-daemon-managed sidecar. | Missing binary records fallback action. |
| `CC_BRIDGE_BRIDGE_IDLE_SLEEP` | `1.0` | Codex bridge FIFO wait timeout; set `0.05` to restore legacy low-latency idle polling for diagnostics. | FIFO messages still wake through the persistent reader. |
| `CC_BRIDGE_CODEX_BIND_POLL_INTERVAL` | `5.0` | Codex session/log binding follow interval; set `0.5` to restore legacy follow cadence. | Does not disable binding follow. |
| `CC_BRIDGE_CC_BRIDGE_DAEMON_IDLE_FULL_HEARTBEAT_INTERVAL_S` | `30.0` | Idle full-maintenance interval for cc-bridge-daemon. | Active jobs/queues still run full maintenance immediately. |

## Rollback

Use `CC_BRIDGE_RUNTIME_ACCELERATOR_CODEX=0` to bypass the Rust Codex observation path without disabling Codex hooks. Existing Python behavior remains the fallback for unavailable sidecar, timeout, malformed response, per-job error, or unknown item kind.

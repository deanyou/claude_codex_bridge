from __future__ import annotations

from dataclasses import replace

from agents.models import RuntimeBindingSource

from ..common import ACTIVE_RUNTIME_STATES, fallback_workspace_path


def restore_attachment_kwargs(*, layout, spec, runtime) -> dict[str, object]:
    return {
        "agent_name": spec.name,
        "workspace_path": fallback_workspace_path(layout=layout, spec=spec, runtime=runtime),
        # Always use the spec's runtime_mode as the authoritative source for backend_type.
        # The restored runtime may have backend_type="pane-backed" from a previous run where
        # the spec said pane-backed, but if the spec has been updated to "headless" (e.g.
        # peri/pi sub-agents), the restored context must reflect the current spec so that
        # should_start_execution() returns True for headless agents.
        "backend_type": spec.runtime_mode.value,
        "pid": runtime.pid if runtime is not None else None,
        "runtime_ref": runtime.runtime_ref if runtime is not None else None,
        "session_ref": runtime.session_ref if runtime is not None else None,
        "slot_key": runtime.slot_key if runtime is not None else spec.name,
        "window_id": runtime.window_id if runtime is not None else None,
        "workspace_epoch": runtime.workspace_epoch if runtime is not None else None,
        "binding_source": (
            runtime.binding_source if runtime is not None else RuntimeBindingSource.PROVIDER_SESSION
        ),
    }


def touch_active_runtime(*, registry, runtime, timestamp: str, health: str | None = None):
    def _update(current):
        base = current or runtime
        return replace(
            base,
            last_seen_at=timestamp,
            health=health if health is not None else base.health,
        )

    updated_runtime = registry.update(runtime.agent_name, _update)
    if updated_runtime is not None:
        return updated_runtime
    fallback = replace(
        runtime,
        last_seen_at=timestamp,
        health=health if health is not None else runtime.health,
    )
    return registry.upsert(fallback)


def runtime_is_active(runtime) -> bool:
    return runtime is not None and runtime.state in ACTIVE_RUNTIME_STATES


__all__ = ["restore_attachment_kwargs", "runtime_is_active", "touch_active_runtime"]

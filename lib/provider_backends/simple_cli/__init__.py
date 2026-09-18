from __future__ import annotations

from provider_core.contracts import ProviderBackend

from .launcher import build_runtime_launcher
from .manifest import build_manifest
from .session import build_session_binding


def build_backend(provider: str) -> ProviderBackend:
    return ProviderBackend(
        manifest=build_manifest(provider=provider),
        session_binding=build_session_binding(provider=provider),
        runtime_launcher=build_runtime_launcher(provider=provider),
    )


__all__ = ['build_backend']

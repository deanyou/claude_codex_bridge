from __future__ import annotations

from provider_core.contracts import ProviderRuntimeLauncher

from provider_backends.native_cli_support import (
    NativeCliLaunchConfig,
    build_native_cli_runtime_launcher,
)


def build_runtime_launcher(*, provider: str) -> ProviderRuntimeLauncher:
    """Build a simple tmux-based runtime launcher for CLI agents."""
    config = NativeCliLaunchConfig(provider=provider)
    return build_native_cli_runtime_launcher(config)


__all__ = ['build_runtime_launcher']

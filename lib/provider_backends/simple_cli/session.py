from __future__ import annotations

from provider_backends.native_cli_support import build_native_session_binding
from provider_core.contracts import ProviderSessionBinding


def build_session_binding(*, provider: str) -> ProviderSessionBinding:
    """Build a session binding for simple CLI agents.

    Uses the native_cli session binding which tracks the session via
    a session file in the workspace.
    """
    return build_native_session_binding(
        provider=provider,
        session_filename=f'.{provider}-session',
    )


__all__ = ['build_session_binding']

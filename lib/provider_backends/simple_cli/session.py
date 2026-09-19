from __future__ import annotations

from provider_backends.native_cli_support import build_native_session_binding
from provider_core.contracts import ProviderSessionBinding
from provider_core.pathing import PROVIDER_SESSION_FILENAMES


def build_session_binding(*, provider: str) -> ProviderSessionBinding:
    """Build a session binding for simple CLI agents.

    Uses the native_cli session binding which tracks the session via
    a session file in the workspace. Maps provider to the correct session filename.
    """
    normalized = str(provider or '').strip().lower()
    session_filename = PROVIDER_SESSION_FILENAMES.get(normalized, f'.{provider}-session')
    return build_native_session_binding(
        provider=provider,
        session_filename=session_filename,
    )


__all__ = ['build_session_binding']

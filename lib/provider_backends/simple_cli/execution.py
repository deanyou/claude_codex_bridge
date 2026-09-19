"""
Execution adapter for simple CLI providers like ccb.

Supports both pane-backed and headless execution modes.
"""
from __future__ import annotations

import os
from pathlib import Path

from provider_core.contracts import ProviderExecutionAdapter

from provider_backends.native_cli_support import (
    NativeCliExecutionConfig,
    NativeCliExecutionRequest,
    NativeCliSubprocessAdapter,
    observe_stdout_output,
)
from provider_core.pathing import PROVIDER_SESSION_FILENAMES


# Environment variable to control execution mode
SIMPLE_CLI_EXECUTION_MODE_ENV = "CC_BRIDGE_SIMPLE_CLI_EXECUTION_MODE"
SIMPLE_CLI_HEADLESS_MODE = "headless"
SIMPLE_CLI_PANE_MODE = "pane"


class SimpleCliExecutionAdapter:
    """Execution adapter that supports both pane and subprocess modes."""
    
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.pane_mode = SIMPLE_CLI_PANE_MODE
        self._pane_adapter = None
        self._headless_adapter = None

    @property
    def pane_adapter(self):
        if self._pane_adapter is None:
            # Import here to avoid circular imports
            from provider_backends.pi.pane_execution import PiPaneExecutionAdapter
            
            # Use Pi's pane adapter as base but with our provider name
            self._pane_adapter = PiPaneExecutionAdapter(
                provider=self.provider,
                pane_mode=SIMPLE_CLI_PANE_MODE,
                terminal_event_type="agent_settled",
                terminal_authority="simple_cli_agent_settled",
            )
        return self._pane_adapter

    @property
    def headless_adapter(self):
        if self._headless_adapter is None:
            normalized = str(self.provider or '').strip().lower()
            session_filename = PROVIDER_SESSION_FILENAMES.get(normalized, f'.{self.provider}-session')
            
            config = NativeCliExecutionConfig(
                provider=self.provider,
                session_filename=session_filename,
                command_builder=_build_command,
                observer=observe_stdout_output,
                output_kind='out',
                mode='simple_cli_run',
            )
            self._headless_adapter = NativeCliSubprocessAdapter(config)
        return self._headless_adapter

    @property
    def restart_resume_supported(self) -> bool:
        return self.headless_adapter.restart_resume_supported

    def restore_diagnostics(self) -> dict:
        return {
            "resume_supported": self.restart_resume_supported,
            "restore_mode": "pane_or_subprocess",
            "restore_reason": "simple_cli_execution_mode_aware",
            "restore_detail": "Uses pane mode for visible execution, subprocess for headless",
        }

    def start(
        self,
        job,
        *,
        context=None,
        now: str,
    ):
        mode = _configured_execution_mode()
        if mode == SIMPLE_CLI_HEADLESS_MODE:
            return self.headless_adapter.start(job, context=context, now=now)
        return self.pane_adapter.start(job, context=context, now=now)

    def poll(self, submission, *, now: str):
        mode = submission.runtime_state.get("mode", "")
        if mode == "simple_cli_run":
            return self.headless_adapter.poll(submission, now=now)
        return self.pane_adapter.poll(submission, now=now)

    def cancel(self, submission):
        mode = submission.runtime_state.get("mode", "")
        if mode == "simple_cli_run":
            self.headless_adapter.cancel(submission)
        else:
            self.pane_adapter.cancel(submission)

    def export_runtime_state(self, submission):
        return dict(submission.runtime_state)


def _configured_execution_mode() -> str:
    return os.environ.get(SIMPLE_CLI_EXECUTION_MODE_ENV, "").strip().lower() or SIMPLE_CLI_PANE_MODE


def build_execution_adapter(*, provider: str) -> ProviderExecutionAdapter:
    """Build an execution adapter for simple CLI agents."""
    return SimpleCliExecutionAdapter(provider=provider)


def _build_command(request: NativeCliExecutionRequest) -> list[str]:
    """Build the command to execute for a simple CLI agent."""
    from provider_command_defaults import provider_start_parts
    parts = provider_start_parts(request.provider)
    
    # For claude/ccb, add --print flag and skip permissions
    if request.provider in ('claude', 'ccb'):
        parts.append('--print')
        parts.append('--dangerously-skip-permissions')
        # Extract the actual prompt from the wrapped prompt
        prompt = request.prompt or ''
        # Strip the req_id prefix if present
        if prompt.startswith('REQ '):
            lines = prompt.split('\n', 2)
            prompt = lines[2] if len(lines) > 2 else ''
        parts.append(prompt.strip())
    
    return parts


__all__ = ['build_execution_adapter']

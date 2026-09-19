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
from provider_core.protocol_runtime.constants import REQ_ID_PREFIX


# Environment variable to control execution mode
SIMPLE_CLI_EXECUTION_MODE_ENV = "CC_BRIDGE_SIMPLE_CLI_EXECUTION_MODE"
SIMPLE_CLI_HEADLESS_MODE = "headless"
SIMPLE_CLI_PANE_MODE = "pane"


def _configured_execution_mode(provider: str) -> str:
    env_mode = os.environ.get(SIMPLE_CLI_EXECUTION_MODE_ENV, "").strip().lower()
    if env_mode:
        return env_mode
    # ccb (claude variant) always uses headless mode because PiPaneExecutionAdapter
    # is designed for pi's structured event protocol which claude does not implement.
    # peri also must be headless because its pane is a REPL that cannot be driven
    # by PiPaneExecutionAdapter's tmux send-keys protocol.
    if provider in ('ccb', 'peri'):
        return SIMPLE_CLI_HEADLESS_MODE
    return SIMPLE_CLI_PANE_MODE


class SimpleCliExecutionAdapter:
    """Execution adapter that supports both pane and subprocess modes.

    For ccb, always uses headless subprocess mode regardless of env var,
    because PiPaneExecutionAdapter is incompatible with claude's pane I/O protocol.
    """

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
                run_timeout_s=8.0 if self.provider == 'peri' else 120.0,
                # peri exits non-zero (SIGTERM) after producing output — treat as COMPLETED
                treat_nonzero_exit_as_complete_when_output_present=(self.provider == 'peri'),
                # Allow resume after daemon restart: re-observes output file; if output already
                # exists the job completed before restart and will be detected as complete.
                resume_command_builder=(_peri_resume_command_builder if self.provider == 'peri' else None),
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
        mode = _configured_execution_mode(self.provider)
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


def build_execution_adapter(*, provider: str) -> ProviderExecutionAdapter:
    """Build an execution adapter for simple CLI agents."""
    return SimpleCliExecutionAdapter(provider=provider)


def _build_command(request: NativeCliExecutionRequest) -> list[str]:
    """Build the command to execute for a simple CLI agent.

    Returns the command list. Prompt delivery varies by provider:
    - claude/ccb: prompt as trailing positional argument after flags
    - peri: prompt as the argument to --print (not a trailing positional)
    """
    from provider_command_defaults import provider_start_parts
    parts = provider_start_parts(request.provider)

    # claude/ccb: append prompt as positional argument
    if request.provider in ('claude', 'ccb'):
        parts.append('--print')
        parts.append('--dangerously-skip-permissions')
        prompt = _strip_anchor(request.prompt or '')
        parts.append(prompt)
        return parts

    # peri: --print takes the prompt as its own argument value.
    # Do NOT pass prompt as a trailing positional — peri interprets that as a
    # subcommand name. Do NOT use stdin — peri hangs when stdin is provided.
    if request.provider == 'peri':
        prompt = _strip_anchor(request.prompt or '')
        parts.append('--print')
        parts.append(prompt)
        parts.append('--permission-mode')
        parts.append('bypass')
        parts.append('--no-session-persistence')
        parts.append('--output-format')
        parts.append('text')
        return parts

    return parts


def _strip_anchor(prompt: str) -> str:
    """Strip REQ_ID_PREFIX anchor and leading blank lines from prompt."""
    prefix = f'{REQ_ID_PREFIX} '
    if prompt.startswith(prefix):
        after_prefix = prompt[len(prefix):]
    else:
        after_prefix = prompt
    idx = after_prefix.find('\n\n')
    return after_prefix[idx + 2:].strip() if idx >= 0 else after_prefix.strip()


def _peri_resume_command_builder(state: dict) -> list[str] | None:
    """Resume command builder for peri headless subprocess.

    If the output file already has content, the job completed before the daemon
    restarted — return None so the standard observe path detects completion.
    If the output file is empty, re-run the same peri command.
    """
    stdout_path = state.get("stdout_path")
    if stdout_path:
        try:
            content = Path(stdout_path).read_text(encoding="utf-8", errors="replace")
            if content.strip():
                # Output already exists — job was already complete before restart.
                # Return None to let the normal observe path pick up the result.
                return None
        except OSError:
            pass

    # No output yet — re-run the same peri command using the stored prompt.
    from provider_command_defaults import provider_start_parts

    prompt = state.get("_prompt", "")
    stripped = _strip_anchor(prompt)
    parts = provider_start_parts("peri")
    parts.append('--print')
    parts.append(stripped)
    parts.append('--permission-mode')
    parts.append('bypass')
    parts.append('--no-session-persistence')
    parts.append('--output-format')
    parts.append('text')
    return parts


__all__ = ['build_execution_adapter']

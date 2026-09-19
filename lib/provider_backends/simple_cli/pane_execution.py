"""
Pane execution adapter for simple CLI providers like ccb.

This enables ask requests to be sent to the pane for visible execution.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from cc_bridge_daemon.api_models import JobRecord
from completion.models import CompletionConfidence, CompletionDecision, CompletionStatus
from provider_core.protocol import request_anchor_for_job
from provider_execution.active_runtime.polling_runtime.result import runtime_error_result
from provider_execution.base import (
    ProviderPollResult,
    ProviderRuntimeContext,
    ProviderSubmission,
)
from provider_execution.common import (
    build_item,
    interrupt_and_clear_runtime_target,
    no_wrap_requested,
    send_prompt_to_runtime_target,
)

from .prompt import clean_native_reply, wrap_native_prompt

SIMPLE_CLI_PANE_MODE = "simple_cli_pane"


@dataclass
class SimpleCliPaneExecutionState:
    pane_id: str = ""
    pane_mode: str = SIMPLE_CLI_PANE_MODE
    request_anchor: str = ""
    prompt_text: str = ""
    prompt_sent: bool = False
    prompt_sent_at: str = ""
    prompt_enqueued: bool = False
    queue_dequeue_observed: bool = False
    reply_buffer: str = ""
    terminal_reply: str = ""
    finish_reason: str = ""
    error: str = ""


class SimpleCliPaneExecutionAdapter:
    provider = "simple_cli"
    restart_resume_supported = False

    def __init__(self, provider: str = "ccb") -> None:
        self.provider = provider
        self.pane_mode = SIMPLE_CLI_PANE_MODE

    def start(
        self,
        job: JobRecord,
        *,
        context: ProviderRuntimeContext | None,
        now: str,
    ) -> ProviderSubmission:
        pane_id = context.pane_id if context else ""
        if not pane_id:
            return runtime_error_result(
                JobRecord=job,
                now=now,
                reason="no_pane_available",
                error=f"SimpleCliPaneExecution requires a pane context for {self.provider}",
            )

        request_anchor = request_anchor_for_job(job.job_id)
        prompt = job.request.body or ""
        wrapped_prompt = wrap_native_prompt(prompt, request_anchor) if not no_wrap_requested(job) else prompt

        try:
            send_prompt_to_runtime_target(
                pane_id=pane_id,
                prompt=wrapped_prompt,
                request_anchor=request_anchor,
                now=now,
            )
        except Exception as exc:
            return runtime_error_result(
                job=job,
                now=now,
                reason="pane_send_failed",
                error=f"{type(exc).__name__}: {exc}",
            )

        runtime_state = {
            "mode": self.pane_mode,
            "pane_id": pane_id,
            "request_anchor": request_anchor,
            "prompt_text": prompt,
            "prompt_sent": True,
            "prompt_sent_at": now,
            "prompt_enqueued": True,
            "queue_dequeue_observed": False,
            "reply_buffer": "",
            "terminal_reply": "",
            "finish_reason": "",
            "error": "",
        }

        return ProviderSubmission(
            job_id=job.job_id,
            provider=self.provider,
            state=CompletionStatus.IN_PROGRESS,
            runtime_state=runtime_state,
            completion_sequence_number=0,
            confidence=CompletionConfidence.LOW,
        )

    def poll(
        self,
        submission: ProviderSubmission,
        *,
        now: str,
    ) -> ProviderPollResult | None:
        from terminal_runtime import get_backend_for_session

        pane_id = submission.runtime_state.get("pane_id", "")
        if not pane_id:
            return runtime_error_result(
                job=submission,
                now=now,
                reason="no_pane_in_state",
                error="missing pane_id in runtime_state",
            )

        runtime_state = dict(submission.runtime_state)
        terminal_reply = runtime_state.get("terminal_reply", "")
        finish_reason = runtime_state.get("finish_reason", "")

        # Check if there's output in the reply buffer
        reply_buffer = runtime_state.get("reply_buffer", "")
        
        if not terminal_reply and not reply_buffer:
            return None  # Still waiting

        if terminal_reply or finish_reason:
            cleaned = clean_native_reply(terminal_reply or reply_buffer, runtime_state.get("request_anchor", ""))
            return ProviderPollResult(
                state=CompletionStatus.COMPLETED,
                items=[build_item(cleaned, is_final=True)],
                finish_reason=finish_reason or "done",
                completed_at=now,
                runtime_state=runtime_state,
            )

        return None

    def cancel(self, submission: ProviderSubmission) -> None:
        pane_id = submission.runtime_state.get("pane_id", "")
        if pane_id:
            interrupt_and_clear_runtime_target(pane_id)

    def export_runtime_state(self, submission: ProviderSubmission) -> dict:
        return dict(submission.runtime_state)


def build_pane_execution_adapter(provider: str = "ccb") -> SimpleCliPaneExecutionAdapter:
    """Build a pane execution adapter for simple CLI providers."""
    return SimpleCliPaneExecutionAdapter(provider=provider)

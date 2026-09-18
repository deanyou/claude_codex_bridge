from __future__ import annotations

from provider_backends.pane_log_support import PaneLogCommunicatorBase, PaneLogReaderBase


class QwenLogReader(PaneLogReaderBase):
    poll_env_var = 'QWEN_POLL_INTERVAL'


class QwenCommunicator(PaneLogCommunicatorBase):
    provider_key = 'qwen'
    provider_label = 'Qwen'
    session_filename = '.qwen-session'
    sync_timeout_env = 'QWEN_SYNC_TIMEOUT'
    missing_session_message = (
        "No active Qwen session found. "
        "Run 'cc_bridge qwen' (or add qwen to cc_bridge.config) first"
    )
    unhealthy_message = (
        "Session unhealthy: {status}\n"
        "Hint: run cc_bridge qwen (or add qwen to cc_bridge.config) to start a new session"
    )
    reader_cls = QwenLogReader


__all__ = ['QwenCommunicator', 'QwenLogReader']

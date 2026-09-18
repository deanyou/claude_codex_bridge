from __future__ import annotations

import re


_TMUX_SAFE_NAME_RE = re.compile(r'[^A-Za-z0-9_-]+')


def _tmux_safe_name(value: object, *, fallback: str) -> str:
    text = str(value or '').strip()
    sanitized = _TMUX_SAFE_NAME_RE.sub('_', text).strip('_-')
    return sanitized or fallback


class ProjectAnchorPathMixin:
    @property
    def project_anchor_dir(self):
        return self.cc_bridge_dir

    @property
    def cc_bridge_dir(self):
        return self.project_root / '.cc-bridge'

    @property
    def config_path(self):
        return self.cc_bridge_dir / 'cc_bridge.config'

    @property
    def cc_bridge_daemon_dir(self):
        return self.runtime_state_root / 'cc_bridge_daemon'


class CcbdMailboxPathMixin:
    @property
    def cc_bridge_daemon_submissions_path(self):
        return self.cc_bridge_daemon_dir / 'submissions.jsonl'

    @property
    def cc_bridge_daemon_mailboxes_dir(self):
        return self.cc_bridge_daemon_dir / 'mailboxes'

    @property
    def cc_bridge_daemon_messages_dir(self):
        return self.cc_bridge_daemon_dir / 'messages'

    @property
    def cc_bridge_daemon_messages_path(self):
        return self.cc_bridge_daemon_messages_dir / 'messages.jsonl'

    @property
    def cc_bridge_daemon_attempts_dir(self):
        return self.cc_bridge_daemon_dir / 'attempts'

    @property
    def cc_bridge_daemon_attempts_path(self):
        return self.cc_bridge_daemon_attempts_dir / 'attempts.jsonl'

    @property
    def cc_bridge_daemon_replies_dir(self):
        return self.cc_bridge_daemon_dir / 'replies'

    @property
    def cc_bridge_daemon_replies_path(self):
        return self.cc_bridge_daemon_replies_dir / 'replies.jsonl'

    @property
    def cc_bridge_daemon_callback_edges_path(self):
        return self.cc_bridge_daemon_dir / 'callbacks' / 'edges.jsonl'

    @property
    def cc_bridge_daemon_leases_dir(self):
        return self.cc_bridge_daemon_dir / 'leases'

    @property
    def cc_bridge_daemon_dead_letters_dir(self):
        return self.cc_bridge_daemon_dir / 'dead-letters'

    @property
    def cc_bridge_daemon_dead_letters_path(self):
        return self.cc_bridge_daemon_dead_letters_dir / 'dead_letters.jsonl'

    @property
    def cc_bridge_daemon_provider_health_dir(self):
        return self.cc_bridge_daemon_dir / 'provider-health'


class CcbdMountPathMixin:
    @property
    def cc_bridge_daemon_socket_placement(self):
        return self._project_socket_placement('cc_bridge_daemon')

    @property
    def cc_bridge_daemon_lifecycle_path(self):
        return self.cc_bridge_daemon_dir / 'lifecycle.json'

    @property
    def cc_bridge_daemon_lease_path(self):
        return self.cc_bridge_daemon_dir / 'lease.json'

    @property
    def cc_bridge_daemon_socket_path(self):
        return self.cc_bridge_daemon_socket_placement.effective_path

    @property
    def cc_bridge_daemon_state_path(self):
        return self.cc_bridge_daemon_dir / 'state.json'

    @property
    def cc_bridge_daemon_project_view_state_path(self):
        return self.cc_bridge_daemon_dir / 'project-view-state.json'

    @property
    def cc_bridge_daemon_config_restart_intent_path(self):
        return self.cc_bridge_daemon_dir / 'config-restart-intent.json'

    @property
    def cc_bridge_daemon_mobile_dir(self):
        return self.cc_bridge_daemon_dir / 'mobile'

    @property
    def cc_bridge_daemon_mobile_gateway_path(self):
        return self.cc_bridge_daemon_mobile_dir / 'gateway.json'

    @property
    def cc_bridge_daemon_mobile_devices_path(self):
        return self.cc_bridge_daemon_mobile_dir / 'devices.json'

    @property
    def cc_bridge_daemon_mobile_pairing_tokens_path(self):
        return self.cc_bridge_daemon_mobile_dir / 'pairing-tokens.jsonl'

    @property
    def cc_bridge_daemon_mobile_terminal_tokens_path(self):
        return self.cc_bridge_daemon_mobile_dir / 'terminal-tokens.jsonl'

    @property
    def cc_bridge_daemon_mobile_audit_path(self):
        return self.cc_bridge_daemon_mobile_dir / 'audit.jsonl'

    @property
    def cc_bridge_daemon_start_policy_path(self):
        return self.cc_bridge_daemon_dir / 'start-policy.json'

    @property
    def cc_bridge_daemon_restore_report_path(self):
        return self.cc_bridge_daemon_dir / 'restore-report.json'

    @property
    def cc_bridge_daemon_startup_report_path(self):
        return self.cc_bridge_daemon_dir / 'startup-report.json'

    @property
    def cc_bridge_daemon_shutdown_report_path(self):
        return self.cc_bridge_daemon_dir / 'shutdown-report.json'

    @property
    def cc_bridge_daemon_tmux_socket_placement(self):
        return self._project_socket_placement('tmux')

    @property
    def cc_bridge_daemon_tmux_socket_path(self):
        return self.cc_bridge_daemon_tmux_socket_placement.effective_path

    @property
    def cc_bridge_daemon_tmux_session_name(self) -> str:
        return f'cc_bridge-{_tmux_safe_name(self.project_slug, fallback="project")}'

    @property
    def cc_bridge_daemon_tmux_control_window_name(self) -> str:
        return '__cc_bridge_ctl'

    @property
    def cc_bridge_daemon_tmux_workspace_window_name(self) -> str:
        return 'cc_bridge'


class CcbdOpsPathMixin:
    @property
    def cc_bridge_daemon_supervision_path(self):
        return self.cc_bridge_daemon_dir / 'supervision.jsonl'

    @property
    def cc_bridge_daemon_lifecycle_log_path(self):
        return self.cc_bridge_daemon_dir / 'lifecycle.jsonl'

    @property
    def cc_bridge_daemon_keeper_path(self):
        return self.cc_bridge_daemon_dir / 'keeper.json'

    @property
    def cc_bridge_daemon_shutdown_intent_path(self):
        return self.cc_bridge_daemon_dir / 'shutdown-intent.json'

    @property
    def cc_bridge_daemon_tmux_cleanup_history_path(self):
        return self.cc_bridge_daemon_dir / 'tmux-cleanup-history.jsonl'

    @property
    def cc_bridge_daemon_maintenance_heartbeat_dir(self):
        return self.cc_bridge_daemon_dir / 'maintenance-heartbeat'

    @property
    def cc_bridge_daemon_maintenance_heartbeat_schedule_path(self):
        return self.cc_bridge_daemon_maintenance_heartbeat_dir / 'schedule.json'

    @property
    def cc_bridge_daemon_maintenance_heartbeat_status_path(self):
        return self.cc_bridge_daemon_maintenance_heartbeat_dir / 'status.json'

    @property
    def cc_bridge_daemon_maintenance_heartbeat_runner_path(self):
        return self.cc_bridge_daemon_maintenance_heartbeat_dir / 'runner.json'

    @property
    def cc_bridge_daemon_maintenance_heartbeat_lock_path(self):
        return self.cc_bridge_daemon_maintenance_heartbeat_dir / 'lock.json'

    @property
    def cc_bridge_daemon_maintenance_heartbeat_activations_path(self):
        return self.cc_bridge_daemon_maintenance_heartbeat_dir / 'activations.jsonl'

    @property
    def cc_bridge_daemon_fault_injection_path(self):
        return self.cc_bridge_daemon_dir / 'fault-injection.json'

    @property
    def cc_bridge_daemon_reload_drain_path(self):
        return self.cc_bridge_daemon_dir / 'reload-drain.json'

    @property
    def cc_bridge_daemon_reload_handoff_path(self):
        return self.cc_bridge_daemon_dir / 'reload-handoff.json'

    @property
    def cc_bridge_daemon_active_followups_path(self):
        return self.cc_bridge_daemon_dir / 'active-followups.jsonl'


class CcbdArtifactsPathMixin:
    @property
    def cc_bridge_daemon_artifacts_dir(self):
        return self.cc_bridge_daemon_dir / 'artifacts'

    @property
    def cc_bridge_daemon_text_artifacts_dir(self):
        return self.cc_bridge_daemon_artifacts_dir / 'text'

    @property
    def cc_bridge_daemon_support_dir(self):
        return self.cc_bridge_daemon_dir / 'support'

    @property
    def cc_bridge_daemon_executions_dir(self):
        return self.cc_bridge_daemon_dir / 'executions'

    @property
    def cc_bridge_daemon_snapshots_dir(self):
        return self.cc_bridge_daemon_dir / 'snapshots'

    @property
    def cc_bridge_daemon_cursors_dir(self):
        return self.cc_bridge_daemon_dir / 'cursors'

    @property
    def cc_bridge_daemon_heartbeats_dir(self):
        return self.cc_bridge_daemon_dir / 'heartbeats'


__all__ = [
    'CcbdArtifactsPathMixin',
    'CcbdMailboxPathMixin',
    'CcbdMountPathMixin',
    'CcbdOpsPathMixin',
    'ProjectAnchorPathMixin',
]

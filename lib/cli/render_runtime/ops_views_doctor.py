from __future__ import annotations

from collections.abc import Mapping

from .ops_views_common import binding_line, herdr_surface_lines


def render_doctor(payload: Mapping[str, object]) -> tuple[str, ...]:
    installation = payload.get('installation') or {}
    entrypoint = payload.get('entrypoint') or {}
    runtime = payload.get('runtime') or {}
    requirements = payload.get('requirements') or {}
    cc_bridge_daemon = payload['cc_bridge_daemon']
    lines = [
        f'project: {payload["project"]}',
        f'project_id: {payload["project_id"]}',
        f'install_path: {installation.get("path")}',
        f'install_mode: {installation.get("install_mode")}',
        f'install_source_kind: {installation.get("source_kind")}',
        f'install_version: {installation.get("version")}',
        f'install_channel: {installation.get("channel")}',
        f'install_build_time: {installation.get("build_time")}',
        f'install_platform: {installation.get("platform")}',
        f'install_arch: {installation.get("arch")}',
        f'entrypoint_status: {entrypoint.get("status")}',
        f'entrypoint_reason: {entrypoint.get("reason")}',
        f'entrypoint_path: {entrypoint.get("path")}',
        f'entrypoint_realpath: {entrypoint.get("realpath")}',
        f'entrypoint_expected_install_path: {entrypoint.get("expected_install_path")}',
        f'entrypoint_matches_current_install: {entrypoint.get("matches_current_install")}',
        f'user_id: {runtime.get("user_id")}',
        f'user_name: {runtime.get("user_name")}',
        f'home: {runtime.get("home")}',
        f'root_runtime: {runtime.get("root_runtime")}',
        f'install_root_owned: {runtime.get("install_root_owned")}',
        f'install_user_id: {runtime.get("install_user_id")}',
        f'install_user_name: {runtime.get("install_user_name")}',
        f'sudo_user: {runtime.get("sudo_user")}',
        f'project_owner: {runtime.get("project_owner")}',
        f'cc_bridge_dir_owner: {runtime.get("cc_bridge_dir_owner")}',
        f'install_owner: {runtime.get("install_owner")}',
        f'requirement_python_executable: {requirements.get("python_executable")}',
        f'requirement_python_version: {requirements.get("python_version")}',
        f'requirement_tmux_available: {requirements.get("tmux_available")}',
        f'requirement_tmux_path: {requirements.get("tmux_path")}',
    ]
    lines.extend(_windows_x64_release_surface_lines(payload.get('windows_x64_release_surface')))
    lines.extend([
        f'cc_bridge_daemon_state: {cc_bridge_daemon["state"]}',
        f'cc_bridge_daemon_pid: {cc_bridge_daemon.get("pid")}',
        f'cc_bridge_daemon_keeper_pid: {cc_bridge_daemon.get("keeper_pid")}',
        f'cc_bridge_daemon_implementation_root: {cc_bridge_daemon.get("implementation_root")}',
        f'cc_bridge_daemon_implementation_status: {cc_bridge_daemon.get("implementation_status")}',
        f'cc_bridge_daemon_implementation_reason: {cc_bridge_daemon.get("implementation_reason")}',
        f'cc_bridge_daemon_implementation_cmdline: {cc_bridge_daemon.get("implementation_cmdline")}',
        f'cc_bridge_daemon_socket_path: {cc_bridge_daemon.get("socket_path")}',
        f'cc_bridge_daemon_project_anchor_path: {cc_bridge_daemon.get("project_anchor_path")}',
        f'cc_bridge_daemon_runtime_state_root: {cc_bridge_daemon.get("runtime_state_root")}',
        f'cc_bridge_daemon_runtime_root_kind: {cc_bridge_daemon.get("runtime_root_kind")}',
        f'cc_bridge_daemon_runtime_relocation_reason: {cc_bridge_daemon.get("runtime_relocation_reason")}',
        f'cc_bridge_daemon_runtime_filesystem_hint: {cc_bridge_daemon.get("runtime_filesystem_hint")}',
        f'cc_bridge_daemon_runtime_marker_status: {cc_bridge_daemon.get("runtime_marker_status")}',
        f'cc_bridge_daemon_preferred_socket_path: {cc_bridge_daemon.get("preferred_socket_path")}',
        f'cc_bridge_daemon_effective_socket_path: {cc_bridge_daemon.get("effective_socket_path")}',
        f'cc_bridge_daemon_preferred_socket_path_bytes: {cc_bridge_daemon.get("preferred_socket_path_bytes")}',
        f'cc_bridge_daemon_effective_socket_path_bytes: {cc_bridge_daemon.get("effective_socket_path_bytes")}',
        f'cc_bridge_daemon_socket_root_kind: {cc_bridge_daemon.get("socket_root_kind")}',
        f'cc_bridge_daemon_socket_fallback_reason: {cc_bridge_daemon.get("socket_fallback_reason")}',
        f'cc_bridge_daemon_socket_filesystem_hint: {cc_bridge_daemon.get("socket_filesystem_hint")}',
        f'cc_bridge_daemon_tmux_socket_path: {cc_bridge_daemon.get("tmux_socket_path")}',
        f'cc_bridge_daemon_tmux_preferred_socket_path: {cc_bridge_daemon.get("tmux_preferred_socket_path")}',
        f'cc_bridge_daemon_tmux_effective_socket_path: {cc_bridge_daemon.get("tmux_effective_socket_path")}',
        f'cc_bridge_daemon_tmux_preferred_socket_path_bytes: {cc_bridge_daemon.get("tmux_preferred_socket_path_bytes")}',
        f'cc_bridge_daemon_tmux_effective_socket_path_bytes: {cc_bridge_daemon.get("tmux_effective_socket_path_bytes")}',
        f'cc_bridge_daemon_tmux_start_server_command: {cc_bridge_daemon.get("tmux_start_server_command")}',
        f'cc_bridge_daemon_tmux_socket_root_kind: {cc_bridge_daemon.get("tmux_socket_root_kind")}',
        f'cc_bridge_daemon_tmux_socket_fallback_reason: {cc_bridge_daemon.get("tmux_socket_fallback_reason")}',
        f'cc_bridge_daemon_tmux_socket_filesystem_hint: {cc_bridge_daemon.get("tmux_socket_filesystem_hint")}',
        f'cc_bridge_daemon_health: {cc_bridge_daemon["health"]}',
        f'cc_bridge_daemon_generation: {cc_bridge_daemon["generation"]}',
        f'cc_bridge_daemon_last_heartbeat_at: {cc_bridge_daemon["last_heartbeat_at"]}',
        f'cc_bridge_daemon_pid_alive: {cc_bridge_daemon["pid_alive"]}',
        f'cc_bridge_daemon_socket_connectable: {cc_bridge_daemon["socket_connectable"]}',
        f'cc_bridge_daemon_heartbeat_fresh: {cc_bridge_daemon["heartbeat_fresh"]}',
        f'cc_bridge_daemon_takeover_allowed: {cc_bridge_daemon["takeover_allowed"]}',
        f'cc_bridge_daemon_reason: {cc_bridge_daemon["reason"]}',
        f'cc_bridge_daemon_last_request_queue_wait_s: {cc_bridge_daemon.get("last_request_queue_wait_s")}',
        f'cc_bridge_daemon_last_submit_duration_s: {cc_bridge_daemon.get("last_submit_duration_s")}',
        f'cc_bridge_daemon_last_ping_duration_s: {cc_bridge_daemon.get("last_ping_duration_s")}',
        f'cc_bridge_daemon_last_handler_latency_s_by_op: {_format_mapping(cc_bridge_daemon.get("last_handler_latency_s_by_op"))}',
        f'cc_bridge_daemon_last_maintenance_duration_s: {cc_bridge_daemon.get("last_maintenance_duration_s")}',
        f'cc_bridge_daemon_last_heartbeat_duration_s: {cc_bridge_daemon.get("last_heartbeat_duration_s")}',
        f'cc_bridge_daemon_heartbeat_step_duration_s: {_format_mapping(cc_bridge_daemon.get("heartbeat_step_duration_s"))}',
        f'cc_bridge_daemon_last_heartbeat_agents_inspected: {cc_bridge_daemon.get("last_heartbeat_agents_inspected")}',
        f'cc_bridge_daemon_last_heartbeat_runtime_store_writes: {cc_bridge_daemon.get("last_heartbeat_runtime_store_writes")}',
        f'cc_bridge_daemon_pending_maintenance_ticks: {cc_bridge_daemon.get("pending_maintenance_ticks")}',
        f'cc_bridge_daemon_last_project_view_response_duration_s: {cc_bridge_daemon.get("last_project_view_response_duration_s")}',
        f'cc_bridge_daemon_last_project_view_build_duration_s: {cc_bridge_daemon.get("last_project_view_build_duration_s")}',
        f'cc_bridge_daemon_project_view_cache_hits: {cc_bridge_daemon.get("project_view_cache_hits")}',
        f'cc_bridge_daemon_project_view_cache_misses: {cc_bridge_daemon.get("project_view_cache_misses")}',
        f'cc_bridge_daemon_last_project_view_tmux_command_count: {cc_bridge_daemon.get("last_project_view_tmux_command_count")}',
        f'cc_bridge_daemon_last_project_view_capture_pane_count: {cc_bridge_daemon.get("last_project_view_capture_pane_count")}',
        f'cc_bridge_daemon_last_project_view_store_scan_count: {cc_bridge_daemon.get("last_project_view_store_scan_count")}',
        f'cc_bridge_daemon_rss_bytes: {cc_bridge_daemon.get("rss_bytes")}',
        f'cc_bridge_daemon_virtual_memory_bytes: {cc_bridge_daemon.get("virtual_memory_bytes")}',
        f'cc_bridge_daemon_fd_count: {cc_bridge_daemon.get("fd_count")}',
        f'cc_bridge_daemon_thread_count: {cc_bridge_daemon.get("thread_count")}',
        f'cc_bridge_daemon_service_graph_version: {cc_bridge_daemon.get("service_graph_version")}',
        f'cc_bridge_daemon_service_graph_created_at: {cc_bridge_daemon.get("service_graph_created_at")}',
        f'cc_bridge_daemon_service_graph_retained_count: {cc_bridge_daemon.get("service_graph_retained_count")}',
        f'cc_bridge_daemon_service_graph_retained_count_scope: {cc_bridge_daemon.get("service_graph_retained_count_scope")}',
        f'cc_bridge_daemon_last_reload_duration_s: {cc_bridge_daemon.get("last_reload_duration_s")}',
        f'cc_bridge_daemon_last_reload_plan_class: {cc_bridge_daemon.get("last_reload_plan_class")}',
        f'cc_bridge_daemon_last_reload_error: {cc_bridge_daemon.get("last_reload_error")}',
        f'cc_bridge_daemon_active_execution_count: {cc_bridge_daemon["active_execution_count"]}',
        f'cc_bridge_daemon_recoverable_execution_count: {cc_bridge_daemon["recoverable_execution_count"]}',
        f'cc_bridge_daemon_nonrecoverable_execution_count: {cc_bridge_daemon["nonrecoverable_execution_count"]}',
        f'cc_bridge_daemon_pending_items_count: {cc_bridge_daemon["pending_items_count"]}',
        f'cc_bridge_daemon_terminal_pending_count: {cc_bridge_daemon["terminal_pending_count"]}',
        f'cc_bridge_daemon_recoverable_execution_providers: {cc_bridge_daemon["recoverable_execution_providers"]}',
        f'cc_bridge_daemon_nonrecoverable_execution_providers: {cc_bridge_daemon["nonrecoverable_execution_providers"]}',
        f'cc_bridge_daemon_last_restore_at: {cc_bridge_daemon.get("last_restore_at")}',
        f'cc_bridge_daemon_last_restore_running_job_count: {cc_bridge_daemon.get("last_restore_running_job_count")}',
        f'cc_bridge_daemon_last_restore_restored_execution_count: {cc_bridge_daemon.get("last_restore_restored_execution_count")}',
        f'cc_bridge_daemon_last_restore_replay_pending_count: {cc_bridge_daemon.get("last_restore_replay_pending_count")}',
        f'cc_bridge_daemon_last_restore_terminal_pending_count: {cc_bridge_daemon.get("last_restore_terminal_pending_count")}',
        f'cc_bridge_daemon_last_restore_abandoned_execution_count: {cc_bridge_daemon.get("last_restore_abandoned_execution_count")}',
        f'cc_bridge_daemon_last_restore_already_active_count: {cc_bridge_daemon.get("last_restore_already_active_count")}',
        f'cc_bridge_daemon_last_restore_results_text: {cc_bridge_daemon.get("last_restore_results_text")}',
        f'cc_bridge_daemon_startup_last_at: {cc_bridge_daemon.get("startup_last_at")}',
        f'cc_bridge_daemon_startup_last_trigger: {cc_bridge_daemon.get("startup_last_trigger")}',
        f'cc_bridge_daemon_startup_last_status: {cc_bridge_daemon.get("startup_last_status")}',
        f'cc_bridge_daemon_startup_last_generation: {cc_bridge_daemon.get("startup_last_generation")}',
        f'cc_bridge_daemon_startup_last_daemon_started: {cc_bridge_daemon.get("startup_last_daemon_started")}',
        f'cc_bridge_daemon_startup_last_run_id: {cc_bridge_daemon.get("startup_last_run_id")}',
        f'cc_bridge_daemon_startup_last_requested_agents: {cc_bridge_daemon.get("startup_last_requested_agents")}',
        f'cc_bridge_daemon_startup_last_desired_agents: {cc_bridge_daemon.get("startup_last_desired_agents")}',
        f'cc_bridge_daemon_startup_last_actions: {cc_bridge_daemon.get("startup_last_actions")}',
        f'cc_bridge_daemon_startup_last_cleanup_killed: {cc_bridge_daemon.get("startup_last_cleanup_killed")}',
        f'cc_bridge_daemon_startup_last_failure_reason: {cc_bridge_daemon.get("startup_last_failure_reason")}',
        f'cc_bridge_daemon_startup_last_timings_ms: {cc_bridge_daemon.get("startup_last_timings_ms")}',
        f'cc_bridge_daemon_startup_last_operation_counts: {cc_bridge_daemon.get("startup_last_operation_counts")}',
        f'cc_bridge_daemon_startup_last_provider_prepare_count: {cc_bridge_daemon.get("startup_last_provider_prepare_count")}',
        f'cc_bridge_daemon_startup_last_agent_timings_ms: {cc_bridge_daemon.get("startup_last_agent_timings_ms")}',
        f'cc_bridge_daemon_startup_last_agent_results_text: {cc_bridge_daemon.get("startup_last_agent_results_text")}',
        f'cc_bridge_daemon_shutdown_last_at: {cc_bridge_daemon.get("shutdown_last_at")}',
        f'cc_bridge_daemon_shutdown_last_trigger: {cc_bridge_daemon.get("shutdown_last_trigger")}',
        f'cc_bridge_daemon_shutdown_last_status: {cc_bridge_daemon.get("shutdown_last_status")}',
        f'cc_bridge_daemon_shutdown_last_forced: {cc_bridge_daemon.get("shutdown_last_forced")}',
        f'cc_bridge_daemon_shutdown_last_generation: {cc_bridge_daemon.get("shutdown_last_generation")}',
        f'cc_bridge_daemon_shutdown_last_reason: {cc_bridge_daemon.get("shutdown_last_reason")}',
        f'cc_bridge_daemon_shutdown_last_stopped_agents: {cc_bridge_daemon.get("shutdown_last_stopped_agents")}',
        f'cc_bridge_daemon_shutdown_last_actions: {cc_bridge_daemon.get("shutdown_last_actions")}',
        f'cc_bridge_daemon_shutdown_last_cleanup_killed: {cc_bridge_daemon.get("shutdown_last_cleanup_killed")}',
        f'cc_bridge_daemon_shutdown_last_failure_reason: {cc_bridge_daemon.get("shutdown_last_failure_reason")}',
        f'cc_bridge_daemon_shutdown_last_runtime_states_text: {cc_bridge_daemon.get("shutdown_last_runtime_states_text")}',
        f'cc_bridge_daemon_namespace_epoch: {cc_bridge_daemon.get("namespace_epoch")}',
        f'cc_bridge_daemon_namespace_tmux_socket_path: {cc_bridge_daemon.get("namespace_tmux_socket_path")}',
        f'cc_bridge_daemon_namespace_tmux_session_name: {cc_bridge_daemon.get("namespace_tmux_session_name")}',
        f'cc_bridge_daemon_namespace_layout_version: {cc_bridge_daemon.get("namespace_layout_version")}',
        f'cc_bridge_daemon_namespace_ui_attachable: {cc_bridge_daemon.get("namespace_ui_attachable")}',
        f'cc_bridge_daemon_namespace_last_started_at: {cc_bridge_daemon.get("namespace_last_started_at")}',
        f'cc_bridge_daemon_namespace_last_destroyed_at: {cc_bridge_daemon.get("namespace_last_destroyed_at")}',
        f'cc_bridge_daemon_namespace_last_destroy_reason: {cc_bridge_daemon.get("namespace_last_destroy_reason")}',
        f'cc_bridge_daemon_namespace_last_event_kind: {cc_bridge_daemon.get("namespace_last_event_kind")}',
        f'cc_bridge_daemon_namespace_last_event_at: {cc_bridge_daemon.get("namespace_last_event_at")}',
        f'cc_bridge_daemon_namespace_last_event_epoch: {cc_bridge_daemon.get("namespace_last_event_epoch")}',
        f'cc_bridge_daemon_namespace_last_event_socket_path: {cc_bridge_daemon.get("namespace_last_event_socket_path")}',
        f'cc_bridge_daemon_namespace_last_event_session_name: {cc_bridge_daemon.get("namespace_last_event_session_name")}',
        f'cc_bridge_daemon_start_policy_auto_permission: {cc_bridge_daemon.get("start_policy_auto_permission")}',
        f'cc_bridge_daemon_start_policy_recovery_restore: {cc_bridge_daemon.get("start_policy_recovery_restore")}',
        f'cc_bridge_daemon_start_policy_last_started_at: {cc_bridge_daemon.get("start_policy_last_started_at")}',
        f'cc_bridge_daemon_start_policy_source: {cc_bridge_daemon.get("start_policy_source")}',
        f'cc_bridge_daemon_tmux_cleanup_last_kind: {cc_bridge_daemon.get("tmux_cleanup_last_kind")}',
        f'cc_bridge_daemon_tmux_cleanup_last_at: {cc_bridge_daemon.get("tmux_cleanup_last_at")}',
        f'cc_bridge_daemon_tmux_cleanup_socket_count: {cc_bridge_daemon.get("tmux_cleanup_socket_count")}',
        f'cc_bridge_daemon_tmux_cleanup_total_owned: {cc_bridge_daemon.get("tmux_cleanup_total_owned")}',
        f'cc_bridge_daemon_tmux_cleanup_total_active: {cc_bridge_daemon.get("tmux_cleanup_total_active")}',
        f'cc_bridge_daemon_tmux_cleanup_total_orphaned: {cc_bridge_daemon.get("tmux_cleanup_total_orphaned")}',
        f'cc_bridge_daemon_tmux_cleanup_total_killed: {cc_bridge_daemon.get("tmux_cleanup_total_killed")}',
        f'cc_bridge_daemon_tmux_cleanup_sockets: {cc_bridge_daemon.get("tmux_cleanup_sockets")}',
    ])
    for provider in requirements.get('provider_commands') or ():
        line = (
            'requirement_provider: '
            f'name={provider.get("provider")} '
            f'executable={provider.get("executable")} '
            f'available={provider.get("available")} '
            f'path={provider.get("path")}'
        )
        if provider.get('status') is not None:
            line = f'{line} status={provider.get("status")}'
        if provider.get('reason') is not None:
            line = f'{line} reason={provider.get("reason")}'
        if provider.get('warning') is not None:
            line = f'{line} warning={provider.get("warning")}'
        lines.append(line)
    for warning in runtime.get('warnings') or ():
        lines.append(f'runtime_warning: {warning}')
    for error in cc_bridge_daemon.get('diagnostic_errors') or ():
        lines.append(f'cc_bridge_daemon_diagnostic_error: {error}')
    lines.extend(herdr_surface_lines(cc_bridge_daemon.get('herdr_surface_projection'), prefix='cc_bridge_daemon_herdr'))
    diagnostics = payload.get('active_inbound_diagnostics') or ()
    lines.append(f'active_inbound_diagnostic_count: {len(diagnostics)}')
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, Mapping):
            continue
        lines.append(
            'active_inbound_diagnostic: '
            f'condition={diagnostic.get("condition_kind")} '
            f'reason={diagnostic.get("reason")} '
            f'job={diagnostic.get("job_id")} '
            f'inbound={diagnostic.get("inbound_event_id")} '
            f'lease={diagnostic.get("lease_state")} '
            f'observed_for_s={diagnostic.get("observed_for_s")} '
            f'required_s={diagnostic.get("required_observation_s")} '
            f'recommended_action={diagnostic.get("recommended_action")} '
            f'automatic_action={diagnostic.get("automatic_action")}'
        )
    for agent in payload['agents']:
        lines.append(
            f'agent: name={agent["agent_name"]} health={agent["health"]} provider={agent["provider"]} completion={agent["completion_family"]}'
        )
        lines.append(binding_line(agent))
        lines.append(
            f'restore: supported={agent["execution_resume_supported"]} mode={agent["execution_restore_mode"]} reason={agent["execution_restore_reason"]}'
        )
        lines.append(f'restore_detail: {agent["execution_restore_detail"]}')
        lines.append(
            'mailbox_summary: '
            f'version={agent.get("mailbox_summary_version")} '
            f'source={agent.get("mailbox_summary_source")} '
            f'refreshed_at={agent.get("mailbox_summary_refreshed_at")} '
            f'state={agent.get("mailbox_state")} '
            f'queue={agent.get("mailbox_queue_depth")} '
            f'pending_reply={agent.get("mailbox_pending_reply_count")} '
            f'active={agent.get("mailbox_active_inbound_event_id")} '
            f'head={agent.get("mailbox_head_inbound_event_id")} '
            f'head_type={agent.get("mailbox_head_event_type")} '
            f'head_status={agent.get("mailbox_head_status")}'
        )
        projected = agent.get('mailbox_consistency_projected') or {}
        mismatches = agent.get('mailbox_consistency_mismatches') or ()
        lines.append(
            'mailbox_consistency: '
            f'status={agent.get("mailbox_consistency_status")} '
            f'mismatches={",".join(str(item) for item in mismatches) or "none"} '
            f'projected_state={projected.get("mailbox_state")} '
            f'projected_queue={projected.get("queue_depth")} '
            f'projected_pending_reply={projected.get("pending_reply_count")} '
            f'projected_active={projected.get("active_inbound_event_id")} '
            f'projected_head={projected.get("head_inbound_event_id")} '
            f'projected_head_type={projected.get("head_event_type")} '
            f'projected_head_status={projected.get("head_status")}'
        )
        if agent.get('mailbox_consistency_error'):
            lines.append(f'mailbox_consistency_error: {agent.get("mailbox_consistency_error")}')
        if agent.get("session_switch_state"):
            lines.append(
                'session_switch: '
                f'state={agent.get("session_switch_state")} '
                f'reason={agent.get("session_switch_reason")} '
                f'committed={agent.get("session_switch_committed")} '
                f'candidate_session={agent.get("session_switch_candidate_id")} '
                f'candidate_path={agent.get("session_switch_candidate_path")}'
            )
    return tuple(lines)


def _format_mapping(value: object) -> str:
    if not isinstance(value, Mapping):
        return ''
    return ','.join(f'{key}={value[key]}' for key in sorted(value))


def _windows_x64_release_surface_lines(value: object) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    return [
        'windows_x64_release_surface: '
        f'surface_state={value.get("surface_state")} '
        f'failure_reason={value.get("failure_reason")} '
        f'release_install_entry={value.get("release_install_entry")} '
        f'source_install_allowed={value.get("source_install_allowed")} '
        f'source_install_entry={value.get("source_install_entry")} '
        f'update_entry={value.get("update_entry")} '
        f'managed_python_status={value.get("managed_python_status")} '
        f'native_helper_status={value.get("native_helper_status")}',
        'windows_x64_release_surface_detail: '
        f'implementation_admission={value.get("implementation_admission")} '
        f'baseline_version_status={value.get("baseline_version_status")} '
        f'upstream_gate_status={value.get("upstream_gate_status")} '
        f'upstream_failure_ref={value.get("upstream_failure_ref")} '
        f'upstream_detail_reason={value.get("upstream_detail_reason")} '
        f'beta_gaps={_format_list(value.get("beta_gaps"))}',
        'windows_x64_release_surface_next_action: '
        f'diagnostic={value.get("diagnostic")} '
        f'next_action={value.get("next_action")}',
    ]


def _format_list(value: object) -> str:
    if isinstance(value, (list, tuple, set)):
        return ','.join(str(item) for item in value) or 'none'
    text = str(value or '').strip()
    return text or 'none'


def render_doctor_storage(payload: Mapping[str, object]) -> tuple[str, ...]:
    user_provider_cache_bytes = payload.get('user_provider_cache_bytes')
    lines = [
        'storage_status: ok',
        f'storage_schema_version: {payload.get("schema_version")}',
        f'project: {payload.get("project")}',
        f'project_id: {payload.get("project_id")}',
        f'storage_runtime_root_kind: {payload.get("runtime_root_kind")}',
        f'storage_runtime_state_root: {payload.get("runtime_state_root")}',
        f'storage_shared_cache_root: {payload.get("shared_cache_root") or ""}',
        f'storage_shared_cache_root_usable: {payload.get("shared_cache_root_usable", False)}',
        f'storage_shared_cache_status: {payload.get("shared_cache_status")}',
        f'storage_shared_cache_reason: {payload.get("shared_cache_reason")}',
        f'storage_legacy_provider_cache_root: {payload.get("legacy_provider_cache_root") or ""}',
        f'storage_legacy_provider_cache_present: {payload.get("legacy_provider_cache_present", False)}',
        f'storage_legacy_provider_cache_bytes: {payload.get("legacy_provider_cache_bytes", 0)}',
        f'storage_user_provider_cache_root: {payload.get("user_provider_cache_root") or ""}',
        f'storage_user_provider_cache_present: {payload.get("user_provider_cache_present", False)}',
        f'storage_user_provider_cache_bytes: {user_provider_cache_bytes if user_provider_cache_bytes is not None else ""}',
        f'storage_user_provider_cache_size_status: {payload.get("user_provider_cache_size_status") or ""}',
        f'storage_total_bytes: {payload.get("total_bytes")}',
        f'storage_total_count: {payload.get("total_count")}',
    ]
    for storage_class, summary in sorted((payload.get('by_class') or {}).items()):
        lines.append(
            'storage_class: '
            f'class={storage_class} '
            f'bytes={summary.get("bytes")} '
            f'count={summary.get("count")}'
        )
    for provider, summary in sorted((payload.get('by_provider') or {}).items()):
        lines.append(
            'storage_provider: '
            f'provider={provider} '
            f'bytes={summary.get("bytes")} '
            f'count={summary.get("count")}'
        )
    for agent, summary in sorted((payload.get('by_agent') or {}).items()):
        lines.append(
            'storage_agent: '
            f'agent={agent} '
            f'bytes={summary.get("bytes")} '
            f'count={summary.get("count")}'
        )
    for entry in (payload.get('entries') or ())[:50]:
        lines.append(
            'storage_entry: '
            f'class={entry.get("storage_class")} '
            f'provider={entry.get("provider")} '
            f'agent={entry.get("agent")} '
            f'bytes={entry.get("size_bytes")} '
            f'active={entry.get("active")} '
            f'reclaimable={entry.get("reclaimable")} '
            f'reason={entry.get("reason")} '
            f'path={entry.get("relative_path")}'
        )
    return tuple(lines)


__all__ = ['render_doctor', 'render_doctor_storage']

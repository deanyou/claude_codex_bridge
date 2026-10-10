"""Step 3'-b: durable-bridge 接入 daemon 端 submit 路径的回归测试。

测试 6 项（plan §1.2 测试表）：

  1. ``test_default_dispatcher_has_no_durable_backend``
     — 默认构造下行为与改动前逐字段一致。
  2. ``test_durable_dispatch_runs_at_job_start``
     — durable 模式下 job 转 running 时产生 binding + submission。
  3. ``test_durable_dispatch_is_idempotent``
     — 连触发两次 start 逻辑，只产生一条 submission（防重复提交三道防线）。
  4. ``test_durable_dispatch_failure_falls_back_to_legacy``
     — 桥不可用时 job 照常跑，日志有说明。
  5. ``test_no_durable_dispatcher_means_no_bridge_calls``
     — ``durable_dispatcher=None`` 时完全不碰 bridge client。
  6. ``test_multi_agent_routes_to_correct_dispatcher``
     — 多 agent 场景下按 agent_name 路由（callable 形态）。

约束：本测试文件只触碰 ``lib/cc_bridge_daemon/**`` 与
``test/test_cc_bridge_daemon_*.py``；不引入对 ``lib/durable_bridge/**`` 内
部的强依赖（只通过 ``DurableDispatcher`` 公共 API 触发）。
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agents.models import (
    AgentApiSpec,
    AgentRuntime,
    AgentSpec,
    AgentState,
    PermissionMode,
    ProjectConfig,
    QueuePolicy,
    RestoreMode,
    RuntimeMode,
    WorkspaceMode,
)
from cc_bridge_daemon.api_models import (
    DeliveryScope,
    JobStatus,
    MessageEnvelope,
)
from cc_bridge_daemon.services.dispatcher import JobDispatcher
from cc_bridge_daemon.services.dispatcher_runtime.durable_dispatch import (
    attempt_durable_dispatch,
    resolve_durable_dispatcher,
)
from cc_bridge_daemon.services.registry import AgentRegistry
from completion.tracker import CompletionTrackerService
from project.ids import compute_project_id
from project.resolver import ProjectContext
from provider_core.catalog import build_default_provider_catalog
from storage.paths import PathLayout


# ---- helpers ----


def _bootstrap_test_project(project_root: Path) -> ProjectContext:
    project_root.mkdir()
    config_dir = project_root / '.cc-bridge'
    config_dir.mkdir(exist_ok=True)
    (config_dir / 'cc_bridge.config').write_text('cmd; demo:fake\n', encoding='utf-8')
    return ProjectContext(
        cwd=project_root,
        project_root=project_root,
        config_dir=config_dir,
        project_id=compute_project_id(project_root),
        source='test',
    )


def _runtime(agent_name: str, *, project_id: str, layout: PathLayout, pid: int) -> AgentRuntime:
    return AgentRuntime(
        agent_name=agent_name,
        state=AgentState.IDLE,
        pid=pid,
        started_at='2026-03-30T00:00:00Z',
        last_seen_at='2026-03-30T00:00:00Z',
        runtime_ref=f'{agent_name}-runtime',
        session_ref=f'{agent_name}-session',
        workspace_path=str(layout.workspace_path(agent_name)),
        project_id=project_id,
        backend_type='tmux',
        queue_depth=0,
        socket_path=None,
        health='healthy',
    )


def _provider_config(agent_name: str) -> ProjectConfig:
    return ProjectConfig(
        version=2,
        default_agents=(agent_name,),
        agents={agent_name: AgentSpec(
            name=agent_name,
            provider=agent_name,
            target='.',
            workspace_mode=WorkspaceMode.GIT_WORKTREE,
            workspace_root=None,
            runtime_mode=RuntimeMode.PANE_BACKED,
            restore_default=RestoreMode.AUTO,
            permission_default=PermissionMode.MANUAL,
            queue_policy=QueuePolicy.SERIAL_PER_AGENT,
            model=None,
            api=AgentApiSpec(key='k', url='u'),
            branch_template='cc/{agent_name}',
        )},
        cmd_enabled=True,
    )


def _build_dispatcher(
    tmp_path: Path,
    agent_name: str = 'codex',
    *,
    durable_dispatcher=None,
    extra_agents: tuple[str, ...] = (),
) -> JobDispatcher:
    """构造一个最小可用的 JobDispatcher（不依赖真实 execution service）。

    关闭 ``execution_service``、``runtime_service`` 避免随机副作用；
    关闭 ``completion_tracker``、``auto_reply_delivery_on_complete`` 走
    最朴素的路径。
    """
    project_root = tmp_path / f'repo-{agent_name}'
    ctx = _bootstrap_test_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config(agent_name)
    registry = AgentRegistry(layout, config)
    registry.upsert(_runtime(agent_name, project_id=ctx.project_id, layout=layout, pid=101))
    for idx, extra in enumerate(extra_agents):
        extra_config = _provider_config(extra)
        extra_registry = AgentRegistry(layout, extra_config)
        try:
            registry.upsert(_runtime(extra, project_id=ctx.project_id, layout=layout, pid=200 + idx))
        except Exception:
            pass
    return JobDispatcher(
        layout,
        config,
        registry,
        auto_reply_delivery_on_complete=False,
        require_actionable_runtime_binding_for_execution=False,
        completion_tracker=CompletionTrackerService(
            config, build_default_provider_catalog(), request_timeout_s=10.0,
        ),
        provider_catalog=build_default_provider_catalog(),
        durable_dispatcher=durable_dispatcher,
        clock=lambda: '2026-03-30T00:00:00Z',
    )


def _submit_codex(dispatcher: JobDispatcher, body: str = 'hello') -> str:
    ctx_project_id = dispatcher._config.default_agents[0]  # not actually project id but for unique
    receipt = dispatcher.submit(
        MessageEnvelope(
            project_id='proj-3b',
            to_agent=str(dispatcher._config.default_agents[0]),
            from_actor='user',
            body=body,
            task_id='task-3b',
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        )
    )
    assert receipt.jobs, 'submit produced no jobs'
    return receipt.jobs[0].job_id


# ---- 真实 DurableDispatcher 桥 ----


class _RecordingDispatcher:
    """记录 ``dispatch()`` 调用次数并提供真实 ledger 接口的最小 dispatcher。

    不修改 ``lib/durable_bridge/**``；通过 MagicMock 提供 ``_ledger`` 字段，
    让 ``attempt_durable_dispatch()`` 的第 3 道防线能读到 ``submitted``.
    """
    def __init__(self, *, raise_exc: Exception | None = None, simulate_already_submitted: bool = False):
        self.raise_exc = raise_exc
        self.simulate_already_submitted = simulate_already_submitted
        self.calls: list[dict] = []
        self._ledger = MagicMock()
        # 默认 ledger 返回 None（binding 不存在）
        self._ledger.lookup_by_binding_id.return_value = None
        # simulate_already_submitted=True 时返回 submitted 阶段记录
        if simulate_already_submitted:
            rec = MagicMock()
            rec.delivery_phase = 'submitted'
            self._ledger.lookup_by_binding_id.return_value = rec

    def dispatch(self, *, binding_id, inbound_event_id, message_id, attempt_id,
                 request_id, input_hash, storage_path, input_text):
        self.calls.append({
            'binding_id': binding_id,
            'inbound_event_id': inbound_event_id,
            'message_id': message_id,
            'attempt_id': attempt_id,
            'request_id': request_id,
            'input_hash': input_hash,
            'storage_path': storage_path,
            'input_text': input_text,
        })
        if self.raise_exc is not None:
            raise self.raise_exc
        # 模拟 SUBMITTED
        result = MagicMock()
        result.outcome = MagicMock()
        result.outcome.value = 'submitted'
        result.submission_id = f'sub-{binding_id}'
        result.conversation_id = f'conv-{binding_id}'
        result.detail = 'ok'
        return result


# ---- 测试 1: 默认行为逐字段不变 ----


def test_default_dispatcher_has_no_durable_backend(tmp_path: Path) -> None:
    """durable_dispatcher=None 时 JobDispatcher 字段集合与改动前一致。

    通过：仅 kwargs 增加新参数；老用法不传 name 走默认 None；self._durable_dispatcher
    应当存在但为 None；其它属性原样。
    """
    dispatcher = _build_dispatcher(tmp_path, agent_name='codex')
    # 新字段存在
    assert hasattr(dispatcher, '_durable_dispatcher')
    # 默认值为 None —— 意味着 attempt_durable_dispatch 直接早返回
    assert dispatcher._durable_dispatcher is None
    # 行为：resolve_durable_dispatcher 返回 None
    assert resolve_durable_dispatcher(dispatcher, 'codex') is None

    # 其它关键属性仍在
    assert dispatcher._agent_lifecycle_bridge is None  # 默认
    assert dispatcher._layout is not None
    assert dispatcher._message_bureau is not None


def test_default_dispatcher_submit_unchanged_when_durable_is_none(tmp_path: Path) -> None:
    """durable_dispatcher=None 时 submit + tick 行为与改动前一致。"""
    dispatcher = _build_dispatcher(tmp_path, agent_name='codex')
    job_id = _submit_codex(dispatcher, body='hello world')
    # tick 把 queued 推成 running（无 durable 介入）
    started = dispatcher.tick()
    assert any(j.job_id == job_id for j in started)
    # job 状态变 RUNNING
    job = dispatcher.get(job_id)
    assert job is not None
    assert job.status is JobStatus.RUNNING


# ---- 测试 2: durable 模式下启动时产生 binding + submission ----


def test_durable_dispatch_runs_at_job_start(tmp_path: Path, caplog) -> None:
    """durable 模式开启：submit + tick 触发 DurableDispatcher.dispatch 一次。

    验证：
      - work_calls 长度 = 1
      - binding_id 派生自 job_id（idempotent）
      - inbound_event_id / message_id / attempt_id 来自 mailbox
      - 日志包含 "durable_dispatch"
    """
    durable = _RecordingDispatcher()
    dispatcher = _build_dispatcher(
        tmp_path, agent_name='codex', durable_dispatcher=durable,
    )
    job_id = _submit_codex(dispatcher)
    with caplog.at_level(logging.INFO, logger='cc_bridge_daemon.services.dispatcher_runtime.durable_dispatch'):
        dispatcher.tick()

    assert len(durable.calls) == 1, f'expected exactly one dispatch call, got {len(durable.calls)}'
    call = durable.calls[0]
    # binding_id 派生自 job_id
    assert call['binding_id'] == f'bdg-{job_id}'
    assert call['request_id'] == f'req-{job_id}'
    # inbound_event_id / message_id / attempt_id 都填了
    assert call['inbound_event_id'].startswith('iev_')
    assert call['message_id'].startswith('msg_')
    assert call['attempt_id'].startswith('att_')
    # input_hash 是 body 的 sha256
    expected_hash = hashlib.sha256(b'hello').hexdigest()
    assert call['input_hash'] == expected_hash
    assert call['input_text'] == 'hello'
    # 日志
    assert any('durable_dispatch' in rec.message for rec in caplog.records)


# ---- 测试 3: 防重复提交（核心） ----


def test_durable_dispatch_is_idempotent_via_binding_id_short_circuit(tmp_path: Path) -> None:
    """第 3 道防线：账本已 submitted → 第二次 start 不会调 dispatch()。

    模拟 daemon 重启后第二次跑同一个 job_id 的 start 路径。
    ledger.lookup_by_binding_id 返回 submitted 记录。
    """
    durable = _RecordingDispatcher(simulate_already_submitted=True)
    dispatcher = _build_dispatcher(
        tmp_path, agent_name='codex', durable_dispatcher=durable,
    )
    job_id = _submit_codex(dispatcher)
    # 第一次 tick —— 但是 ledger 模拟成已 submitted，触发第 3 道防线短路
    dispatcher.tick()
    # 即使 ledger 假装说 submitted，binding_id 派生自 job_id，
    # 我们的 attempt_durable_dispatch 直接返回而不调用 dispatch()
    assert durable.calls == [], (
        f'expected zero dispatch() calls due to short-circuit, '
        f'got {len(durable.calls)}: {durable.calls!r}'
    )
    # 第 3 道防线确认：job 仍然处于 RUNNING 状态（pane 路径继续跑）
    job = dispatcher.get(job_id)
    assert job is not None
    assert job.status is JobStatus.RUNNING


def test_durable_dispatch_double_tick_is_idempotent(tmp_path: Path) -> None:
    """第 1+2 道防线：连触发两次 → 一次只产生一条 submission。

    第一次 tick 触发 dispatch()，binding 进入 submitted。
    第二次 tick：ledger 返回 submitted 阶段记录 → 第 3 道防线短路 → 不调 dispatch()。
    """
    durable = _RecordingDispatcher()
    dispatcher = _build_dispatcher(
        tmp_path, agent_name='codex', durable_dispatcher=durable,
    )
    job_id = _submit_codex(dispatcher)

    # 第一次 tick：dispatch() 被调用一次
    dispatcher.tick()
    assert len(durable.calls) == 1

    # 现在 ledger 假装已 submitted (后续重试场景)
    submitted_rec = MagicMock()
    submitted_rec.delivery_phase = 'submitted'
    durable._ledger.lookup_by_binding_id.return_value = submitted_rec

    # 第二次 tick：start_next_queued_job 应该不再弹出（status 已是 RUNNING，
    # 不会再走 start_running_job），但是保险起见手动调用一次
    from cc_bridge_daemon.services.dispatcher_runtime.lifecycle_start_runtime.start import (
        start_running_job,
    )
    from cc_bridge_daemon.services.dispatcher_runtime.lifecycle_start_runtime.models import (
        QueuedTargetSlot,
    )
    slot = QueuedTargetSlot(
        target_kind=dispatcher.get(job_id).target_kind,
        target_name=dispatcher.get(job_id).target_name,
        runtime=None,
    )
    current = dispatcher.get(job_id)
    start_running_job(dispatcher, current, slot=slot, started_at='2026-03-30T00:00:01Z')

    # 仍然只有一次
    assert len(durable.calls) == 1, (
        f'expected exactly one dispatch call after duplicate start, '
        f'got {len(durable.calls)}: {durable.calls!r}'
    )


# ---- 测试 4: 失败降级 ----


def test_durable_dispatch_failure_falls_back_to_legacy(tmp_path: Path, caplog) -> None:
    """桥 dispatch() 抛异常 → job 照常跑，日志有 warning 说明。

    legacy 路径不受影响：mark_attempt_started / start_execution 继续工作。
    """
    durable = _RecordingDispatcher(raise_exc=RuntimeError('bridge offline'))
    dispatcher = _build_dispatcher(
        tmp_path, agent_name='codex', durable_dispatcher=durable,
    )
    job_id = _submit_codex(dispatcher)

    with caplog.at_level(logging.WARNING, logger='cc_bridge_daemon.services.dispatcher_runtime.durable_dispatch'):
        dispatcher.tick()

    # dispatch 被调用了一次（虽然抛异常）
    assert len(durable.calls) == 1
    # job 仍被 tick 推 RUNNING（legacy 路径生效）
    job = dispatcher.get(job_id)
    assert job is not None
    assert job.status is JobStatus.RUNNING
    # 日志包含 fallback 提示
    assert any(
        'falling back to legacy pane path' in rec.message
        for rec in caplog.records
    ), f'fallback log missing; records: {[r.message for r in caplog.records]!r}'


def test_durable_dispatch_resolver_exception_returns_none(tmp_path: Path) -> None:
    """多 agent 路由 callable 抛异常 → resolve 返回 None，不挂 job。"""
    def broken_resolver(agent_name: str):
        raise RuntimeError(f'router broken for {agent_name}')

    dispatcher = _build_dispatcher(
        tmp_path, agent_name='codex', durable_dispatcher=broken_resolver,
    )
    assert resolve_durable_dispatcher(dispatcher, 'codex') is None
    # 不抛异常，dispatcher 构造完没坏
    assert dispatcher._durable_dispatcher is broken_resolver


# ---- 测试 5: 默认 None 时完全不碰 bridge ----


def test_no_durable_dispatcher_means_no_bridge_calls(tmp_path: Path, caplog) -> None:
    """``durable_dispatcher=None`` → tick 全程不调 attempt_durable_dispatch 内部逻辑。"""
    dispatcher = _build_dispatcher(tmp_path, agent_name='codex')  # durable_dispatcher=None
    job_id = _submit_codex(dispatcher)

    with caplog.at_level(logging.DEBUG, logger='cc_bridge_daemon.services.dispatcher_runtime.durable_dispatch'):
        dispatcher.tick()

    # 没有 durable_dispatch 日志
    assert not any(
        'durable_dispatch' in rec.message for rec in caplog.records
    ), f'unexpected durable_dispatch logs: {[r.message for r in caplog.records]!r}'
    # job 仍正常启动
    job = dispatcher.get(job_id)
    assert job is not None
    assert job.status is JobStatus.RUNNING


def test_durable_dispatch_skipped_for_reply_delivery(tmp_path: Path) -> None:
    """reply_delivery job 跳过（其 inbound 共享源 job）。"""
    durable = _RecordingDispatcher()
    dispatcher = _build_dispatcher(
        tmp_path, agent_name='codex', durable_dispatcher=durable,
    )

    # 手工构造一个 reply_delivery job
    from cc_bridge_daemon.api_models import JobRecord, TargetKind
    from cc_bridge_daemon.api_models_runtime.messages import MessageEnvelope as _ME
    reply_job = JobRecord(
        job_id='job-rd-001',
        submission_id=None,
        agent_name='codex',
        provider='codex',
        request=_ME(
            project_id='proj-3b',
            to_agent='codex',
            from_actor='user',
            body='reply',
            task_id=None,
            reply_to=None,
            message_type='reply_delivery',
            delivery_scope=DeliveryScope.SINGLE,
        ),
        status=JobStatus.QUEUED,
        terminal_decision=None,
        cancel_requested_at=None,
        created_at='2026-03-30T00:00:00Z',
        updated_at='2026-03-30T00:00:00Z',
        workspace_path=None,
        target_kind=TargetKind.AGENT,
        target_name='codex',
    )

    result = attempt_durable_dispatch(dispatcher, reply_job, started_at='2026-03-30T00:00:01Z')
    # reply_delivery 跳过 → 返回 None 且未触发 dispatch
    assert result is None
    assert durable.calls == []


# ---- 测试 6: 多 agent 路由 ----


def test_multi_agent_routes_via_callable_resolver(tmp_path: Path) -> None:
    """多 agent 场景下 callable resolver 按 agent_name 路由。"""
    codex_dispatcher = _RecordingDispatcher()
    claude_dispatcher = _RecordingDispatcher()
    by_agent = {
        'codex': codex_dispatcher,
        'claude': claude_dispatcher,
    }
    resolver = lambda name: by_agent.get(name)

    dispatcher = _build_dispatcher(
        tmp_path, agent_name='codex', durable_dispatcher=resolver,
    )
    assert resolve_durable_dispatcher(dispatcher, 'codex') is codex_dispatcher
    assert resolve_durable_dispatcher(dispatcher, 'claude') is claude_dispatcher
    # 未知 agent：resolver 返回 None
    assert resolve_durable_dispatcher(dispatcher, 'unknown') is None


def test_multi_agent_dispatch_invokes_only_target_dispatcher(tmp_path: Path) -> None:
    """callable resolver 把 dispatch() 派给正确的 dispatcher。"""
    codex_dispatcher = _RecordingDispatcher()
    resolver = lambda name: codex_dispatcher if name == 'codex' else None
    dispatcher = _build_dispatcher(
        tmp_path, agent_name='codex', durable_dispatcher=resolver,
    )
    job_id = _submit_codex(dispatcher)
    dispatcher.tick()

    # codex_dispatcher 收到一次调用
    assert len(codex_dispatcher.calls) == 1
    assert codex_dispatcher.calls[0]['binding_id'] == f'bdg-{job_id}'


# ---- sanity: JobDispatcher 构造签名兼容老调用 ----


def test_job_dispatcher_construction_backward_compatible(tmp_path: Path) -> None:
    """老用法（不传 durable_dispatcher）依然 work。"""
    project_root = tmp_path / 'repo-bc'
    ctx = _bootstrap_test_project(project_root)
    layout = PathLayout(project_root)
    config = _provider_config('codex')
    registry = AgentRegistry(layout, config)
    registry.upsert(_runtime('codex', project_id=ctx.project_id, layout=layout, pid=42))
    # 不传 durable_dispatcher
    dispatcher = JobDispatcher(
        layout, config, registry,
        clock=lambda: '2026-03-30T00:00:00Z',
    )
    assert dispatcher._durable_dispatcher is None

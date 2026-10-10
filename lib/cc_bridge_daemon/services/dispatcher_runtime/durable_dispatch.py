"""Step 3'-b: durable-dridge 接入 daemon 端 submit 路径。

设计哲学
--------
原提案（明确）：

    durable 模式的 pane 是**状态展示客户端**，不另开拥有同一 storage
    的 Pi CLI。submission 记账归 durable bridge，pane 只负责执行与展示。

因此 ``JobDispatcher.start_running_job`` 在「job 由 queued 转为 running」
的时点，把 ``DurableDispatcher.dispatch()`` 接进去：

  - durable 模式开启：按 ``job_id`` 派生 ``binding_id``（天然幂等）→ 把
    inbound_event / attempt / request 信息喂进 ``dispatch()`` → bridge
    写 ledger + claim + submit。
  - 桥失联 / claim 失败 / 任何异常：返回 fallback 信号，让 pane 路径继续
    执行 job（durable 只是增强，不能让 job 卡死）。

硬性约束（plan §硬性要求）
--------------------------
1. 默认行为逐字段不变 —— ``durable_dispatcher=None`` 时本模块完全不工作。
2. 防重复提交三道防线（见 :func:`attempt_durable_dispatch` 注释）：
   - ``binding_id`` 由 ``job_id`` 派生 → ``record_intent`` 同内容幂等
   - ``DurableDispatcher.dispatch()`` 重入安全（已 submitted 返回 ALREADY_TERMINAL）
   - 本接线点显式检查：账本里 ``submitted / delivered`` 直接跳过 dispatch
3. 失败降级要有日志，不许静默 ``except: pass``。
4. 多 agent 场景下：dispatcher 提供 ``Callable[[str], dispatcher | None]``
   路由；fallback 路径打日志记录"当前 daemon 仅注册单 dispatcher，agent Y 跳过"。

写集
----
只触碰 ``lib/cc_bridge_daemon/**`` 与 ``test/test_cc_bridge_daemon_*.py``；
不修改 ``lib/durable_bridge/**`` 或 ``tools/pi_durable_bridge/**``（Step 4 写集）。
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Callable

from cc_bridge_daemon.api_models import JobRecord
from mailbox_kernel import InboundEventStatus

from .reply_delivery import is_reply_delivery_job

_LOG = logging.getLogger(__name__)


# 类型：JobDispatcher._durable_dispatcher 可为 None / 单 dispatcher / 路由 callable
DurableResolver = Callable[[str], Any | None]


def resolve_durable_dispatcher(dispatcher, agent_name: str) -> Any | None:
    """把 ``JobDispatcher._durable_dispatcher`` 解析为该 agent 的 dispatcher。

    形态（按优先级匹配）：

    - None                          → 返回 None（legacy 模式）
    - callable(agent_name)         → 调用并返回结果（multi-agent router）
    - 其它对象                     → 当作单 dispatcher 原样返回
      （bootstrap 当前是 per-daemon 单例，本步不强求拆分）

    任何解析异常都会被吞掉并返回 None（**会**打 warning），
    防止路由失败把 job 卡死。
    """
    raw = getattr(dispatcher, '_durable_dispatcher', None)
    if raw is None:
        return None
    if callable(raw):
        try:
            return raw(agent_name)
        except Exception:
            _LOG.warning(
                'durable_dispatch: resolver raised for agent=%s; '
                'falling back to legacy pane path',
                agent_name,
                exc_info=True,
            )
            return None
    return raw


def attempt_durable_dispatch(
    dispatcher,
    job: JobRecord,
    *,
    started_at: str,
) -> dict[str, Any] | None:
    """在 ``start_running_job`` 早期尝试 durable dispatch。

    返回值：
    - None：未尝试（durable 模式未开启 / 无 inbound / reply_delivery 跳过 / 其它前置检查失败）
    - dict：包含 ``outcome`` 字段；调用方可记日志或埋指标。

    防重复提交三道防线
    ----------------
    1. ``binding_id = f"bdg-{job_id}"``：同 job 永远只产生同一 binding_id，
       ``BindingLedger.record_intent`` 同内容幂等（已 submitted/delivered
       直接返回 existing；同 input_hash intent 阶段直接返回 existing）。
    2. ``DurableDispatcher.dispatch()`` 自带重入安全：
       已 submitted 时返回 ``ALREADY_TERMINAL`` 而不是再 submit。
    3. 本函数显式查 ledger：若 ``submitted / delivered`` 已发生则跳过
       dispatch() 调用（既避免 ALREADY_TERMINAL 噪音，也避免 console 重复日志）。

    失败降级
    --------
    - dispatcher.dispatch() 抛异常 → 记 warning，返回 ``{'outcome': 'exception'}``
    - 任何前置检查（无 inbound / 无 storage path / is_reply_delivery_job）失败
      → 记 info，返回 None（这是正常的"durable 不适用"，不是错误）
    """
    agent_name = str(getattr(job, 'agent_name', '') or '').strip()
    durable = resolve_durable_dispatcher(dispatcher, agent_name)
    if durable is None:
        return None

    if is_reply_delivery_job(job):
        # reply_delivery job 的 inbound_event 共享源 job，不能独立 dispatch；
        # 跳过 durable 路径，pane 路径处理 reply delivery。
        return None

    inbound = _peek_inbound_for_job(dispatcher, job)
    if inbound is None:
        _LOG.info(
            'durable_dispatch: no QUEUED inbound for job_id=%s agent=%s '
            '(event missing or already advanced); legacy pane path continues',
            getattr(job, 'job_id', '?'),
            agent_name,
        )
        return None

    # 第 3 道防线：账本已 submitted / delivered → 跳过 dispatch
    binding_id = f'bdg-{job.job_id}'
    if _binding_already_terminal(durable, binding_id):
        _LOG.info(
            'durable_dispatch: binding_id=%s already terminal in ledger; '
            'skipping duplicate dispatch (job_id=%s agent=%s)',
            binding_id, job.job_id, agent_name,
        )
        return {
            'outcome': 'already_terminal_short_circuit',
            'binding_id': binding_id,
            'submission_id': None,
            'conversation_id': None,
            'detail': 'binding already terminal; no new dispatch invoked',
        }

    storage_path = _resolve_storage_path(dispatcher)
    if storage_path is None:
        _LOG.info(
            'durable_dispatch: layout has no '
            'cc_bridge_daemon_durable_bridge_storage_path (test stub layout?); '
            'skipping durable path for job_id=%s agent=%s',
            job.job_id, agent_name,
        )
        return None

    input_text = str(getattr(job.request, 'body', '') or '')
    input_hash = hashlib.sha256(input_text.encode('utf-8', 'replace')).hexdigest()
    request_id = f'req-{job.job_id}'

    attempt_id = str(getattr(inbound, 'attempt_id', '') or '')

    try:
        from durable_bridge.dispatcher import DispatchOutcome  # local import: keep lib free of constants
        outcome = durable.dispatch(
            binding_id=binding_id,
            inbound_event_id=inbound.inbound_event_id,
            message_id=str(inbound.message_id or ''),
            attempt_id=attempt_id,
            request_id=request_id,
            input_hash=input_hash,
            storage_path=storage_path,
            input_text=input_text,
        )
    except Exception as exc:  # noqa: BLE001
        # 桥失联 / claim 异常 / bridge_client 配置错：降级回 pane 路径
        _LOG.warning(
            'durable_dispatch: dispatch() raised for job_id=%s agent=%s: '
            '%s: %s; falling back to legacy pane path',
            job.job_id, agent_name, type(exc).__name__, exc,
        )
        return {
            'outcome': 'exception',
            'binding_id': binding_id,
            'submission_id': None,
            'conversation_id': None,
            'detail': f'{type(exc).__name__}: {exc}',
        }

    record = {
        'outcome': outcome.outcome.value
            if hasattr(outcome.outcome, 'value') else str(outcome.outcome),
        'binding_id': binding_id,
        'submission_id': outcome.submission_id,
        'conversation_id': outcome.conversation_id,
        'detail': outcome.detail,
    }
    _LOG.info(
        'durable_dispatch: job_id=%s agent=%s outcome=%s submission_id=%s '
        'conversation_id=%s detail=%s',
        job.job_id, agent_name, record['outcome'],
        record['submission_id'], record['conversation_id'], record['detail'],
    )
    return record


def _peek_inbound_for_job(dispatcher, job: JobRecord):
    """找出指向该 job 的 QUEUED inbound event。

    路径：``_attempt_store.get_latest_by_job_id(job_id)`` →
    ``_inbound_store.get_latest_for_attempt(agent_name, attempt_id)``。

    任何中间环节失败 / attempt 不存在 / inbound 不存在 / inbound 已被
    claim → 返回 None（让 attempt_durable_dispatch 走 fallback 日志）。
    """
    mb = getattr(dispatcher, '_message_bureau', None)
    if mb is None:
        return None
    attempt_store = getattr(mb, '_attempt_store', None)
    inbound_store = getattr(mb, '_inbound_store', None)
    if attempt_store is None or inbound_store is None:
        return None
    try:
        attempt = attempt_store.get_latest_by_job_id(job.job_id)
    except Exception:  # noqa: BLE001
        return None
    if attempt is None:
        return None
    try:
        inbound = inbound_store.get_latest_for_attempt(job.agent_name, attempt.attempt_id)
    except Exception:  # noqa: BLE001
        return None
    if inbound is None:
        return None
    if inbound.status is not InboundEventStatus.QUEUED:
        return None
    return inbound


def _binding_already_terminal(durable, binding_id: str) -> bool:
    """第 3 道防线：账本已 submitted / delivered → 跳过。

    直接读 ledger，避免触发 dispatch() 重入日志噪音。
    对 delivered / abandoned / submitted 都返回 True；对 intent /
    conversation_bound / None 返回 False。
    """
    ledger = getattr(durable, '_ledger', None)
    if ledger is None:
        return False
    try:
        record = ledger.lookup_by_binding_id(binding_id)
    except Exception:  # noqa: BLE001
        return False
    if record is None:
        return False
    phase = getattr(record, 'delivery_phase', None)
    return phase in ('submitted', 'delivered', 'abandoned')


def _resolve_storage_path(dispatcher) -> str | None:
    """从 ``dispatcher._layout`` 拿 durable-bridge storage_path。

    测试布局（MagicMock）通常没有这个属性；返回 None 时 caller 走
    fallback 日志路径。
    """
    layout = getattr(dispatcher, '_layout', None)
    if layout is None:
        return None
    try:
        return str(layout.cc_bridge_daemon_durable_bridge_storage_path)
    except AttributeError:
        return None


__all__ = [
    'attempt_durable_dispatch',
    'resolve_durable_dispatcher',
]

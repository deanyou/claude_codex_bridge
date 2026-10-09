"""worker outcome → durable-bridge ``result_kind`` / ``CompletionStatus`` 映射。

v4 09 节规格表：

    stop + 非空 reply     → COMPLETED / pi_run_stop            → result_kind='final'
    error                 → FAILED / pi_run_error              → result_kind='error'
    stop + 空 reply       → INCOMPLETE / pi_empty_reply        → result_kind='incomplete'
    缺 outcome            → INCOMPLETE / pi_native_outcome_missing → result_kind='inconclusive'
    其他 outcome          → INCOMPLETE / pi_run_finished:{outcome} → result_kind='inconclusive'

中间工具调用 / queued / 过期 bridge_epoch → 不进入映射表。

本模块只做纯函数映射；与具体 Pi provider / cc_bridge_daemon 完成端的
衔接属于 v4 实施"未完成工作"。
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class CompletionStatus(str, enum.Enum):
    COMPLETED = 'completed'
    FAILED = 'failed'
    INCOMPLETE = 'incomplete'


VALID_RESULT_KINDS = frozenset({'final', 'error', 'incomplete', 'inconclusive'})


@dataclass(frozen=True)
class CompletionDecision:
    """worker 终态评估结果。"""

    status: CompletionStatus
    reason: str
    result_kind: str

    def to_record(self) -> dict:
        return {
            'status': self.status.value,
            'reason': self.reason,
            'result_kind': self.result_kind,
        }


def _clean_reply(reply: object) -> str:
    if reply is None:
        return ''
    return str(reply).strip()


def map_worker_outcome(
    *,
    outcome: str | None,
    reply: object,
) -> CompletionDecision:
    """根据 (outcome, reply) 判定 worker 完成态。

    ``outcome``: worker 端报告的 stop_reason（'stop' / 'error' / 其他 / None）。
    ``reply``: 实际回复内容（可空字符串、None、任意可打印对象）。
    """
    cleaned = _clean_reply(reply)
    if outcome == 'error':
        return CompletionDecision(
            status=CompletionStatus.FAILED,
            reason='pi_run_error',
            result_kind='error',
        )
    if outcome == 'stop' and cleaned:
        return CompletionDecision(
            status=CompletionStatus.COMPLETED,
            reason='pi_run_stop',
            result_kind='final',
        )
    if outcome == 'stop' and not cleaned:
        return CompletionDecision(
            status=CompletionStatus.INCOMPLETE,
            reason='pi_empty_reply',
            result_kind='incomplete',
        )
    if not outcome:
        return CompletionDecision(
            status=CompletionStatus.INCOMPLETE,
            reason='pi_native_outcome_missing',
            result_kind='inconclusive',
        )
    # 其他 outcome（withdrawn / stale / max_steps / 等）
    return CompletionDecision(
        status=CompletionStatus.INCOMPLETE,
        reason=f'pi_run_finished:{outcome}',
        result_kind='inconclusive',
    )


def is_intermediate_or_unfinished(
    *,
    has_pending_tool_call: bool,
    in_queue_or_pending: bool,
    bridge_epoch_expired: bool,
) -> bool:
    """判定是否处于"中间态"，不能映射为终态。

    满足任一条件 → True（不进入映射表）：
        - ``has_pending_tool_call``：还有未结束的工具调用
        - ``in_queue_or_pending``：尚在队列 / pending / running
        - ``bridge_epoch_expired``：bridge_epoch 已过期，需重新对账
    """
    if has_pending_tool_call:
        return True
    if in_queue_or_pending:
        return True
    if bridge_epoch_expired:
        return True
    return False


__all__ = [
    'CompletionDecision',
    'CompletionStatus',
    'VALID_RESULT_KINDS',
    'is_intermediate_or_unfinished',
    'map_worker_outcome',
]

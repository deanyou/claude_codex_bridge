"""durable-bridge 派发编排器（v4 实施步骤 3）。

核心不变量（由 v4 步骤 2 决议明文规定，本模块逐条实现）：

1. 账本 intent 记录与 mailbox claim 是两个独立事实源。claim 失败
   （返回 None 或抛异常）**绝不**触发 ``mark_abandoned("claim_failed")``。
2. 派发只走"先 record_intent → claim → 核对 → submit → record_submission"
   的串行状态序列；任一步失败保留 intent，等待重新核对。
3. 重试必须复用同一 ``binding_id`` 与 ``requestId``；record_intent 的
   幂等保证多次调用不破坏账本。
4. ``record_delivery`` 只能在 ``submitted`` 之后；submitted 之前的报告
   一律拒绝（步骤 4 接 completion 时再扩展）。
5. reconcile 流程不能修改账本已有 phase；只读取并给出建议。
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any

from .binding_ledger import (
    BindingConflict,
    BindingLedger,
    BindingLedgerError,
    BindingRecord,
)
from .exceptions import DurableBridgeError
from .tcp_client import DurableBridgeClient


# ---- 公开枚举与结果 ----


class DispatchOutcome(str, enum.Enum):
    """派发终结态（区别于中间 phase 的 BindingRecord.delivery_phase）。

    终结态意味着 dispatcher 不再自动继续；调用方决定下一步。
    """

    # 路径：intent 写入后，claim 返回 None（队列顺序/竞争/事件已终态）
    # 含义：保持 intent，**不**调用 submit。调用方可重试 dispatch()。
    CLAIM_NOT_READY = 'claim_not_ready'

    # 路径：claim 抛异常；event 可能部分写入
    # 含义：账本保留 intent，**不**修改 phase，**不**调用 submit。
    # 调用方必须先 reconcile() 再决定下一步。
    CLAIM_RAISED = 'claim_raised'

    # 路径：账本 conflict（input_hash 冲突等）
    # 含义：账本保留既有记录，调用方应终止派发。
    LEDGER_CONFLICT = 'ledger_conflict'

    # 路径：submit 桥接失败（epoch mismatch / auth / 网络）
    # 含义：claim 已成功，submit 未完成；调用方应 reconcile 后重试。
    # 重试时复用 binding_id/requestId；若 bridge 端已记录，按幂等返回。
    SUBMIT_FAILED = 'submit_failed'

    # 路径：success
    # 含义：账本已 submitted，submission_id 可用。worker 完成后
    # report_result() 触发 record_delivery（步骤 4 接入 ack_reply）。
    SUBMITTED = 'submitted'

    # 路径：dispatch 入口发现账本已 abandoned / delivered
    # 含义：调用方不应再操作。
        # 路径：worker 报告结果，账本已 result_pending。
    # 含义：result_id 已记录，调用 mailbox.consume()。下步看
    # RESULT_DELIVERED 或 RESULT_CONFLICT。
    RESULT_PENDING = 'result_pending'

    # 路径：mailbox 端确认消费（status == CONSUMED），账本 delivered。
    # 含义：全路径完成。
    RESULT_DELIVERED = 'result_delivered'

    # 路径：consume() 返回 ABANDONED / SUPERSEDED 或其他非 CONSUMED 终态。
    # 含义：不能标 delivered，需人工 reconciliation；result_id 仍在账本里。
    RESULT_CONFLICT = 'result_conflict'

    ALREADY_TERMINAL = 'already_terminal'


@dataclass(frozen=True)
class DispatchResult:
    """一次 dispatch() 的完整结果。

    字段语义：
    - ``outcome``: 见 ``DispatchOutcome``
    - ``binding``: 派发涉及的 binding 记录（已落盘的最权威快照）
    - ``submission_id``: 仅在 ``SUBMITTED`` 时非空
    - ``conversation_id``: 仅在 ``SUBMITTED`` 时非空
    - ``detail``: 自由附加（错误消息 / 已观察到的事件 ID 等）
    """

    outcome: DispatchOutcome
    binding: BindingRecord
    submission_id: str | None = None
    conversation_id: str | None = None
    detail: str | None = None

    @property
    def success(self) -> bool:
        return self.outcome is DispatchOutcome.SUBMITTED


@dataclass(frozen=True)
class ReconcileObservation:
    """一次 reconcile() 的检查结果，不修改任何状态。

    字段语义：
    - ``binding``: 当前账本快照
    - ``mailbox_lease_present``: 该 agent 当前是否持有与 binding 关联的 lease
    - ``mailbox_event_status``: 关联的 inbound_event 当前 phase（"DELIVERING"
      / "CONSUMED" / None 表示不存在）
    - ``bridge_known_submission``: bridge 端是否认识 binding.submission_id
    - ``advice``: 字符串形式的建议
    """

    binding: BindingRecord
    mailbox_lease_present: bool | None
    mailbox_event_status: str | None
    bridge_known_submission: bool | None
    advice: str


# ---- 公开异常 ----


class DispatcherError(DurableBridgeError):
    """dispatcher 自身的不可恢复错误（参数错误 / 多次冲突）。"""


# ---- 编排器 ----


class DurableDispatcher:
    """单 agent 的派发编排器。

    线程安全：所有公开方法持有 ``self._lock``，可被多线程并发调用。
    不假设 mailbox / ledger / bridge client 自身线程安全；调用方在注入
    这些对象时需各自保证（mailbox kernel 与 ledger 已是线程安全）。
    """

    def __init__(
        self,
        *,
        ledger: BindingLedger,
        mailbox: Any,  # MailboxKernelService；不引入类型以避免跨模块导入
        bridge_client: DurableBridgeClient,
        bridge_epoch: str,
        agent_name: str,
        result_store: Any = None,  # 可选 ResultStore；不传则仅接受 result_payload_hash
    ) -> None:
        from threading import RLock

        self._ledger = ledger
        self._mailbox = mailbox
        self._bridge = bridge_client
        self._bridge_epoch = bridge_epoch
        self._agent_name = agent_name
        self._result_store = result_store  # 可选
        self._lock = RLock()

    # ---- 主入口 ----

    def dispatch(
        self,
        *,
        binding_id: str,
        inbound_event_id: str,
        message_id: str,
        attempt_id: str,
        request_id: str,
        input_hash: str,
        storage_path: str,
        input_text: str,
    ) -> DispatchResult:
        """执行"先 record_intent → claim → submit → record_submission"序列。

        重入安全：相同参数二次调用应得到与"已 submitted"一致的终结态
        （已 submitted 时返回 ALREADY_TERMINAL；这避免了重复 submit 风险）。
        """
        with self._lock:
            try:
                intent = self._ledger.record_intent(
                    binding_id,
                    inbound_event_id=inbound_event_id,
                    message_id=message_id,
                    attempt_id=attempt_id,
                    request_id=request_id,
                    input_hash=input_hash,
                    storage_path=storage_path,
                    bridge_epoch=self._bridge_epoch,
                )
            except BindingConflict as exc:
                # 已有 record 但被重新调用且 input_hash 冲突：
                # 我们读出当前 binding 并返回 LEDGER_CONFLICT
                current = self._ledger.lookup_by_binding_id(binding_id)
                if current is None:
                    raise DispatcherError(
                        f'conflict on record_intent but binding vanished: {binding_id!r}'
                    ) from exc
                return DispatchResult(
                    outcome=DispatchOutcome.LEDGER_CONFLICT,
                    binding=current,
                    detail=str(exc),
                )

            # 已 delivered / abandoned → ALREADY_TERMINAL
            if intent.delivery_phase in ('delivered', 'abandoned'):
                return DispatchResult(
                    outcome=DispatchOutcome.ALREADY_TERMINAL,
                    binding=intent,
                )

            # 已 submitted：仅当参数匹配时直接返回；不匹配视作 conflict
            if intent.delivery_phase == 'submitted':
                # 已 submitted 不应再次 dispatch；调用方应走 reconcile。
                return DispatchResult(
                    outcome=DispatchOutcome.ALREADY_TERMINAL,
                    binding=intent,
                    submission_id=intent.submission_id,
                    conversation_id=intent.conversation_id,
                    detail='binding already submitted; use reconcile() to advance',
                )

            # intent 阶段：继续 claim
            try:
                claimed = self._mailbox.claim(self._agent_name, inbound_event_id)
            except Exception as exc:  # noqa: BLE001
                # 抛异常：可能已部分写入。**不**改写账本，**不**改写 mailbox
                # 的 lease 状态。返回 CLAIM_RAISED；调用方应先 reconcile。
                latest = self._ledger.lookup_by_binding_id(binding_id) or intent
                return DispatchResult(
                    outcome=DispatchOutcome.CLAIM_RAISED,
                    binding=latest,
                    detail=f'{type(exc).__name__}: {exc}',
                )

            if claimed is None:
                # 队列顺序 / 竞争 / 事件已终态。
                # 保持 intent（账本不动），不调 submit。
                latest = self._ledger.lookup_by_binding_id(binding_id) or intent
                return DispatchResult(
                    outcome=DispatchOutcome.CLAIM_NOT_READY,
                    binding=latest,
                    detail='mailbox.claim returned None; preserve intent for retry',
                )

            # claim 成功 → submit
            return self._submit_and_record(binding_id, intent, input_text, request_id)

    # ---- 内部 submit ----

    def _submit_and_record(
        self,
        binding_id: str,
        intent: BindingRecord,
        input_text: str,
        request_id: str,
    ) -> DispatchResult:
        """submit 到 bridge；成功后 record_submission。

        状态序列（v4 步骤 4）：
            intent → conversation_bound → submitted

        关键：conversation_id 在 submit 之前先持久化。如果首次 submit
        已接受但回包丢失，重试仍会用同一 conversation（从账本读出）
        open，bridge 侧按 requestId 幂等返回原 submission。
        """
        # 1. 找到 / 创建 durable conversation。
        #    恢复路径：账本已记录 conversation_id，bridge 已认识它。
        #    首次路径：open() 不传 conversation_id 由 bridge 分配。
        try:
            open_result = self._open_durable_conversation(intent)
        except Exception as exc:  # noqa: BLE001
            latest = self._ledger.lookup_by_binding_id(binding_id) or intent
            return DispatchResult(
                outcome=DispatchOutcome.SUBMIT_FAILED,
                binding=latest,
                detail=f'open failed: {type(exc).__name__}: {exc}',
            )

        conversation_id = open_result['conversation_id']
        handle = open_result  # handle 字段是 open() 返回对象本身

        # 2. 立即持久补记 conversation（before submit）。
        #    如果此处异常：open 已发生，bridge 端有 conversation，
        #    账本未绑定；重试时 record_intent 幂等，_open_durable_conversation
        #    读 conversation_id=None 会 open 新 conversation——不幂等。
        #    所以这一步必须坚持做；如果失败，返回 SUBMIT_FAILED 让调用方重试。
        try:
            bound = self._ledger.record_conversation_bound(
                binding_id,
                conversation_id=conversation_id,
                bridge_epoch=self._bridge_epoch,
            )
        except BindingConflict as exc:
            latest = self._ledger.lookup_by_binding_id(binding_id) or intent
            return DispatchResult(
                outcome=DispatchOutcome.LEDGER_CONFLICT,
                binding=latest,
                detail=f'record_conversation_bound failed: {exc}',
            )

        # 3. submit（按 requestId 幂等；同 input 必须返回同一 submission_id）
        try:
            sub_payload = self._bridge.call(
                'submit',
                {
                    'handle': handle,
                    'conversation_id': conversation_id,
                    'requestId': request_id,
                    'input': input_text,
                },
            )['result']
        except Exception as exc:  # noqa: BLE001
            latest = self._ledger.lookup_by_binding_id(binding_id) or bound
            return DispatchResult(
                outcome=DispatchOutcome.SUBMIT_FAILED,
                binding=latest,
                detail=f'submit failed: {type(exc).__name__}: {exc}',
            )

        submission_id = str(sub_payload['submission_id'])
        # 4. 持久补记 submission
        try:
            after = self._ledger.record_submission(
                binding_id,
                conversation_id=conversation_id,
                submission_id=submission_id,
                bridge_epoch=self._bridge_epoch,
            )
        except BindingConflict as exc:
            # 已有 submitted 且不一致：桥返回了不同 submission_id。
            # 这是异常态：调用方应 reconcile。
            latest = self._ledger.lookup_by_binding_id(binding_id) or bound
            return DispatchResult(
                outcome=DispatchOutcome.LEDGER_CONFLICT,
                binding=latest,
                detail=f'submission_id mismatch after submit: {exc}',
            )

        return DispatchResult(
            outcome=DispatchOutcome.SUBMITTED,
            binding=after,
            submission_id=submission_id,
            conversation_id=conversation_id,
        )

    def _open_durable_conversation(self, intent: BindingRecord) -> dict:
        """对账本记录的 storage_path 打开 conversation。

        恢复路径：账本已有 conversation_id → 用 conversation_id open
        （让 bridge 端复用 conversation 内的 submission 映射）。
        首次路径：账本无 conversation_id → open() 让 bridge 分配。
        """
        params: dict[str, Any] = {'storage_path': intent.storage_path}
        if intent.conversation_id:
            params['conversation_id'] = intent.conversation_id
        return self._bridge.call('open', params)['result']

    # ---- 报告结果（步骤 4 接 ack_reply） ----

    def report_result(
        self,
        *,
        binding_id: str,
        result_id: str | None = None,
        result_kind: str,
        result_payload_hash: str | None = None,
        result_payload: Any = None,
        result_payload_ref: str | None = None,
    ) -> DispatchResult:
        """worker 报告结果 → 走三段交付：
        ``submitted → result_pending → delivered``。

        两种使用方式：
        - 传 ``result_payload``（dict / str / 任何可序列化对象）：dispatcher 调
          ``ResultStore`` 落盘完整结果。``result_payload_hash`` 留空则从
          payload 派生。这是推荐路径。
        - 仅传 ``result_payload_hash`` + ``result_payload_ref``：用于已经
          在外部存好完整结果、只把 hash 和 ref 报过来的场景。Ref 路径不
          受 ResultStore 管理。

        ``result_id`` 若不提供则根据 (binding_id, submission_id, result_kind) 派生。
        同一 binding 重复报告必须一致，不一致拒绝。

        ``delivered`` 仅在 ``mailbox.consume()`` 返回的 inbound_event 状态
        等于 ``CONSUMED`` 时才写入；其他终态（ABANDONED / SUPERSEDED）保留
        ``result_pending`` 并返回 ``RESULT_CONFLICT``，等待人工 reconciliation。
        """
        from .binding_ledger import VALID_RESULT_KINDS

        if result_kind not in VALID_RESULT_KINDS:
            raise DispatcherError(
                f'result_kind must be one of {sorted(VALID_RESULT_KINDS)}, '
                f'got {result_kind!r}'
            )

        # 决定结果持久化路径
        resolved_hash: str
        resolved_ref: str | None
        if result_payload is not None:
            # 推荐路径：完整 payload → ResultStore
            if self._result_store is None:
                raise DispatcherError(
                    f'result_payload given but no result_store configured '
                    f'for binding {binding_id!r}'
                )
            from .result_store import hash_payload as _hp
            resolved_hash = _hp(result_payload)
            self._result_store.save(binding_id, result_payload, resolved_hash)
            resolved_ref = f'results/{binding_id}.json'
        else:
            if not result_payload_hash:
                raise DispatcherError(
                    'must provide either result_payload (for ResultStore) '
                    'or result_payload_hash (for external ref)'
                )
            resolved_hash = result_payload_hash
            resolved_ref = result_payload_ref

        with self._lock:
            binding = self._ledger.lookup_by_binding_id(binding_id)
            if binding is None:
                raise DispatcherError(
                    f'report_result on missing binding: {binding_id!r}'
                )
            if binding.delivery_phase == 'delivered':
                # 幂等：已 delivered；同 result_id + 同 payload hash 才接受
                if result_id is not None and result_id != binding.result_id:
                    return DispatchResult(
                        outcome=DispatchOutcome.RESULT_CONFLICT,
                        binding=binding,
                        detail=f'result_id mismatch on delivered binding: '
                               f'on file={binding.result_id!r} new={result_id!r}',
                    )
                # 关键：比较实际派生出来的 hash（resolved_hash），不是入参
                # result_payload_hash。后者在 result_payload 路径上为 None，
                # 会导致同一 binding 重复报告完整 payload 时被误判为冲突。
                if (
                    binding.result_payload_hash is not None
                    and binding.result_payload_hash != resolved_hash
                ):
                    return DispatchResult(
                        outcome=DispatchOutcome.RESULT_CONFLICT,
                        binding=binding,
                        detail=f'result_payload_hash mismatch on delivered binding: '
                               f'on file={binding.result_payload_hash!r} '
                               f'new={resolved_hash!r}',
                    )
                return DispatchResult(
                    outcome=DispatchOutcome.RESULT_DELIVERED,
                    binding=binding,
                    submission_id=binding.submission_id,
                    conversation_id=binding.conversation_id,
                )
            if binding.delivery_phase not in ('submitted', 'result_pending'):
                # intent / conversation_bound / abandoned：不能记 result
                return DispatchResult(
                    outcome=DispatchOutcome.LEDGER_CONFLICT,
                    binding=binding,
                    detail=f'cannot report result in phase {binding.delivery_phase!r}',
                )

            # 1. 派生 result_id（若未提供）
            if result_id is None:
                result_id = _derive_result_id(
                    binding_id=binding_id,
                    submission_id=binding.submission_id or '',
                    result_kind=result_kind,
                )

            # 2. submitted → result_pending
            try:
                pending = self._ledger.record_result_pending(
                    binding_id,
                    result_id=result_id,
                    result_kind=result_kind,
                    result_payload_hash=resolved_hash,
                    result_payload_ref=resolved_ref,
                    bridge_epoch=self._bridge_epoch,
                )
            except BindingConflict as exc:
                # 同 result_id / payload / kind 一致 → 幂等；不一致 → 冲突
                latest = self._ledger.lookup_by_binding_id(binding_id) or binding
                return DispatchResult(
                    outcome=DispatchOutcome.RESULT_CONFLICT,
                    binding=latest,
                    detail=f'record_result_pending conflict: {exc}',
                )

            # 3. mailbox.consume()
            try:
                consume_result = self._mailbox.consume(
                    self._agent_name, binding.inbound_event_id
                )
            except Exception as exc:  # noqa: BLE001
                # consume 异常：保留 result_pending，调用方重试
                latest = self._ledger.lookup_by_binding_id(binding_id) or pending
                return DispatchResult(
                    outcome=DispatchOutcome.RESULT_CONFLICT,
                    binding=latest,
                    detail=f'mailbox.consume raised: {type(exc).__name__}: {exc}',
                )

            # 4. 验证 consume 返回的状态
            if consume_result is None:
                latest = self._ledger.lookup_by_binding_id(binding_id) or pending
                return DispatchResult(
                    outcome=DispatchOutcome.RESULT_CONFLICT,
                    binding=latest,
                    detail='mailbox.consume returned None; cannot confirm delivery',
                )
            actual_status = _status_value(consume_result)
            if actual_status != 'consumed':
                # 关键不变量：非 CONSUMED 终态不采纳
                latest = self._ledger.lookup_by_binding_id(binding_id) or pending
                return DispatchResult(
                    outcome=DispatchOutcome.RESULT_CONFLICT,
                    binding=latest,
                    detail=f'mailbox event status is {actual_status!r}, not '
                           f'"consumed"; result kept in result_pending for '
                           f'reconciliation',
                )

            # 5. result_pending → delivered
            try:
                delivered = self._ledger.record_delivery(
                    binding_id,
                    mailbox_consume_status='consumed',
                    bridge_epoch=self._bridge_epoch,
                )
            except BindingConflict as exc:
                latest = self._ledger.lookup_by_binding_id(binding_id) or pending
                return DispatchResult(
                    outcome=DispatchOutcome.RESULT_CONFLICT,
                    binding=latest,
                    detail=f'record_delivery conflict: {exc}',
                )
            return DispatchResult(
                outcome=DispatchOutcome.RESULT_DELIVERED,
                binding=delivered,
                submission_id=delivered.submission_id,
                conversation_id=delivered.conversation_id,
            )

    # ---- 恢复 ----

    def reconcile(
        self,
        *,
        binding_id: str | None = None,
        inbound_event_id: str | None = None,
    ) -> ReconcileObservation:
        """只读检查；不修改任何状态。

        接受 ``binding_id`` 或 ``inbound_event_id`` 二选一定位；
        给调用方"现在可以继续做 X 吗"的建议。
        """
        with self._lock:
            if binding_id is not None:
                binding = self._ledger.lookup_by_binding_id(binding_id)
            elif inbound_event_id is not None:
                binding = self._ledger.lookup_by_inbound_event(inbound_event_id)
            else:
                raise DispatcherError('reconcile requires binding_id or inbound_event_id')

            if binding is None:
                raise DispatcherError('binding not found for reconcile')

            mailbox_lease_present: bool | None = None
            mailbox_event_status: str | None = None
            try:
                lease = self._mailbox._lease_store.load(self._agent_name)
                if lease is not None and lease.inbound_event_id == binding.inbound_event_id:
                    mailbox_lease_present = True
                else:
                    mailbox_lease_present = False
                latest_event = self._mailbox._inbound_store.get_latest(
                    self._agent_name, binding.inbound_event_id
                )
                if latest_event is not None:
                    mailbox_event_status = _status_value(latest_event)
            except Exception:  # noqa: BLE001
                mailbox_lease_present = None
                mailbox_event_status = None

            bridge_known: bool | None = None
            if binding.submission_id is not None:
                try:
                    self._bridge.call('status', {'handle': {}, 'submission_id': binding.submission_id})
                    bridge_known = True
                except Exception:  # noqa: BLE001
                    bridge_known = False

            advice = _build_advice(binding, mailbox_lease_present, mailbox_event_status, bridge_known)
            return ReconcileObservation(
                binding=binding,
                mailbox_lease_present=mailbox_lease_present,
                mailbox_event_status=mailbox_event_status,
                bridge_known_submission=bridge_known,
                advice=advice,
            )


# Real MailboxKernelService 使用的状态值（与 InboundEventStatus 枚举对应）。
# 这里的常量是字符串值，真实场景下 mailbox_event_status 是 InboundEventStatus
# 枚举，_status_value() 会取出 .value；与本表小写字符串直接比较。
_TERMINAL_EVENT_STATUSES = frozenset({'consumed', 'superseded', 'abandoned'})
_ACTIVE_EVENT_STATUSES = frozenset({'created', 'queued', 'delivering'})


def _build_advice(
    binding: BindingRecord,
    lease_present: bool | None,
    event_status: str | None,
    bridge_known: bool | None,
) -> str:
    """由 binding + 外部观察 → 给调用方一段人话建议。"""
    phase = binding.delivery_phase
    if phase == 'delivered':
        return 'binding fully delivered; no action needed'
    if phase == 'abandoned':
        return (
            f'binding abandoned (reason={binding.abandoned_reason!r}); '
            f'no action'
        )
    if phase == 'result_pending':
        # 关键恢复点：result 已落账本/落盘，mailbox 端还未消费（或已消费但 record_delivery 未写）
        if event_status == 'consumed':
            return (
                'result_pending; mailbox event already consumed but ledger not '
                'delivered yet — call report_result() to advance to delivered '
                '(mailbox.consume is idempotent on terminal events)'
            )
        if event_status in _TERMINAL_EVENT_STATUSES:
            return (
                f'result_pending; mailbox event in terminal state '
                f'{event_status!r}; cannot mark delivered; reconcile manually'
            )
        return (
            'result_pending; safe to call report_result() to advance to '
            'delivered (will call mailbox.consume then record_delivery)'
        )
    if phase == 'submitted':
        if bridge_known is False:
            return (
                'submitted per ledger but bridge does not know the submission; '
                'investigate bridge storage before retry'
            )
        return (
            'submitted; awaiting worker result; safe to query bridge for status'
        )
    if phase == 'conversation_bound':
        # 关键恢复点：conversation_id 已落账本，submit 是否已接受未知
        if bridge_known:
            return (
                f'conversation_bound; bridge knows the conversation '
                f'({binding.conversation_id!r}); '
                f'safe to query bridge for submission '
                f'(conversation_id, request_id={binding.request_id!r}); '
                f'if found, advance via record_submission'
            )
        return (
            f'conversation_bound; conversation_id={binding.conversation_id!r} '
            f'persisted but bridge has no record — investigate; '
            f'cannot re-submit (requestId dedup would route to old conversation)'
        )
    # phase == 'intent'
    if event_status is None:
        return (
            'intent recorded; inbound event missing from mailbox — cannot '
            'dispatch; investigate mailbox store'
        )
    if event_status in _TERMINAL_EVENT_STATUSES:
        return (
            f'intent recorded; inbound event terminal ({event_status}); '
            f'do NOT mark abandoned (claim returned None may not mean task '
            f'terminated); investigate before any cleanup; '
            f'use force_abandon(confirmed_no_pending_submission=True) if '
            f'verified no forward progress'
        )
    if lease_present is False and event_status in _ACTIVE_EVENT_STATUSES:
        return (
            'intent recorded; mailbox event present but no matching lease — '
            'event append succeeded, lease save did not; '
            'safe to retry dispatch() (claim() will re-acquire and re-save lease)'
        )
    if lease_present is True:
        return 'intent recorded; lease held by current dispatch — already in flight'
    return 'intent recorded; safe to retry dispatch() if queue ordering permits'


# ---- helpers ----


def _status_value(record: Any) -> str:
    """从 mailbox 返回的事件记录中取 status 字符串值。

    兼容：status 是 enum（带 .value）或纯字符串。
    """
    if record is None:
        return ''
    status = getattr(record, 'status', None)
    if status is None:
        return ''
    value = getattr(status, 'value', None)
    if value is not None:
        return str(value)
    return str(status)


def _derive_result_id(
    *,
    binding_id: str,
    submission_id: str,
    result_kind: str,
) -> str:
    """稳定生成 result_id：不包含时间、bridge_epoch 或随机数。

    result_id = sha256(binding_id|submission_id|result_kind)[:32]
    """
    import hashlib as _hl

    material = f'{binding_id}|{submission_id}|{result_kind}'
    digest = _hl.sha256(material.encode('utf-8', 'replace')).hexdigest()
    return digest[:32]


__all__ = [
    'DispatchOutcome',
    'DispatchResult',
    'DispatcherError',
    'DurableDispatcher',
    'ReconcileObservation',
]

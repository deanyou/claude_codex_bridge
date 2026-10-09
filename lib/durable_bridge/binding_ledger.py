"""durable-bridge 绑定账本（v4 实施步骤 2）。

核心设计：
- 一份绑定一个 JSON 文件，原子写入（lib/storage/atomic.atomic_write_json）
- 不维护外部索引文件；查询用 in-memory 缓存，懒加载自目录扫描
- 缓存可被丢弃，丢弃后下次查询会从目录重建（满足"可重建"要求）
- 写入不依赖 mailbox 状态；映射保留至明确清理策略执行
- 步骤 2 不引入对外清理 API（受 lease 删除影响由调用方决定）

状态序列（v4 09 节 / 步骤 2 决议 2）：

    持久记录 intent
        ↓
    MailboxKernelService.claim()    ← claim 失败则不投递
        ↓
    核对认领成功
        ↓
    submit（durable）
        ↓
    持久补记 submission_id

intent 必须在首次外部调用前落盘；步骤 3 引入 record_delivery。
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from storage.atomic import atomic_write_json
from storage.paths import PathLayout

from .exceptions import DurableBridgeError


SCHEMA_VERSION = 2
VALID_PHASES = frozenset(
    {
        'intent',
        'conversation_bound',
        'submitted',
        'result_pending',
        'delivered',
        'abandoned',
    }
)

# 合法 result_kind（用于 record_result_pending 与 result_id 推导）
VALID_RESULT_KINDS = frozenset({'final', 'error', 'incomplete', 'inconclusive'})


class BindingLedgerError(DurableBridgeError):
    """账本语义错误。"""


class BindingConflict(BindingLedgerError):
    """写入与已落盘内容冲突（input_hash 不一致 / 重复状态转换）。"""


class BindingNotFound(BindingLedgerError):
    """指定 binding_id 不存在。"""


@dataclass(frozen=True)
class BindingRecord:
    """一份绑定的完整状态。"""

    schema_version: int
    binding_id: str
    inbound_event_id: str
    message_id: str
    attempt_id: str
    request_id: str
    input_hash: str
    storage_path: str
    bridge_epoch: str
    delivery_phase: str
    conversation_id: str | None = None
    submission_id: str | None = None
    result_id: str | None = None
    result_kind: str | None = None
    result_payload_hash: str | None = None
    result_payload_ref: str | None = None
    consume_attempted_at: str | None = None
    abandoned_reason: str | None = None
    created_at: str = ''
    updated_at: str = ''

    def to_record(self) -> dict:
        return {
            'schema_version': self.schema_version,
            'binding_id': self.binding_id,
            'inbound_event_id': self.inbound_event_id,
            'message_id': self.message_id,
            'attempt_id': self.attempt_id,
            'request_id': self.request_id,
            'input_hash': self.input_hash,
            'storage_path': self.storage_path,
            'bridge_epoch': self.bridge_epoch,
            'delivery_phase': self.delivery_phase,
            'conversation_id': self.conversation_id,
            'submission_id': self.submission_id,
            'result_id': self.result_id,
            'result_kind': self.result_kind,
            'result_payload_hash': self.result_payload_hash,
            'result_payload_ref': self.result_payload_ref,
            'consume_attempted_at': self.consume_attempted_at,
            'abandoned_reason': self.abandoned_reason,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_record(cls, record: Any) -> 'BindingRecord':
        if not isinstance(record, dict):
            raise BindingLedgerError('binding record must be a JSON object')
        try:
            return cls(
                schema_version=int(record.get('schema_version', SCHEMA_VERSION)),
                binding_id=str(record['binding_id']),
                inbound_event_id=str(record['inbound_event_id']),
                message_id=str(record['message_id']),
                attempt_id=str(record['attempt_id']),
                request_id=str(record['request_id']),
                input_hash=str(record['input_hash']),
                storage_path=str(record['storage_path']),
                bridge_epoch=str(record['bridge_epoch']),
                delivery_phase=str(record['delivery_phase']),
                conversation_id=(
                    str(record['conversation_id'])
                    if record.get('conversation_id') is not None
                    else None
                ),
                submission_id=(
                    str(record['submission_id'])
                    if record.get('submission_id') is not None
                    else None
                ),
                result_id=(
                    str(record['result_id'])
                    if record.get('result_id') is not None
                    else None
                ),
                result_kind=(
                    str(record['result_kind'])
                    if record.get('result_kind') is not None
                    else None
                ),
                result_payload_hash=(
                    str(record['result_payload_hash'])
                    if record.get('result_payload_hash') is not None
                    else None
                ),
                result_payload_ref=(
                    str(record['result_payload_ref'])
                    if record.get('result_payload_ref') is not None
                    else None
                ),
                consume_attempted_at=(
                    str(record['consume_attempted_at'])
                    if record.get('consume_attempted_at') is not None
                    else None
                ),
                abandoned_reason=(
                    str(record['abandoned_reason'])
                    if record.get('abandoned_reason') is not None
                    else None
                ),
                created_at=str(record.get('created_at') or ''),
                updated_at=str(record.get('updated_at') or ''),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BindingLedgerError(
                f'invalid binding record: {exc}'
            ) from exc


def _now_iso() -> str:
    """ISO8601 UTC 时间戳，秒精度。

    避免依赖项目里其他时间工具（这里账本只是个简单的持久层）。
    """
    import datetime as _dt

    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec='seconds')


class BindingLedger:
    """绑定账本：单进程读写安全，跨进程安全交给调用方（daemon 单 owner）。

    写操作：
        - 写文件前对同一 binding_id 的现有记录做"内容比较"决策：
          - 字段全部一致 → 跳过（保持 mtime 不变，便于测试）
          - 字段部分一致但关键字段不同 → 抛 BindingConflict
        - 文件写入走 atomic_write_json（已 fsync 父目录）
        - 写完后清掉内存缓存中该 binding 的旧值再回填
    """

    def __init__(self, layout: PathLayout) -> None:
        self._layout = layout
        self._dir = layout.cc_bridge_daemon_durable_bindings_dir
        self._lock = threading.RLock()
        # 缓存：binding_id -> record
        self._cache: dict[str, BindingRecord] | None = None

    # ---- 路径 ----

    def _path_for(self, binding_id: str) -> Path:
        return self._layout.cc_bridge_daemon_durable_binding_path(binding_id)

    # ---- 缓存 ----

    def _ensure_cache(self) -> dict[str, BindingRecord]:
        if self._cache is None:
            self._rebuild_cache()
        assert self._cache is not None
        return self._cache

    def _rebuild_cache(self) -> None:
        """从目录扫描重建缓存。

        单条记录解析失败不抛：跳过该文件并继续（账本对单条损坏隔离）。
        """
        cache: dict[str, BindingRecord] = {}
        if self._dir.exists():
            for path in sorted(self._dir.glob('*.json')):
                try:
                    text = path.read_text(encoding='utf-8')
                except OSError:
                    continue
                try:
                    raw = json.loads(text)
                except json.JSONDecodeError:
                    continue
                try:
                    rec = BindingRecord.from_record(raw)
                except BindingLedgerError:
                    continue
                cache[rec.binding_id] = rec
        self._cache = cache

    def drop_cache(self) -> None:
        """丢弃 in-memory 缓存（测试与恢复路径用）。"""
        with self._lock:
            self._cache = None

    def rebuild_index(self) -> int:
        """强制重扫并返回记录数。"""
        with self._lock:
            self._cache = None
            cache = self._ensure_cache()
            return len(cache)

    # ---- 内部写入 ----

    def _write_locked(self, record: BindingRecord) -> None:
        """持锁写入。"""
        path = self._path_for(record.binding_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(path, record.to_record())
        try:
            os.chmod(path, 0o600)
        except OSError:
            # Windows 不支持 chmod；ACL 由后续步骤补齐
            pass
        cache = self._ensure_cache()
        cache[record.binding_id] = record

    def _read_locked(self, binding_id: str) -> BindingRecord | None:
        cache = self._ensure_cache()
        return cache.get(binding_id)

    def _require_locked(self, binding_id: str) -> BindingRecord:
        rec = self._read_locked(binding_id)
        if rec is None:
            raise BindingNotFound(f'unknown binding_id: {binding_id!r}')
        return rec

    # ---- 公开写入 API ----

    def record_intent(
        self,
        binding_id: str,
        *,
        inbound_event_id: str,
        message_id: str,
        attempt_id: str,
        request_id: str,
        input_hash: str,
        storage_path: str,
        bridge_epoch: str,
        created_at: str | None = None,
    ) -> BindingRecord:
        """记录输入意图。同一 binding_id + 同内容 → 幂等；冲突 → 拒绝。"""
        _require_str('binding_id', binding_id)
        _require_str('inbound_event_id', inbound_event_id)
        _require_str('request_id', request_id)
        _require_str('input_hash', input_hash)
        _require_str('storage_path', storage_path)
        _require_str('bridge_epoch', bridge_epoch)
        with self._lock:
            existing = self._read_locked(binding_id)
            now = created_at or _now_iso()
            if existing is not None:
                # 已存在：校验关键字段一致性
                _check_consistency(
                    existing,
                    input_hash=input_hash,
                    request_id=request_id,
                    inbound_event_id=inbound_event_id,
                )
                # submission/delivery 已完成：保持原状（不重置）
                if existing.delivery_phase in ('submitted', 'delivered'):
                    return existing
                # intent 阶段重复记录 + 同内容 → 直接返回（幂等）
                if existing.delivery_phase == 'intent':
                    return existing
                # abandoned 状态：禁止再用同一 binding_id 重启
                raise BindingConflict(
                    f'binding {binding_id!r} already in phase {existing.delivery_phase!r}'
                )
            record = BindingRecord(
                schema_version=SCHEMA_VERSION,
                binding_id=binding_id,
                inbound_event_id=inbound_event_id,
                message_id=message_id,
                attempt_id=attempt_id,
                request_id=request_id,
                input_hash=input_hash,
                storage_path=storage_path,
                bridge_epoch=bridge_epoch,
                delivery_phase='intent',
                created_at=now,
                updated_at=now,
            )
            self._write_locked(record)
            return record

    def record_conversation_bound(
        self,
        binding_id: str,
        *,
        conversation_id: str,
        bridge_epoch: str,
        updated_at: str | None = None,
    ) -> BindingRecord:
        """补记 conversation_id——在 submit 之前调。

        v4 步骤 4 决定：conversation_id 必须在首次 submit 之前持久化，
        否则首次 submit 后回包丢失会让重试 open 出新 conversation，
        丢失 requestId 跨 conversation 的去重能力。

        转换：
            intent        → conversation_bound
            conversation_bound (idempotent on same id)
        """
        _require_str('binding_id', binding_id)
        _require_str('conversation_id', conversation_id)
        with self._lock:
            existing = self._require_locked(binding_id)
            if existing.delivery_phase == 'abandoned':
                raise BindingConflict(
                    f'binding {binding_id!r} is abandoned; cannot bind conversation'
                )
            if existing.delivery_phase in (
                'delivered',
                'result_pending',
                'submitted',
            ):
                # submitted 及之后不应重新绑 conversation；拒绝
                raise BindingConflict(
                    f'binding {binding_id!r} already in phase '
                    f'{existing.delivery_phase!r}; cannot rebind conversation'
                )
            if existing.delivery_phase == 'conversation_bound':
                if existing.conversation_id != conversation_id:
                    raise BindingConflict(
                        f'conversation_id mismatch for {binding_id!r}: '
                        f'on file={existing.conversation_id!r} new={conversation_id!r}'
                    )
                return existing
            # intent → conversation_bound
            now = updated_at or _now_iso()
            record = _replace(
                existing,
                conversation_id=conversation_id,
                delivery_phase='conversation_bound',
                updated_at=now,
            )
            self._write_locked(record)
            return record

    def record_submission(
        self,
        binding_id: str,
        *,
        conversation_id: str,
        submission_id: str,
        bridge_epoch: str,
        updated_at: str | None = None,
    ) -> BindingRecord:
        """补记 submission_id。

        只允许从 ``intent`` 或 ``conversation_bound`` 转换；submitted 之后
        不接受新的 submission（避免覆盖 result_pending / delivered）。
        """
        _require_str('binding_id', binding_id)
        _require_str('conversation_id', conversation_id)
        _require_str('submission_id', submission_id)
        with self._lock:
            existing = self._require_locked(binding_id)
            if existing.delivery_phase == 'abandoned':
                raise BindingConflict(
                    f'binding {binding_id!r} is abandoned; cannot record submission'
                )
            if existing.delivery_phase in ('result_pending', 'delivered'):
                # 已交付或交付中：submission 锁死，不能重新记录
                if existing.submission_id != submission_id:
                    raise BindingConflict(
                        f'submission_id mismatch for {binding_id!r}: '
                        f'on file={existing.submission_id!r} new={submission_id!r}'
                    )
                return existing
            if existing.delivery_phase == 'submitted':
                if existing.submission_id != submission_id:
                    raise BindingConflict(
                        f'submission_id mismatch for {binding_id!r}: '
                        f'on file={existing.submission_id!r} new={submission_id!r}'
                    )
                if existing.conversation_id != conversation_id:
                    raise BindingConflict(
                        f'conversation_id mismatch for {binding_id!r}: '
                        f'on file={existing.conversation_id!r} new={conversation_id!r}'
                    )
                return existing
            # intent 或 conversation_bound → submitted
            # 如果 conversation_id 与已记录的（conversation_bound 阶段）不一致 → 拒
            if (
                existing.conversation_id is not None
                and existing.conversation_id != conversation_id
            ):
                raise BindingConflict(
                    f'conversation_id mismatch for {binding_id!r}: '
                    f'on file={existing.conversation_id!r} new={conversation_id!r}'
                )
            now = updated_at or _now_iso()
            record = _replace(
                existing,
                conversation_id=conversation_id,
                submission_id=submission_id,
                delivery_phase='submitted',
                updated_at=now,
            )
            self._write_locked(record)
            return record

    def record_result_pending(
        self,
        binding_id: str,
        *,
        result_id: str,
        result_kind: str,
        result_payload_hash: str,
        result_payload_ref: str | None = None,
        bridge_epoch: str,
        updated_at: str | None = None,
    ) -> BindingRecord:
        """补记 result_id + payload 摘要——submitted → result_pending。

        重复报告必须参数一致；不一致拒绝。
        """
        _require_str('binding_id', binding_id)
        _require_str('result_id', result_id)
        _require_str('result_kind', result_kind)
        _require_str('result_payload_hash', result_payload_hash)
        if result_kind not in VALID_RESULT_KINDS:
            raise BindingLedgerError(
                f'result_kind must be one of {sorted(VALID_RESULT_KINDS)}, got {result_kind!r}'
            )
        with self._lock:
            existing = self._require_locked(binding_id)
            if existing.delivery_phase == 'abandoned':
                raise BindingConflict(
                    f'binding {binding_id!r} is abandoned; cannot record result'
                )
            if existing.delivery_phase == 'delivered':
                # 已交付：允许幂等但需校验 result_id 一致
                if existing.result_id != result_id:
                    raise BindingConflict(
                        f'result_id mismatch for delivered binding {binding_id!r}'
                    )
                return existing
            if existing.delivery_phase == 'result_pending':
                # 已 result_pending：同 id 同 payload → 幂等；否则拒
                if existing.result_id != result_id:
                    raise BindingConflict(
                        f'result_id mismatch for result_pending {binding_id!r}: '
                        f'on file={existing.result_id!r} new={result_id!r}'
                    )
                if existing.result_payload_hash != result_payload_hash:
                    raise BindingConflict(
                        f'result_payload_hash mismatch for {binding_id!r}'
                    )
                if existing.result_kind != result_kind:
                    raise BindingConflict(
                        f'result_kind mismatch for {binding_id!r}'
                    )
                return existing
            if existing.delivery_phase != 'submitted':
                raise BindingConflict(
                    f'cannot record result_pending from phase '
                    f'{existing.delivery_phase!r}; must be submitted'
                )
            now = updated_at or _now_iso()
            record = _replace(
                existing,
                result_id=result_id,
                result_kind=result_kind,
                result_payload_hash=result_payload_hash,
                result_payload_ref=result_payload_ref,
                delivery_phase='result_pending',
                updated_at=now,
            )
            self._write_locked(record)
            return record

    def record_delivery(
        self,
        binding_id: str,
        *,
        mailbox_consume_status: str,
        bridge_epoch: str,
        updated_at: str | None = None,
    ) -> BindingRecord:
        """result_pending → delivered。

        重要：``delivered`` 表示 mailbox 端已确认消费（status == CONSUMED）。
        仅允许从 ``result_pending`` 转换；mailbox 实际状态由调用方验证后
        以 ``mailbox_consume_status`` 参数传入。
        """
        _require_str('binding_id', binding_id)
        _require_str('mailbox_consume_status', mailbox_consume_status)
        with self._lock:
            existing = self._require_locked(binding_id)
            if existing.delivery_phase == 'delivered':
                return existing
            if existing.delivery_phase != 'result_pending':
                raise BindingConflict(
                    f'cannot record delivery from phase {existing.delivery_phase!r}; '
                    f'must be result_pending'
                )
            # 关键不变量：mailbox 端必须报 CONSUMED；其他终态不采纳
            if mailbox_consume_status != 'consumed':
                raise BindingConflict(
                    f'mailbox event status is {mailbox_consume_status!r}, '
                    f'not "consumed"; refusing to mark delivered'
                )
            now = updated_at or _now_iso()
            record = _replace(
                existing,
                consume_attempted_at=now,
                delivery_phase='delivered',
                updated_at=now,
            )
            self._write_locked(record)
            return record

    def mark_abandoned(
        self,
        binding_id: str,
        *,
        reason: str,
        bridge_epoch: str,
        updated_at: str | None = None,
    ) -> BindingRecord:
        """标记放弃（人工或显式清理）。

        仅允许从 ``intent`` phase 主动放弃。``conversation_bound`` 意味
        着 bridge 端已有 conversation，但 submit 是否已接受（回包丢失）
        未知：仅凭账本无法证实无未决 submission。需调用 ``force_abandon``
        并由 caller 显式确认 "已查询原提交" 或 "已补交结果"。

        ``submitted`` / ``result_pending`` / ``delivered`` 意味着下游已
        收到任务或结果，更不能主动废弃——只能由 reconciliation 流程证实
        无未决提交、无未决执行、无未决交付后才能结束。
        """
        _require_str('binding_id', binding_id)
        _require_str('reason', reason)
        with self._lock:
            existing = self._require_locked(binding_id)
            if existing.delivery_phase == 'abandoned':
                if existing.abandoned_reason != reason:
                    raise BindingConflict(
                        f'abandoned_reason mismatch for {binding_id!r}'
                    )
                return existing
            if existing.delivery_phase in (
                'conversation_bound',
                'submitted',
                'result_pending',
                'delivered',
            ):
                raise BindingConflict(
                    f'cannot abandon binding {binding_id!r} in phase '
                    f'{existing.delivery_phase!r}: forward progress detected; '
                    f'use force_abandon() after confirming no pending submission'
                )
            now = updated_at or _now_iso()
            record = _replace(
                existing,
                abandoned_reason=reason,
                delivery_phase='abandoned',
                updated_at=now,
            )
            self._write_locked(record)
            return record

    def force_abandon(
        self,
        binding_id: str,
        *,
        reason: str,
        bridge_epoch: str,
        confirmed_no_pending_submission: bool = False,
        confirmed_no_pending_delivery: bool = False,
        updated_at: str | None = None,
    ) -> BindingRecord:
        """强制放弃——只允许明确证实无未决状态后使用。

        ``conversation_bound`` / ``submitted`` 需 ``confirmed_no_pending_submission=True``，
        表明调用方已通过 bridge 查过 (conversation_id, request_id) 无 submission。
        ``result_pending`` 需 ``confirmed_no_pending_delivery=True``，
        表明调用方已查过 mailbox 端事件状态并非 CONSUMED，或已有理由不交付。
        ``delivered`` 永远不能 force_abandon。

        双重确认防止误清账本里"已 commit 到下游"的工作。
        """
        _require_str('binding_id', binding_id)
        _require_str('reason', reason)
        with self._lock:
            existing = self._require_locked(binding_id)
            if existing.delivery_phase == 'abandoned':
                if existing.abandoned_reason != reason:
                    raise BindingConflict(
                        f'abandoned_reason mismatch for {binding_id!r}'
                    )
                return existing
            if existing.delivery_phase == 'delivered':
                raise BindingConflict(
                    f'cannot force_abandon delivered binding {binding_id!r}'
                )
            if existing.delivery_phase in ('conversation_bound', 'submitted'):
                if not confirmed_no_pending_submission:
                    raise BindingConflict(
                        f'force_abandon from {existing.delivery_phase!r} requires '
                        f'confirmed_no_pending_submission=True; query the bridge '
                        f'first to confirm no submission for '
                        f'(conversation_id={existing.conversation_id!r}, '
                        f'request_id={existing.request_id!r})'
                    )
            if existing.delivery_phase == 'result_pending':
                if not confirmed_no_pending_delivery:
                    raise BindingConflict(
                        f'force_abandon from result_pending requires '
                        f'confirmed_no_pending_delivery=True; verify the mailbox '
                        f'event status is not consumed before abandoning'
                    )
            now = updated_at or _now_iso()
            record = _replace(
                existing,
                abandoned_reason=reason,
                delivery_phase='abandoned',
                updated_at=now,
            )
            self._write_locked(record)
            return record

    # ---- 公开查询 API ----

    def lookup_by_binding_id(self, binding_id: str) -> BindingRecord | None:
        with self._lock:
            return self._read_locked(binding_id)

    def lookup_by_inbound_event(self, inbound_event_id: str) -> BindingRecord | None:
        with self._lock:
            cache = self._ensure_cache()
            for rec in cache.values():
                if rec.inbound_event_id == inbound_event_id:
                    return rec
            return None

    def lookup_by_request_id(self, request_id: str) -> BindingRecord | None:
        with self._lock:
            cache = self._ensure_cache()
            for rec in cache.values():
                if rec.request_id == request_id:
                    return rec
            return None

    def lookup_by_submission_id(self, submission_id: str) -> BindingRecord | None:
        with self._lock:
            cache = self._ensure_cache()
            for rec in cache.values():
                if rec.submission_id == submission_id:
                    return rec
            return None

    def list_all(self) -> tuple[BindingRecord, ...]:
        with self._lock:
            cache = self._ensure_cache()
            return tuple(cache.values())


# ---- helpers ----


def _require_str(name: str, value: Any) -> None:
    if not isinstance(value, str) or not value:
        raise BindingLedgerError(f'{name} must be a non-empty string')


def _check_consistency(
    existing: BindingRecord,
    *,
    input_hash: str,
    request_id: str,
    inbound_event_id: str,
) -> None:
    if existing.input_hash != input_hash:
        raise BindingConflict(
            f'input_hash mismatch for {existing.binding_id!r}: '
            f'on file={existing.input_hash[:12]}... new={input_hash[:12]}...'
        )
    if existing.request_id != request_id:
        raise BindingConflict(
            f'request_id mismatch for {existing.binding_id!r}: '
            f'on file={existing.request_id!r} new={request_id!r}'
        )
    if existing.inbound_event_id != inbound_event_id:
        raise BindingConflict(
            f'inbound_event_id mismatch for {existing.binding_id!r}: '
            f'on file={existing.inbound_event_id!r} new={inbound_event_id!r}'
        )


def _replace(record: BindingRecord, **changes) -> BindingRecord:
    """用 binding.dataclass replace-style 派生新记录。"""
    from dataclasses import replace as _dc_replace

    return _dc_replace(record, **changes)


__all__ = [
    'BindingConflict',
    'BindingLedger',
    'BindingLedgerError',
    'BindingNotFound',
    'BindingRecord',
    'SCHEMA_VERSION',
]

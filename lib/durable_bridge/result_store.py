"""durable-bridge 完整结果持久化（v4 实施步骤 4 缺口补齐）。

职责：
- 把 worker 返回的完整结果（或可恢复的引用）落盘
- 账本 BindingRecord 只存 result_payload_hash（摘要）+ result_payload_ref（路径）
- 不依赖 mailbox.consume 持久化结果；consume 只标记消费事件
- 跨进程可见：通过 PathLayout 目录扫描读取

设计要点：
- 一份 binding 一份 JSON，原子写入
- 重复写：同 hash → 幂等；不同 hash → 拒绝（防覆盖）
- 缺失/损坏：返回 None 而非抛异常（隔离单条错误）
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from storage.atomic import atomic_write_json
from storage.paths import PathLayout

from .binding_ledger import BindingConflict, BindingLedgerError


class ResultStoreError(BindingLedgerError):
    """结果存储语义错误。"""


@dataclass(frozen=True)
class ResultRecord:
    """一份完整结果。"""

    binding_id: str
    payload: Any
    payload_hash: str
    saved_at: str

    def to_record(self) -> dict:
        return {
            'binding_id': self.binding_id,
            'payload': self.payload,
            'payload_hash': self.payload_hash,
            'saved_at': self.saved_at,
        }

    @classmethod
    def from_record(cls, record: Any) -> 'ResultRecord':
        if not isinstance(record, dict):
            raise ResultStoreError('result record must be a JSON object')
        try:
            return cls(
                binding_id=str(record['binding_id']),
                payload=record['payload'],
                payload_hash=str(record['payload_hash']),
                saved_at=str(record.get('saved_at') or ''),
            )
        except (KeyError, TypeError) as exc:
            raise ResultStoreError(f'invalid result record: {exc}') from exc


def _now_iso() -> str:
    import datetime as _dt

    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec='seconds')


def hash_payload(payload: Any) -> str:
    """计算 payload 摘要（规范化 JSON 后 sha256）。"""
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode('utf-8', 'replace')).hexdigest()


class ResultStore:
    """完整结果的目录式持久化存储。"""

    def __init__(self, layout: PathLayout) -> None:
        self._layout = layout
        self._dir = layout.cc_bridge_daemon_durable_bindings_dir / 'results'
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _path_for(self, binding_id: str) -> Path:
        if not isinstance(binding_id, str) or not binding_id:
            raise ResultStoreError('binding_id must be a non-empty string')
        return self._dir / f'{binding_id}.json'

    def save(
        self,
        binding_id: str,
        payload: Any,
        payload_hash: str | None = None,
    ) -> Path:
        """原子写入完整结果。

        - ``payload_hash`` 若不提供则用 ``hash_payload(payload)`` 派生
        - 同 binding + 同 hash → 幂等（不重写）
        - 同 binding + 不同 hash → 拒绝（防覆盖）
        """
        if payload_hash is None:
            payload_hash = hash_payload(payload)
        if not isinstance(payload_hash, str) or not payload_hash:
            raise ResultStoreError('payload_hash must be a non-empty string')

        path = self._path_for(binding_id)
        with self._lock:
            if path.exists():
                existing = self._load_locked(path)
                if existing is not None:
                    if existing.payload_hash == payload_hash:
                        return path  # 幂等
                    raise BindingConflict(
                        f'payload_hash mismatch for binding {binding_id!r}: '
                        f'on file={existing.payload_hash[:12]}... '
                        f'new={payload_hash[:12]}...'
                    )
            record = ResultRecord(
                binding_id=binding_id,
                payload=payload,
                payload_hash=payload_hash,
                saved_at=_now_iso(),
            )
            atomic_write_json(path, record.to_record())
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            return path

    def load(self, binding_id: str) -> ResultRecord | None:
        """读取完整结果；不存在或损坏返回 None。"""
        path = self._path_for(binding_id)
        with self._lock:
            return self._load_locked(path)

    def _load_locked(self, path: Path) -> ResultRecord | None:
        if not path.exists():
            return None
        try:
            text = path.read_text(encoding='utf-8')
        except OSError:
            return None
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            return None
        try:
            return ResultRecord.from_record(raw)
        except ResultStoreError:
            return None

    def exists(self, binding_id: str) -> bool:
        return self._path_for(binding_id).exists()

    def remove(self, binding_id: str) -> bool:
        """删除完整结果文件（仅用于显式清理）。"""
        path = self._path_for(binding_id)
        with self._lock:
            if not path.exists():
                return False
            try:
                path.unlink()
                return True
            except OSError:
                return False


__all__ = [
    'ResultRecord',
    'ResultStore',
    'ResultStoreError',
    'hash_payload',
]

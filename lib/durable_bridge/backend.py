"""durable backend 抽象与占位实现。

v4 实施步骤 1 只需要协议骨架能跑通；真实 pi-durable 绑定在后续步骤接入。
这里的 ``InMemoryDurableBackend`` 用于：

1. 让 BridgeServer 有可调用的方法，验证协议层往返
2. 故障注入测试（步骤 3/4 会用到）可以脱离真 storage 复现

接口（v4 规格 09 节 RPC 表）：
- open(storage_path[, conversation_id]) -> handle
- submit(handle, input, requestId) -> submission_id
- status / wait / resume / read_inbox / read_transcript

每个真实方法都对齐"按 (conversation_id, requestId) 幂等"——这是
后续绑定账本与对账的基石，所以即便占位实现也必须把幂等语义做对。

步骤 2 新增：
- ``open(..., conversation_id=X)`` 支持恢复指定会话；找不到 X 时拒绝
- ``register_conversation(conversation_id)`` 显式注入已知会话（用于测试
  与真实场景下"发现 SQLite 中已有 conversation"后的回灌）
- ``list_conversations()`` 用于索引重建
"""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from .exceptions import DurableBridgeError


class BackendError(DurableBridgeError):
    """后端语义错误（非协议错）。"""


class BackendNotFound(BackendError):
    """指定 handle / conversation / submission 不存在。"""


class BackendInvalidState(BackendError):
    """操作与当前状态冲突（如 resume 时 storage 已被接管）。"""


@dataclass(frozen=True)
class SubmissionState:
    """一次 submission 的完整状态。"""

    submission_id: str
    conversation_id: str
    request_id: str
    input_hash: str
    status: str  # 'pending' | 'settled'
    text: str | None = None
    finish_reason: str | None = None
    created_at: float = field(default_factory=time.time)
    settled_at: float | None = None


class DurableBackend(Protocol):
    """bridge 后端契约。

    关键不变量：
    - 同一 (conversation_id, requestId) 的 submit 必返回同一 submission_id
    - 同一 input_hash 的 submit 必返回同一 submission_id
    - 不同 input_hash 但同 requestId 抛 BackendError（不可调和冲突）
    - open() 不指定 conversation_id 时生成新会话；指定时必须已存在
    """

    def open(self, storage_path: str, *, conversation_id: str | None = None) -> dict:
        ...

    def submit(
        self,
        handle: dict,
        conversation_id: str,
        request_id: str,
        input_text: str,
    ) -> SubmissionState:
        ...

    def status(self, handle: dict, submission_id: str) -> SubmissionState:
        ...

    def close(self, handle: dict) -> None:
        ...

    def register_conversation(self, conversation_id: str) -> None:
        """注入已知 conversation（用于恢复场景：扫描 SQLite 后回灌）。"""
        ...

    def list_conversations(self) -> tuple[str, ...]:
        """返回已知 conversation_id 列表（用于索引重建）。"""
        ...


def _input_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8', 'replace')).hexdigest()


class InMemoryDurableBackend:
    """线程安全的进程内 backend 占位。

    模拟 pi-durable 的三段语义：
    - open: 不指定 conversation_id 时新建；指定时必须在已知集合中，
      否则抛 BackendNotFound（防止错绑——恢复路径必须用 binding ledger
      告知的 conversation_id，绝不能 "open + auto-create"）。
    - submit: 按 (conversation_id, requestId) 幂等；同 input_hash 复用。
    - status: 查询 submission；不存在抛 BackendNotFound。
    - close: 仅移除 handle_id；conversation 与 submission 仍可查询。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._handles: dict[str, dict] = {}
        self._known_conversations: set[str] = set()
        self._by_conv: dict[str, dict[str, SubmissionState]] = {}
        self._by_submission: dict[str, SubmissionState] = {}

    def open(self, storage_path: str, *, conversation_id: str | None = None) -> dict:
        if not isinstance(storage_path, str) or not storage_path:
            raise BackendError('storage_path must be a non-empty string')
        with self._lock:
            handle_id = uuid.uuid4().hex
            if conversation_id is None:
                new_conv = uuid.uuid4().hex
                self._known_conversations.add(new_conv)
                self._by_conv.setdefault(new_conv, {})
                resolved_conversation_id = new_conv
            else:
                if not isinstance(conversation_id, str) or not conversation_id:
                    raise BackendError('conversation_id must be a non-empty string')
                if conversation_id not in self._known_conversations:
                    raise BackendNotFound(
                        f'unknown conversation_id: {conversation_id!r} '
                        '(refusing to auto-create on resume; must be registered first)'
                    )
                resolved_conversation_id = conversation_id
            handle = {
                'handle_id': handle_id,
                'storage_path': storage_path,
                'conversation_id': resolved_conversation_id,
            }
            self._handles[handle_id] = handle
            return handle

    def submit(
        self,
        handle: dict,
        conversation_id: str,
        request_id: str,
        input_text: str,
    ) -> SubmissionState:
        if not isinstance(input_text, str):
            raise BackendError('input_text must be a string')
        if not isinstance(request_id, str) or not request_id:
            raise BackendError('request_id must be a non-empty string')
        with self._lock:
            handle_id = handle.get('handle_id') if isinstance(handle, dict) else None
            stored = self._handles.get(handle_id) if isinstance(handle_id, str) else None
            if stored is None:
                raise BackendNotFound(f'unknown handle: {handle_id!r}')
            if stored.get('conversation_id') != conversation_id:
                raise BackendInvalidState(
                    f'conversation mismatch: handle={stored.get("conversation_id")!r} '
                    f'requested={conversation_id!r}'
                )
            if conversation_id not in self._known_conversations:
                raise BackendNotFound(f'unknown conversation_id: {conversation_id!r}')
            conv_index = self._by_conv.setdefault(conversation_id, {})
            existing = conv_index.get(request_id)
            input_hash = _input_hash(input_text)
            if existing is not None:
                if existing.input_hash != input_hash:
                    raise BackendError(
                        'requestId reused with different input '
                        f'(existing hash={existing.input_hash[:12]}..., '
                        f'new hash={input_hash[:12]}...)'
                    )
                return existing
            sub = SubmissionState(
                submission_id=uuid.uuid4().hex,
                conversation_id=conversation_id,
                request_id=request_id,
                input_hash=input_hash,
                status='settled',
                text=input_text,
                finish_reason='replayed',
                settled_at=time.time(),
            )
            conv_index[request_id] = sub
            self._by_submission[sub.submission_id] = sub
            return sub

    def status(self, handle: dict, submission_id: str) -> SubmissionState:
        with self._lock:
            sub = self._by_submission.get(submission_id)
            if sub is None:
                raise BackendNotFound(f'unknown submission_id: {submission_id!r}')
            return sub

    def close(self, handle: dict) -> None:
        with self._lock:
            handle_id = handle.get('handle_id') if isinstance(handle, dict) else None
            if isinstance(handle_id, str):
                # 仅移除 handle_id；conversation 与 submission 仍可查询，
                # 让客户端在 handle 失效后仍能通过 conversation_id + requestId 找回。
                self._handles.pop(handle_id, None)

    def register_conversation(self, conversation_id: str) -> None:
        """注入已知 conversation。"""
        if not isinstance(conversation_id, str) or not conversation_id:
            raise BackendError('conversation_id must be a non-empty string')
        with self._lock:
            self._known_conversations.add(conversation_id)
            self._by_conv.setdefault(conversation_id, {})

    def list_conversations(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._known_conversations))


__all__ = [
    'BackendError',
    'BackendInvalidState',
    'BackendNotFound',
    'DurableBackend',
    'InMemoryDurableBackend',
    'SubmissionState',
]

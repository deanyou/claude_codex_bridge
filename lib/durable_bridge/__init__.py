"""durable-bridge 桥接层（v4 实施第 1 步）。

形态：常驻 Node-like 进程占位（当前为 Python 简化版）独占 SQLite storage
并通过 127.0.0.1 TCP loopback + JSON-RPC 2.0 与 CC Bridge daemon 通信。

本模块交付：
- storage 独占锁（POSIX fcntl / Windows msvcrt 跨进程互斥）
- endpoint.json 原子发布（host/port/pid/bridge_epoch/protocol_version/token）
- 长度受限的 JSON-RPC 2.0 协议（每行一帧，UTF-8）
- token + bridge_epoch 鉴权
- 客户端重连退避（250ms→5s 抖动，30s 总预算）

不交付（待后续步骤）：
- pi-durable 真实 binding（目前使用 InMemoryDurableBackend 占位）
- 绑定账本（步骤 2）
- 派发幂等 / 对账（步骤 3）
- completion 映射（步骤 4）
"""

from __future__ import annotations

from .bridge import BridgeServer
from .binding_ledger import (
    BindingConflict,
    BindingLedger,
    BindingLedgerError,
    BindingNotFound,
    BindingRecord,
)
from .completion import (
    CompletionDecision,
    CompletionStatus,
    is_intermediate_or_unfinished,
    map_worker_outcome,
)
from .dispatcher import (
    DispatchOutcome,
    DispatchResult,
    DispatcherError,
    DurableDispatcher,
    ReconcileObservation,
)
from .endpoint import BridgeEndpoint, publish_endpoint, read_endpoint, revoke_endpoint
from .exceptions import (
    BridgeAuthError,
    BridgeBusyError,
    BridgeEpochMismatch,
    BridgeOversizedFrame,
    BridgeProtocolError,
    BridgeStorageLockBusy,
    DurableBridgeError,
)
from .protocol import (
    DEFAULT_MAX_FRAME_BYTES,
    PROTOCOL_VERSION,
    build_error_response,
    build_notification,
    build_request,
    build_result_response,
    parse_frame_line,
)
from .reconnect import ReconnectPolicy, compute_reconnect_deadline, next_reconnect_delay
from .storage_lock import StorageLockHandle, acquire_storage_lock, release_storage_lock

__all__ = [
    'BindingConflict',
    'BindingLedger',
    'BindingLedgerError',
    'BindingNotFound',
    'BindingRecord',
    'BridgeAuthError',
    'CompletionDecision',
    'BridgeBusyError',
    'BridgeEndpoint',
    'BridgeEpochMismatch',
    'BridgeOversizedFrame',
    'BridgeProtocolError',
    'BridgeServer',
    'BridgeStorageLockBusy',
    'CompletionStatus',
    'DEFAULT_MAX_FRAME_BYTES',
    'DispatchOutcome',
    'DispatchResult',
    'DispatcherError',
    'DurableBridgeError',
    'DurableDispatcher',
    'PROTOCOL_VERSION',
    'ReconcileObservation',
    'ReconnectPolicy',
    'ResultRecord',
    'ResultStore',
    'ResultStoreError',
    'StorageLockHandle',
    'acquire_storage_lock',
    'build_error_response',
    'build_notification',
    'build_request',
    'build_result_response',
    'compute_reconnect_deadline',
    'hash_payload',
    'is_intermediate_or_unfinished',
    'map_worker_outcome',
    'next_reconnect_delay',
    'parse_frame_line',
    'publish_endpoint',
    'read_endpoint',
    'release_storage_lock',
    'revoke_endpoint',
]

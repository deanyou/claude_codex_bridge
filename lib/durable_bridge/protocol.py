"""JSON-RPC 2.0 帧构造与解析（durable-bridge 专用）。

帧规则（v4 09 节）：
- UTF-8 文本
- 每个 TCP 消息以 ``\\n`` 结束（一行一帧）
- 单帧上限 1 MiB（可配）
- 消息体本身是合法 JSON-RPC 2.0 载荷

鉴权字段约定（不是 JSON-RPC 标准字段，是 durable-bridge 扩展）：
- 服务端在 ``open``/``hello`` 之外的所有请求都强制带 ``token`` 与 ``bridge_epoch``
- 不匹配时返回 -32001（epoch）/ -32002（token）错误
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from .exceptions import BridgeOversizedFrame, BridgeProtocolError


PROTOCOL_VERSION = 1
DEFAULT_MAX_FRAME_BYTES = 1024 * 1024  # 1 MiB

# JSON-RPC 2.0 错误码
ERR_PARSE = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_INTERNAL = -32603
# 服务自定义错误码（-32000 ~ -32099 范围留给实现）
ERR_EPOCH_MISMATCH = -32001
ERR_AUTH_FAILED = -32002
ERR_LOCK_BUSY = -32003
ERR_FRAME_TOO_LARGE = -32004


def _ensure_str_id(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if value is None:
        return ''
    raise BridgeProtocolError(f'JSON-RPC id must be string/int/null, got {type(value).__name__}')


def build_request(
    method: str,
    params: Any = None,
    *,
    request_id: str | int | None = None,
) -> dict:
    """构造一个 JSON-RPC 2.0 请求对象。"""
    if not isinstance(method, str) or not method:
        raise BridgeProtocolError('method must be a non-empty string')
    rid = str(uuid.uuid4()) if request_id is None else request_id
    payload: dict[str, Any] = {'jsonrpc': '2.0', 'method': method, 'id': rid}
    if params is not None:
        payload['params'] = params
    return payload


def build_notification(method: str, params: Any = None) -> dict:
    """构造一个 JSON-RPC 2.0 通知（无 id 字段）。"""
    if not isinstance(method, str) or not method:
        raise BridgeProtocolError('method must be a non-empty string')
    payload: dict[str, Any] = {'jsonrpc': '2.0', 'method': method}
    if params is not None:
        payload['params'] = params
    return payload


def build_result_response(request_id: Any, result: Any) -> dict:
    rid = _ensure_str_id(request_id)
    return {'jsonrpc': '2.0', 'id': rid, 'result': result}


def build_error_response(
    request_id: Any,
    *,
    code: int,
    message: str,
    data: Any = None,
) -> dict:
    rid = _ensure_str_id(request_id)
    error: dict[str, Any] = {'code': int(code), 'message': str(message)}
    if data is not None:
        error['data'] = data
    return {'jsonrpc': '2.0', 'id': rid, 'error': error}


def parse_frame_line(
    line: bytes,
    *,
    max_bytes: int = DEFAULT_MAX_FRAME_BYTES,
) -> dict:
    """解析一帧 ``\\n`` 结尾的 JSON-RPC 消息。

    抛出：
    - ``BridgeOversizedFrame``: 单帧超过 max_bytes
    - ``BridgeProtocolError``: JSON 解析失败或字段缺失

    接收方应丢弃这一帧对应的连接；不重试（协议层错不可重试）。
    """
    if len(line) > max_bytes:
        raise BridgeOversizedFrame(
            f'frame size {len(line)} exceeds max {max_bytes}'
        )
    # 容忍末尾带 ``\\n`` 或 ``\\r\\n``
    if line.endswith(b'\r\n'):
        line = line[:-2]
    elif line.endswith(b'\n'):
        line = line[:-1]
    if not line:
        raise BridgeProtocolError('empty frame')
    try:
        text = line.decode('utf-8', errors='strict')
    except UnicodeDecodeError as exc:
        raise BridgeProtocolError(f'frame not utf-8: {exc}') from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BridgeProtocolError(f'frame not valid json: {exc}') from exc
    if not isinstance(payload, dict):
        raise BridgeProtocolError('frame must be a JSON object')
    if payload.get('jsonrpc') != '2.0':
        raise BridgeProtocolError('frame missing jsonrpc: "2.0"')
    return payload


def encode_frame(payload: dict) -> bytes:
    """把 JSON-RPC 对象编码为 ``\\n`` 结尾的一行 UTF-8 字节。"""
    text = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    return text.encode('utf-8') + b'\n'


__all__ = [
    'DEFAULT_MAX_FRAME_BYTES',
    'ERR_AUTH_FAILED',
    'ERR_EPOCH_MISMATCH',
    'ERR_FRAME_TOO_LARGE',
    'ERR_INTERNAL',
    'ERR_INVALID_PARAMS',
    'ERR_INVALID_REQUEST',
    'ERR_LOCK_BUSY',
    'ERR_METHOD_NOT_FOUND',
    'ERR_PARSE',
    'PROTOCOL_VERSION',
    'build_error_response',
    'build_notification',
    'build_request',
    'build_result_response',
    'encode_frame',
    'parse_frame_line',
]

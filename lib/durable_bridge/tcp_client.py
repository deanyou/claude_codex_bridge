"""durable-bridge TCP 客户端（thin client）。

职责：
- 连接到 127.0.0.1:port
- 每次请求自动注入 token + bridge_epoch
- 处理 epoch 不匹配（视为可重试错误）
- 处理 token 不匹配（视为不可重试错误）
- 关闭连接即丢弃 handle（不再发送）

不负责：
- 端口发现（read_endpoint 单独调用）
- 重连退避（由调用方调用 reconnect 模块）
"""

from __future__ import annotations

import socket
from typing import Any

from .endpoint import BridgeEndpoint
from .exceptions import (
    BridgeAuthError,
    BridgeEpochMismatch,
    BridgeOversizedFrame,
    BridgeProtocolError,
)
from .protocol import (
    DEFAULT_MAX_FRAME_BYTES,
    ERR_AUTH_FAILED,
    ERR_EPOCH_MISMATCH,
    build_request,
    encode_frame,
    parse_frame_line,
)


class DurableBridgeClient:
    """同步 JSON-RPC over TCP 客户端。

    线程安全：单实例不应被多线程并发 send（与 socket 行为一致）。
    多线程场景下每线程各自实例化。
    """

    def __init__(
        self,
        endpoint: BridgeEndpoint,
        *,
        max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
        connect_timeout_s: float = 5.0,
    ) -> None:
        self._endpoint = endpoint
        self._max_frame_bytes = max_frame_bytes
        self._connect_timeout_s = connect_timeout_s
        self._sock: socket.socket | None = None
        self._recv_buffer = bytearray()
        # 服务端发来的 push 通知（无 id），调用方用 pop_notification 读取。
        self._notifications: list[dict] = []

    @property
    def endpoint(self) -> BridgeEndpoint:
        return self._endpoint

    def _ensure_connected(self) -> None:
        if self._sock is not None:
            return
        sock = socket.create_connection(
            (self._endpoint.host, self._endpoint.port),
            timeout=self._connect_timeout_s,
        )
        sock.settimeout(None)
        self._sock = sock

    def connect(self) -> None:
        self._ensure_connected()

    def close(self) -> None:
        if self._sock is None:
            return
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self._sock.close()
        finally:
            self._sock = None
            self._recv_buffer.clear()

    def __enter__(self) -> 'DurableBridgeClient':
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _send_frame(self, payload: dict) -> None:
        self._ensure_connected()
        assert self._sock is not None
        # auth 字段：所有请求都强制带 token + bridge_epoch
        if 'params' in payload and isinstance(payload['params'], dict):
            payload['params'].setdefault('token', self._endpoint.token)
            payload['params'].setdefault('bridge_epoch', self._endpoint.bridge_epoch)
        elif 'params' in payload:
            # 列表/非 dict params：包一层 auth 字段
            payload = {
                'jsonrpc': payload['jsonrpc'],
                'id': payload['id'],
                'method': payload['method'],
                'params': {
                    '_args': payload['params'],
                    'token': self._endpoint.token,
                    'bridge_epoch': self._endpoint.bridge_epoch,
                },
            }
        else:
            payload = {
                'jsonrpc': payload['jsonrpc'],
                'id': payload['id'],
                'method': payload['method'],
                'params': {
                    'token': self._endpoint.token,
                    'bridge_epoch': self._endpoint.bridge_epoch,
                },
            }
        data = encode_frame(payload)
        if len(data) > self._max_frame_bytes:
            raise BridgeOversizedFrame(
                f'outbound frame size {len(data)} exceeds max {self._max_frame_bytes}'
            )
        self._sock.sendall(data)

    def _recv_frame(self) -> dict:
        assert self._sock is not None
        while True:
            newline = self._recv_buffer.find(b'\n')
            if newline != -1:
                line = bytes(self._recv_buffer[:newline])
                del self._recv_buffer[: newline + 1]
                return self._parse_or_raise(line)
            chunk = self._sock.recv(64 * 1024)
            if not chunk:
                raise BridgeProtocolError('connection closed before frame complete')
            self._recv_buffer.extend(chunk)
            if len(self._recv_buffer) > self._max_frame_bytes:
                raise BridgeOversizedFrame(
                    f'inbound buffer exceeded {self._max_frame_bytes} before newline'
                )

    def _parse_or_raise(self, line: bytes) -> dict:
        try:
            return parse_frame_line(line, max_bytes=self._max_frame_bytes)
        except (BridgeProtocolError, BridgeOversizedFrame):
            raise

    def _translate_error(self, payload: dict) -> None:
        """服务端返回的 error 字段翻译为对应异常。"""
        err = payload.get('error')
        if not isinstance(err, dict):
            raise BridgeProtocolError(f'malformed error response: {err!r}')
        code = int(err.get('code', 0))
        message = str(err.get('message', ''))
        data = err.get('data')
        if code == ERR_EPOCH_MISMATCH:
            raise BridgeEpochMismatch(f'{message} (data={data!r})')
        if code == ERR_AUTH_FAILED:
            raise BridgeAuthError(f'{message} (data={data!r})')
        # 其它错误：让调用方通过 result=None 自行处理；这里不抛。

    def call_raw(
        self,
        method: str,
        params: Any = None,
        *,
        request_id: str | int | None = None,
    ) -> dict:
        """发送请求并返回原始响应帧（不抛 BridgeAuthError/BridgeEpochMismatch）。

        测试和需要细粒度处理错误的代码用这个；正常业务代码用 ``call``。
        """
        req = build_request(method, params, request_id=request_id)
        self._send_frame(req)
        while True:
            payload = self._recv_frame()
            if 'id' not in payload:
                self._notifications.append(payload)
                continue
            if payload.get('id') != req['id']:
                raise BridgeProtocolError(
                    f'request id mismatch: sent={req["id"]!r} got={payload.get("id")!r}'
                )
            return payload

    def call(
        self,
        method: str,
        params: Any = None,
        *,
        request_id: str | int | None = None,
    ) -> dict:
        """发送请求并同步等待响应。"""
        req = build_request(method, params, request_id=request_id)
        self._send_frame(req)
        while True:
            payload = self._recv_frame()
            # 通知（无 id）放入队列，继续等响应
            if 'id' not in payload:
                self._notifications.append(payload)
                continue
            if payload.get('id') != req['id']:
                # id 不匹配的服务端响应视为协议错
                raise BridgeProtocolError(
                    f'request id mismatch: sent={req["id"]!r} got={payload.get("id")!r}'
                )
            if 'error' in payload:
                self._translate_error(payload)
            return payload

    def pop_notifications(self) -> list[dict]:
        out, self._notifications = self._notifications, []
        return out


__all__ = ['DurableBridgeClient']

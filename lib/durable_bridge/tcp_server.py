"""durable-bridge TCP 服务端。

服务循环：
- accept 客户端连接
- 每条连接一个线程，按 ``\\n`` 切帧
- 每帧做：大小限制 → JSON 解析 → auth 校验 → 方法分派 → 写回响应
- 错误分级：
  - 协议层错（帧格式/JSON）：返回 -32600 / -32700 错误，**不关闭连接**
    （客户端可能下一帧恢复），但单帧错误本身不可重试
  - 鉴权错：返回 -32001 / -32002 错误；token 错关闭连接以防暴力枚举
  - 资源/系统错：返回 -32603，关闭连接
  - 超大帧：直接关闭连接（防 DoS）

线程模型：
- 单一 accept 线程循环
- 每条连接一个 daemon 线程
- 所有 backend 调用都进入 backend 自身的锁
- 优雅关闭通过 ``shutdown_event`` 触发：accept 线程退出，等待现有连接
  处理完当前帧后关闭
"""

from __future__ import annotations

import errno
import logging
import socket
import threading
from typing import Any, Callable

from .backend import (
    BackendError,
    BackendInvalidState,
    BackendNotFound,
    DurableBackend,
)
from .endpoint import BridgeEndpoint
from .exceptions import (
    BridgeOversizedFrame,
    BridgeProtocolError,
)
from .protocol import (
    DEFAULT_MAX_FRAME_BYTES,
    ERR_AUTH_FAILED,
    ERR_EPOCH_MISMATCH,
    ERR_INTERNAL,
    ERR_INVALID_PARAMS,
    ERR_INVALID_REQUEST,
    ERR_METHOD_NOT_FOUND,
    ERR_PARSE,
    build_error_response,
    build_result_response,
    encode_frame,
    parse_frame_line,
)

_log = logging.getLogger(__name__)


# 允许的方法名 → 处理函数；处理函数接收 (handle, params) 并返回 result。
HandlerFn = Callable[[dict, dict], dict]


class TcpServer:
    """单实例 JSON-RPC over TCP 服务端。"""

    def __init__(
        self,
        endpoint: BridgeEndpoint,
        backend: DurableBackend,
        *,
        host: str = '127.0.0.1',
        max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
    ) -> None:
        if host != '127.0.0.1':
            raise ValueError(f'transport host must be 127.0.0.1, got: {host!r}')
        self._endpoint = endpoint
        self._backend = backend
        self._host = host
        self._max_frame_bytes = max_frame_bytes
        self._listener: socket.socket | None = None
        self._bound_port: int | None = None
        self._shutdown = threading.Event()
        self._accept_thread: threading.Thread | None = None
        self._connections: set[socket.socket] = set()
        self._conn_lock = threading.Lock()
        # handle_id -> handle record（每条 open() 调用一个）
        self._handles: dict[str, dict] = {}
        self._handles_lock = threading.Lock()
        # 方法注册表
        self._handlers: dict[str, HandlerFn] = {}
        self._register_default_methods()

    # ---- lifecycle ----

    def bind(self) -> int:
        """绑定 127.0.0.1:0，返回实际端口。

        不开始 accept；调用方应先拿到端口写 endpoint.json，再 start()。
        """
        if self._listener is not None:
            raise RuntimeError('server already bound')
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((self._host, 0))
        except OSError as exc:
            sock.close()
            if exc.errno == errno.EADDRINUSE:
                from .exceptions import BridgeBusyError
                raise BridgeBusyError(f'bind {self._host}:0 failed: {exc}') from exc
            raise
        sock.listen(64)
        sock.settimeout(0.5)  # 让 accept 循环能响应 shutdown_event
        self._listener = sock
        self._bound_port = int(sock.getsockname()[1])
        return self._bound_port

    @property
    def bound_port(self) -> int:
        if self._bound_port is None:
            raise RuntimeError('server not bound yet')
        return self._bound_port

    def start(self) -> None:
        if self._listener is None:
            raise RuntimeError('bind() must be called before start()')
        if self._accept_thread is not None:
            raise RuntimeError('server already started')
        self._accept_thread = threading.Thread(
            target=self._accept_loop,
            name=f'durable-bridge-accept[{self._bound_port}]',
            daemon=True,
        )
        self._accept_thread.start()

    def shutdown(self, *, timeout_s: float = 5.0) -> None:
        self._shutdown.set()
        if self._listener is not None:
            try:
                self._listener.close()
            except OSError:
                pass
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=timeout_s)
        # 关闭所有现存连接
        with self._conn_lock:
            connections = list(self._connections)
            self._connections.clear()
        for conn in connections:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                conn.close()
            except OSError:
                pass
        self._listener = None
        self._accept_thread = None

    # ---- method registration ----

    def _register_default_methods(self) -> None:
        self._handlers['open'] = self._handle_open
        self._handlers['close'] = self._handle_close
        self._handlers['submit'] = self._handle_submit
        self._handlers['status'] = self._handle_status
        self._handlers['register_conversation'] = self._handle_register_conversation
        self._handlers['list_conversations'] = self._handle_list_conversations

    def _handle_open(self, _handle: dict, params: dict) -> dict:
        storage_path = params.get('storage_path')
        if not isinstance(storage_path, str) or not storage_path:
            raise ValueError('storage_path must be a non-empty string')
        conversation_id = params.get('conversation_id')
        if conversation_id is not None and not isinstance(conversation_id, str):
            raise ValueError('conversation_id must be a string when provided')
        return self._backend.open(storage_path, conversation_id=conversation_id)

    def _handle_close(self, _handle: dict, params: dict) -> dict:
        handle = params.get('handle')
        if not isinstance(handle, dict):
            raise ValueError('handle must be an object')
        handle_id = handle.get('handle_id')
        if not isinstance(handle_id, str):
            raise ValueError('handle.handle_id must be a string')
        with self._handles_lock:
            self._handles.pop(handle_id, None)
        self._backend.close(handle)
        return {'closed': True}

    def _handle_submit(self, _handle: dict, params: dict) -> dict:
        handle = params.get('handle')
        if not isinstance(handle, dict):
            raise ValueError('handle must be an object')
        conversation_id = params.get('conversation_id')
        request_id = params.get('requestId')
        input_text = params.get('input')
        if not isinstance(conversation_id, str) or not conversation_id:
            raise ValueError('conversation_id must be a non-empty string')
        if not isinstance(request_id, str) or not request_id:
            raise ValueError('requestId must be a non-empty string')
        if not isinstance(input_text, str):
            raise ValueError('input must be a string')
        sub = self._backend.submit(handle, conversation_id, request_id, input_text)
        return _submission_to_result(sub)

    def _handle_status(self, _handle: dict, params: dict) -> dict:
        handle = params.get('handle')
        if not isinstance(handle, dict):
            raise ValueError('handle must be an object')
        submission_id = params.get('submission_id')
        if not isinstance(submission_id, str) or not submission_id:
            raise ValueError('submission_id must be a non-empty string')
        sub = self._backend.status(handle, submission_id)
        return _submission_to_result(sub)

    def _handle_register_conversation(self, _handle: dict, params: dict) -> dict:
        conversation_id = params.get('conversation_id')
        if not isinstance(conversation_id, str) or not conversation_id:
            raise ValueError('conversation_id must be a non-empty string')
        self._backend.register_conversation(conversation_id)
        return {'registered': True}

    def _handle_list_conversations(self, _handle: dict, _params: dict) -> dict:
        return {'conversations': list(self._backend.list_conversations())}

    # ---- internal ----

    def _accept_loop(self) -> None:
        assert self._listener is not None
        while not self._shutdown.is_set():
            try:
                conn, _addr = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                # 监听 socket 在 shutdown() 中被关闭
                if self._shutdown.is_set():
                    return
                raise
            conn.settimeout(None)
            with self._conn_lock:
                self._connections.add(conn)
            t = threading.Thread(
                target=self._serve_connection,
                args=(conn,),
                name=f'durable-bridge-conn[{self._bound_port}]',
                daemon=True,
            )
            t.start()

    def _serve_connection(self, conn: socket.socket) -> None:
        try:
            buf = bytearray()
            while not self._shutdown.is_set():
                # 读至少 1 字节；为简化用固定 chunk 接收
                try:
                    chunk = conn.recv(64 * 1024)
                except OSError:
                    return
                if not chunk:
                    return
                buf.extend(chunk)
                if len(buf) > self._max_frame_bytes:
                    # 单连接缓冲超过上限 → 关闭连接防 DoS
                    return
                # 处理所有完整帧
                while True:
                    newline = buf.find(b'\n')
                    if newline == -1:
                        break
                    line = bytes(buf[:newline])
                    del buf[: newline + 1]
                    try:
                        response = self._dispatch_frame(line)
                    except BridgeOversizedFrame:
                        return
                    except Exception as exc:  # noqa: BLE001
                        _log.exception('dispatch failed: %r', exc)
                        return
                    if response is not None:
                        try:
                            conn.sendall(encode_frame(response))
                        except OSError:
                            return
        finally:
            with self._conn_lock:
                self._connections.discard(conn)
            try:
                conn.close()
            except OSError:
                pass

    def _dispatch_frame(self, line: bytes) -> dict | None:
        try:
            payload = parse_frame_line(line, max_bytes=self._max_frame_bytes)
        except BridgeOversizedFrame:
            raise
        except BridgeProtocolError as exc:
            # 协议层错：返回错误响应
            return build_error_response(
                request_id=None,
                code=ERR_PARSE,
                message=f'parse error: {exc}',
            )

        if not isinstance(payload, dict):
            return build_error_response(
                request_id=None,
                code=ERR_INVALID_REQUEST,
                message='payload must be a JSON object',
            )
        if payload.get('jsonrpc') != '2.0':
            return build_error_response(
                request_id=payload.get('id'),
                code=ERR_INVALID_REQUEST,
                message='missing jsonrpc: "2.0"',
            )
        method = payload.get('method')
        if not isinstance(method, str) or not method:
            return build_error_response(
                request_id=payload.get('id'),
                code=ERR_INVALID_REQUEST,
                message='method must be a non-empty string',
            )
        request_id = payload.get('id')
        is_notification = 'id' not in payload
        params = payload.get('params')
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return build_error_response(
                request_id=request_id,
                code=ERR_INVALID_REQUEST,
                message='params must be an object for durable-bridge methods',
            )

        # 鉴权（open 不要求 token，因为它本身是建立信任的第一步）
        if method != 'open':
            token = params.get('token')
            epoch = params.get('bridge_epoch')
            if not isinstance(token, str) or token != self._endpoint.token:
                # token 错：返回错误并由调用方决定是否关闭连接
                # 这里不直接关闭，让客户端能在多帧间发不同请求测试
                return build_error_response(
                    request_id=request_id,
                    code=ERR_AUTH_FAILED,
                    message='token mismatch',
                )
            if not isinstance(epoch, str) or epoch != self._endpoint.bridge_epoch:
                return build_error_response(
                    request_id=request_id,
                    code=ERR_EPOCH_MISMATCH,
                    message='bridge_epoch mismatch',
                )

        handler = self._handlers.get(method)
        if handler is None:
            if is_notification:
                return None
            return build_error_response(
                request_id=request_id,
                code=ERR_METHOD_NOT_FOUND,
                message=f'unknown method: {method}',
            )

        # 取 handle 字段
        handle = params.get('handle') or {}
        if not isinstance(handle, dict):
            return build_error_response(
                request_id=request_id,
                code=ERR_INVALID_PARAMS,
                message='handle must be an object',
            )

        try:
            result = handler(handle, params)
        except BackendNotFound as exc:
            return build_error_response(
                request_id=request_id,
                code=ERR_INVALID_PARAMS,
                message=str(exc),
            )
        except BackendInvalidState as exc:
            return build_error_response(
                request_id=request_id,
                code=ERR_INVALID_PARAMS,
                message=str(exc),
            )
        except BackendError as exc:
            return build_error_response(
                request_id=request_id,
                code=ERR_INVALID_PARAMS,
                message=str(exc),
            )
        except ValueError as exc:
            return build_error_response(
                request_id=request_id,
                code=ERR_INVALID_PARAMS,
                message=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            _log.exception('handler %s failed', method)
            return build_error_response(
                request_id=request_id,
                code=ERR_INTERNAL,
                message=f'{type(exc).__name__}: {exc}',
            )

        if is_notification:
            return None
        return build_result_response(request_id, result)


def _submission_to_result(sub) -> dict:
    return {
        'submission_id': sub.submission_id,
        'conversation_id': sub.conversation_id,
        'request_id': sub.request_id,
        'status': sub.status,
        'text': sub.text,
        'finish_reason': sub.finish_reason,
        'created_at': sub.created_at,
        'settled_at': sub.settled_at,
    }


__all__ = ['TcpServer']

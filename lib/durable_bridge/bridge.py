"""BridgeServer 编排：lock → bind → publish → serve → shutdown。

生命周期：
1. acquire_storage_lock(storage_path)：拿不到抛 BridgeStorageLockBusy
2. bind() 取得 127.0.0.1 随机端口
3. publish_endpoint() 原子写入 endpoint.json（含 token + bridge_epoch）
4. start() 开始 accept 客户端连接
5. 等待 shutdown_event（外部 signal 或显式 shutdown()）
6. 关闭顺序：
   a. shutdown_event.set() 停止 accept 新连接
   b. 服务线程退出后 revoke_endpoint()
   c. release_storage_lock()
   d. 关闭监听 socket
"""

from __future__ import annotations

import logging
import signal
import threading
from pathlib import Path

from .backend import DurableBackend
from .endpoint import (
    DEFAULT_ENDPOINT_FILENAME,
    BridgeEndpoint,
    make_endpoint,
    publish_endpoint,
    revoke_endpoint,
)
from .storage_lock import (
    StorageLockHandle,
    acquire_storage_lock,
    release_storage_lock,
)
from .tcp_server import TcpServer

_log = logging.getLogger(__name__)


class BridgeServer:
    """常驻桥进程内的服务端对象。

    用途：
    - 测试中直接实例化并调用 start()/shutdown()
    - 生产中由 daemon 主进程在子进程内启动，并通过 SIGTERM 触发 shutdown

    不负责：
    - 进程模型（fork / subprocess）：由调用方决定
    - 桥的 supervision / 重连：见后续步骤
    """

    def __init__(
        self,
        storage_path: Path,
        backend: DurableBackend,
        *,
        endpoint_path: Path | None = None,
    ) -> None:
        self._storage_path = Path(storage_path)
        self._backend = backend
        self._endpoint_path = (
            Path(endpoint_path)
            if endpoint_path is not None
            else self._storage_path.parent / DEFAULT_ENDPOINT_FILENAME
        )
        self._lock_handle: StorageLockHandle | None = None
        self._endpoint: BridgeEndpoint | None = None
        self._server: TcpServer | None = None
        self._shutdown = threading.Event()
        self._started = False
        # 用于 SIGTERM → 优雅关闭：保留旧 handler 以便恢复
        self._prev_sigterm: signal._HANDLER | None = None
        self._sigterm_installed = False

    @property
    def endpoint(self) -> BridgeEndpoint:
        if self._endpoint is None:
            raise RuntimeError('bridge not started')
        return self._endpoint

    @property
    def endpoint_path(self) -> Path:
        return self._endpoint_path

    @property
    def started(self) -> bool:
        return self._started

    def install_signal_handlers(self) -> None:
        """安装 SIGTERM handler（POSIX）触发优雅关闭。

        其它信号（SIGINT 等）不在本模块范围；调用方可单独处理。
        """
        if self._sigterm_installed:
            return
        try:
            self._prev_sigterm = signal.signal(signal.SIGTERM, self._on_sigterm)
            self._sigterm_installed = True
        except (ValueError, OSError):
            # 非主线程或不支持信号时跳过
            pass

    def _on_sigterm(self, signum, frame) -> None:  # noqa: ARG002
        _log.info('bridge received SIGTERM, initiating shutdown')
        self._shutdown.set()

    def start(self) -> BridgeEndpoint:
        if self._started:
            raise RuntimeError('bridge already started')

        # 1. 拿 storage 锁
        self._lock_handle = acquire_storage_lock(self._storage_path)
        # 2. 构造 endpoint（含 token + bridge_epoch）
        self._endpoint = make_endpoint()
        # 3. 启动 TcpServer 并 bind 随机端口
        self._server = TcpServer(self._endpoint, self._backend)
        port = self._server.bind()
        # 4. 把端口写回 endpoint 并原子发布
        self._endpoint = BridgeEndpoint(
            host=self._endpoint.host,
            port=port,
            pid=self._endpoint.pid,
            bridge_epoch=self._endpoint.bridge_epoch,
            protocol_version=self._endpoint.protocol_version,
            token=self._endpoint.token,
        )
        self._server._endpoint = self._endpoint  # 让 server 用最终版 endpoint
        publish_endpoint(self._endpoint_path, self._endpoint)
        # 5. 开始 accept
        self._server.start()
        self._started = True
        return self._endpoint

    def wait_for_shutdown(self, timeout_s: float | None = None) -> bool:
        """阻塞直到收到 shutdown 信号或超时。返回是否被 shutdown 触发。"""
        return self._shutdown.wait(timeout=timeout_s)

    def shutdown(self, *, timeout_s: float = 5.0) -> None:
        """优雅关闭：停 accept → 撤销 endpoint → 释放锁 → 关闭 socket。"""
        if not self._started:
            return
        self._shutdown.set()
        if self._server is not None:
            self._server.shutdown(timeout_s=timeout_s)
        # 撤销 endpoint：只有 epoch 匹配才删除
        if self._endpoint is not None:
            try:
                revoke_endpoint(self._endpoint_path)
            except Exception:  # noqa: BLE001
                _log.exception('revoke_endpoint failed (non-fatal)')
        if self._lock_handle is not None:
            try:
                release_storage_lock(self._lock_handle)
            except Exception:  # noqa: BLE001
                _log.exception('release_storage_lock failed (non-fatal)')
            self._lock_handle = None
        if self._sigterm_installed:
            try:
                signal.signal(signal.SIGTERM, self._prev_sigterm)  # type: ignore[arg-type]
            except (ValueError, OSError):
                pass
            self._sigterm_installed = False
        self._started = False

    def __enter__(self) -> 'BridgeServer':
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.shutdown()


__all__ = ['BridgeServer']

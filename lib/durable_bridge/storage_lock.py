"""durable storage 路径的 OS 独占锁。

职责：
- 把任意 storage 路径（文件或目录）规范化为其旁路锁文件路径
- 用 fcntl.flock（POSIX）或 msvcrt.locking（Windows）取得跨进程互斥
- 同进程内对同一路径获取两次时拒绝（re-entrancy 禁止）
- 平台既无 fcntl 也无 msvcrt 时 fail-closed

不在本模块范围：
- 验证锁持有进程是否仍然存活（便携地判断进程存亡需要平台特定信号；
  这交给 supervisor 心跳 + SIGTERM 流程，本模块只负责"锁住就是锁住"）
"""

from __future__ import annotations

import errno
import os
from pathlib import Path
from threading import Lock
from typing import ClassVar

from .exceptions import BridgeStorageLockBusy


def _sidecar_lock_path(storage_path: Path) -> Path:
    """storage 路径 → 旁路锁文件路径。

    规则：保留 storage 路径的父目录与后缀，在旁边放一个 `.lock` 旁路文件。
    同目录下不同 storage 路径互不冲突，同一 storage 路径每次都得到同一锁。
    """
    target = Path(storage_path).expanduser().absolute()
    parent = target.parent
    name = target.name or 'storage'
    return parent / f'.{name}.durable-bridge.lock'


class _SamePathLockRegistry:
    """进程内同路径获取去重。"""

    def __init__(self) -> None:
        self._held: dict[Path, int] = {}
        self._mutex: Lock = Lock()

    def acquire(self, path: Path) -> bool:
        with self._mutex:
            count = self._held.get(path, 0)
            if count > 0:
                return False
            self._held[path] = 1
            return True

    def release(self, path: Path) -> None:
        with self._mutex:
            count = self._held.get(path, 0)
            if count <= 1:
                self._held.pop(path, None)
            else:
                self._held[path] = count - 1


_PROCESS_REGISTRY = _SamePathLockRegistry()


class StorageLockHandle:
    """storage 锁的拥有权句柄。

    释放方式：调用 ``release()`` 或直接 ``with`` 块退出。重复释放安全。
    """

    __slots__ = ('_lock_path', '_fd', '_released', '_owns_process')

    def __init__(self, lock_path: Path, fd: int) -> None:
        self._lock_path = Path(lock_path)
        self._fd: int | None = fd
        self._released: bool = False
        self._owns_process: bool = True

    @property
    def lock_path(self) -> Path:
        return self._lock_path

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        if self._owns_process:
            _PROCESS_REGISTRY.release(self._lock_path)
            self._owns_process = False

    def __enter__(self) -> 'StorageLockHandle':
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

    def __del__(self) -> None:
        # 进程退出时 OS 会自动释放锁，但显式关闭 fd 仍更稳妥。
        # __del__ 期间不应抛异常，因此任何 OSError 都被吞掉。
        try:
            self.release()
        except Exception:
            pass


def _try_acquire_posix(lock_path: Path) -> int | None:
    """POSIX: 尝试 fcntl.flock 非阻塞独占。成功返回 fd，失败返回 None。"""
    import fcntl  # type: ignore

    fd = os.open(
        str(lock_path),
        os.O_RDWR | os.O_CREAT,
        0o600,
    )
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(fd)
        if exc.errno in {errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES}:
            return None
        raise
    return fd


def _try_acquire_windows(lock_path: Path) -> int | None:
    """Windows: 尝试 msvcrt.locking 非阻塞字节锁。成功返回 fd，失败返回 None。"""
    import msvcrt  # type: ignore

    # msvcrt.locking 要求锁字节落在文件范围内；空文件需要先写 1 字节。
    fd = os.open(
        str(lock_path),
        os.O_RDWR | os.O_CREAT,
        0o600,
    )
    try:
        size = os.fstat(fd).st_size
        if size < 1:
            os.write(fd, b'\0')
            os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    except OSError as exc:
        os.close(fd)
        if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
            return None
        raise
    except BaseException:
        os.close(fd)
        raise
    return fd


# 平台支持检测：导入失败的平台不应触发 try/except ImportError 重复触发。
_PLATFORM: ClassVar[str | None]
try:
    import fcntl as _fcntl_probe  # type: ignore  # noqa: F401
    _PLATFORM = 'posix'
except ImportError:
    try:
        import msvcrt as _msvcrt_probe  # type: ignore  # noqa: F401
        _PLATFORM = 'windows'
    except ImportError:
        _PLATFORM = None


def acquire_storage_lock(
    storage_path: Path,
    *,
    lock_path: Path | None = None,
) -> StorageLockHandle:
    """非阻塞获取 storage 独占锁。

    成功返回 ``StorageLockHandle``；被他人持有抛 ``BridgeStorageLockBusy``。
    同一进程内对同一路径二次获取也抛 ``BridgeStorageLockBusy``。
    """
    target = Path(storage_path).expanduser().absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    sidecar = Path(lock_path).expanduser().absolute() if lock_path is not None else _sidecar_lock_path(target)

    if not _PROCESS_REGISTRY.acquire(sidecar):
        raise BridgeStorageLockBusy(f'storage lock already held in this process: {sidecar}')

    if _PLATFORM == 'posix':
        try:
            fd = _try_acquire_posix(sidecar)
        except BaseException:
            _PROCESS_REGISTRY.release(sidecar)
            raise
    elif _PLATFORM == 'windows':
        try:
            fd = _try_acquire_windows(sidecar)
        except BaseException:
            _PROCESS_REGISTRY.release(sidecar)
            raise
    else:
        # 既无 fcntl 也无 msvcrt：fail-closed，绝不"以为拿到锁"再继续。
        _PROCESS_REGISTRY.release(sidecar)
        raise BridgeStorageLockBusy(
            f'no cross-process locking available on this platform: {sidecar}'
        )

    if fd is None:
        _PROCESS_REGISTRY.release(sidecar)
        raise BridgeStorageLockBusy(f'storage lock busy: {sidecar}')

    return StorageLockHandle(sidecar, fd)


def release_storage_lock(handle: StorageLockHandle) -> None:
    """显式释放锁。重复释放安全。"""
    handle.release()


__all__ = [
    'StorageLockHandle',
    'acquire_storage_lock',
    'release_storage_lock',
]

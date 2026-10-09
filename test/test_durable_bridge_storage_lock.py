"""durable-bridge storage 锁测试。

覆盖：
- 同进程：同一路径二次获取抛 BridgeStorageLockBusy
- 同进程：释放后可重新获取
- 不同路径：互不干扰
- 跨进程：第二个进程拿不到锁
"""

from __future__ import annotations

import multiprocessing
from pathlib import Path

import pytest

from durable_bridge.exceptions import BridgeStorageLockBusy
from durable_bridge.storage_lock import (
    acquire_storage_lock,
    release_storage_lock,
)


def test_same_process_double_acquire_blocked(tmp_path: Path) -> None:
    """同进程内对同一 storage 路径二次获取应被拒。"""
    storage = tmp_path / "durable.sqlite"
    first = acquire_storage_lock(storage)
    try:
        with pytest.raises(BridgeStorageLockBusy):
            acquire_storage_lock(storage)
    finally:
        release_storage_lock(first)


def test_release_then_reacquire(tmp_path: Path) -> None:
    """释放后同一进程可重新拿到锁。"""
    storage = tmp_path / "durable.sqlite"
    first = acquire_storage_lock(storage)
    release_storage_lock(first)

    second = acquire_storage_lock(storage)
    try:
        assert second.lock_path.exists()
    finally:
        release_storage_lock(second)


def test_different_paths_independent(tmp_path: Path) -> None:
    """不同 storage 路径互不干扰。"""
    a = acquire_storage_lock(tmp_path / "a.sqlite")
    b = acquire_storage_lock(tmp_path / "b.sqlite")
    try:
        assert a.lock_path != b.lock_path
    finally:
        release_storage_lock(a)
        release_storage_lock(b)


def test_with_block_releases_on_exit(tmp_path: Path) -> None:
    """``with`` 块退出后锁应自动释放。"""
    storage = tmp_path / "durable.sqlite"
    with acquire_storage_lock(storage) as handle:
        assert handle is not None
        # 在 with 块内：再次获取应失败
        with pytest.raises(BridgeStorageLockBusy):
            acquire_storage_lock(storage)
    # 退出 with 块后：再次获取应成功
    second = acquire_storage_lock(storage)
    try:
        assert second is not None
    finally:
        release_storage_lock(second)


def _child_acquire(storage_str: str, q) -> None:  # noqa: ANN001
    """子进程：尝试获取锁，回报是否成功。"""
    try:
        h = acquire_storage_lock(Path(storage_str))
        try:
            q.put(("ok", str(h.lock_path)))
        finally:
            release_storage_lock(h)
    except BridgeStorageLockBusy as exc:
        q.put(("busy", str(exc)))
    except Exception as exc:  # noqa: BLE001
        q.put(("error", repr(exc)))


def test_cross_process_blocked(tmp_path: Path) -> None:
    """子进程拿不到主进程持有的锁。"""
    storage = tmp_path / "durable.sqlite"
    parent = acquire_storage_lock(storage)
    try:
        ctx = multiprocessing.get_context("spawn")
        q: ctx.Queue = ctx.Queue()
        proc = ctx.Process(
            target=_child_acquire,
            args=(str(storage), q),
        )
        proc.start()
        proc.join(timeout=10)
        assert proc.exitcode == 0, "child crashed"
        kind, _ = q.get(timeout=5)
        assert kind == "busy", f"expected busy, got {kind}"
    finally:
        release_storage_lock(parent)


def test_cross_process_succeeds_after_parent_release(tmp_path: Path) -> None:
    """父进程释放后，子进程可拿到。"""
    storage = tmp_path / "durable.sqlite"
    parent = acquire_storage_lock(storage)
    release_storage_lock(parent)

    ctx = multiprocessing.get_context("spawn")
    q: ctx.Queue = ctx.Queue()
    proc = ctx.Process(
        target=_child_acquire,
        args=(str(storage), q),
    )
    proc.start()
    proc.join(timeout=10)
    assert proc.exitcode == 0, "child crashed"
    kind, _ = q.get(timeout=5)
    assert kind == "ok", f"expected ok, got {kind}"

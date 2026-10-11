"""常驻桥的进程生命周期：起得来，也必须停得掉。

回归背景：Step 3' 在 bootstrap 里起桥并把句柄挂到 app.bridge_supervisor，
注释写「留给 shutdown 路径」，但**没有任何代码真的 stop 它**。
实测跑 daemon reload 测试后残留 347 个孤儿 bridge_process 进程。
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cc_bridge_daemon.app_runtime.lifecycle import (
    register_bridge_atexit,
    stop_bridge_supervisor,
)


def test_stop_bridge_supervisor_stops_running_bridge() -> None:
    """app 上挂着 supervisor 时，stop 必须被调用。"""
    app = MagicMock()
    sup = MagicMock()
    app.bridge_supervisor = sup
    stop_bridge_supervisor(app)
    sup.stop.assert_called_once()


def test_stop_bridge_supervisor_clears_reference() -> None:
    """stop 后必须把引用摘掉，否则重入会二次 stop。"""
    app = MagicMock()
    sup = MagicMock()
    app.bridge_supervisor = sup
    stop_bridge_supervisor(app)
    assert app.bridge_supervisor is None
    # 二次调用不应再碰 sup
    stop_bridge_supervisor(app)
    assert sup.stop.call_count == 1


def test_stop_bridge_supervisor_noop_when_absent() -> None:
    """没有 supervisor 时安全 no-op。"""
    app = MagicMock()
    app.bridge_supervisor = None
    stop_bridge_supervisor(app)  # 不应抛


def test_stop_bridge_supervisor_swallows_stop_failure() -> None:
    """stop 抛异常不得阻塞 shutdown（只记日志）。"""
    app = MagicMock()
    sup = MagicMock()
    sup.stop.side_effect = RuntimeError("bridge already gone")
    app.bridge_supervisor = sup
    stop_bridge_supervisor(app)  # 不应抛
    assert app.bridge_supervisor is None


def test_register_bridge_atexit_does_not_raise() -> None:
    """注册兜底清理不应抛，且不改变当前 supervisor 状态。"""
    app = MagicMock()
    app.bridge_supervisor = None
    register_bridge_atexit(app)  # 不应抛
    assert app.bridge_supervisor is None, "注册本身不应动 supervisor"


def test_real_bridge_process_is_reaped_after_stop(tmp_path: Path) -> None:
    """真实起一个桥，stop 后进程必须真的消失（不是只清 Python 引用）。"""
    from durable_bridge.bridge_supervisor import BridgeSupervisor

    storage = tmp_path / "storage.sqlite"
    endpoint = tmp_path / "endpoint.json"
    sup = BridgeSupervisor(startup_timeout_s=30.0, shutdown_timeout_s=10.0)
    ep = sup.start(storage_path=storage, endpoint_path=endpoint, backend="pi_durable")
    pid = sup.pid
    assert pid is not None and pid > 0

    import os
    import time
    # 桥确实活着
    assert os.path.exists(f"/proc/{pid}") or _pid_alive(pid)

    sup.stop()
    assert not sup.is_running, "stop() 后 supervisor 仍认为桥在跑"
    # 给 OS 一点时间回收
    for _ in range(50):
        if not _pid_alive(pid):
            break
        time.sleep(0.1)
    assert not _pid_alive(pid), f"桥进程 {pid} 在 stop() 后仍存活 —— 进程泄漏"


def _pid_alive(pid: int) -> bool:
    import os
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False

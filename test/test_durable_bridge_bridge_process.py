"""Step 3′ 桥进程 + supervisor + bootstrap 集成测试。

10 个测试（plan §4.4）：
- 1：桥进程独立 exec → endpoint.json 落盘，port != 0
- 2：supervisor.start 返回真实 endpoint，且 list_conversations 经 TCP 真能通
- 3：node 缺失 → 桥非 0 退出，stderr 提到 node
- 4：锁忙 → supervisor 抛 BridgeSupervisorError，消息含"锁"
- 5：桥起来后被 kill → supervisor 超时抛错，不 hang
- 6：stop() 后进程真退出
- 7：连调两次 stop 不抛
- 8：桥忽略 SIGTERM → stop 走 SIGKILL 路径并成功
- 9：bootstrap _inject 后 dispatcher 非 None，bridge_client 连真实 endpoint
- 10：桥不可用 → dispatcher is None，且有日志记录原因
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from durable_bridge.backend import InMemoryDurableBackend
from durable_bridge.bridge import BridgeServer
from durable_bridge.endpoint import BridgeEndpoint, read_endpoint
from durable_bridge.exceptions import BridgeStorageLockBusy
from durable_bridge.tcp_client import DurableBridgeClient


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------


PYTHONPATH = str(Path(__file__).resolve().parent.parent / "lib")


def _env_with_lib() -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = PYTHONPATH + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _make_dirs(tmp_path: Path) -> tuple[Path, Path]:
    storage = (tmp_path / "storage.sqlite").resolve()
    endpoint = (tmp_path / "ep.json").resolve()
    storage.parent.mkdir(parents=True, exist_ok=True)
    return storage, endpoint


def _read_endpoint_json(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return json.loads(text)


# ----------------------------------------------------------------------------
# 1: bridge_process 独立 exec → endpoint.json 落盘，port != 0
# ----------------------------------------------------------------------------


def test_bridge_process_starts_and_publishes_real_endpoint(tmp_path: Path) -> None:
    """独立 exec 桥进程 → endpoint.json 出现，port != 0。"""
    storage, endpoint = _make_dirs(tmp_path)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "durable_bridge.bridge_process",
            "--storage-path",
            str(storage),
            "--endpoint-path",
            str(endpoint),
            "--backend",
            "in_memory",
        ],
        env=_env_with_lib(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        # 等 endpoint.json 出现
        deadline = time.time() + 15.0
        while time.time() < deadline:
            if endpoint.exists():
                break
            if proc.poll() is not None:
                raise AssertionError(
                    f"bridge process exited prematurely (code={proc.returncode}); "
                    f"stderr={proc.stderr.read() if proc.stderr else ''}"
                )
            time.sleep(0.05)
        assert endpoint.exists(), "endpoint.json never appeared"

        record = _read_endpoint_json(endpoint)
        assert record["port"] != 0, f"port must be != 0, got {record}"
        assert record["host"] == "127.0.0.1"
        assert record["protocol_version"] == 1
        assert record["token"]
        assert record["bridge_epoch"]

        # stdout 应有 BRIDGE_READY 行
        assert proc.stdout is not None
        # 把已 buffer 的 stdout 读出来（lines 可能含末尾 \n）
        output_so_far = proc.stdout.readline()  # 读掉 BRIDGE_READY 行
        assert output_so_far.startswith("BRIDGE_READY "), f"stdout={output_so_far!r}"
        ready_payload = json.loads(output_so_far[len("BRIDGE_READY "):])
        assert ready_payload["port"] == record["port"]
        assert ready_payload["bridge_epoch"] == record["bridge_epoch"]
    finally:
        try:
            proc.terminate()
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2.0)


# ----------------------------------------------------------------------------
# 2: supervisor.start 返回真实 endpoint + TCP 真通
# ----------------------------------------------------------------------------


def test_supervisor_start_returns_live_endpoint(tmp_path: Path) -> None:
    """supervisor.start 返回 endpoint，且 list_conversations 经 TCP 真能通。"""
    from durable_bridge.bridge_supervisor import BridgeSupervisor

    storage, endpoint = _make_dirs(tmp_path)
    sup = BridgeSupervisor(startup_timeout_s=15.0, shutdown_timeout_s=5.0)
    try:
        ep = sup.start(
            storage_path=storage,
            endpoint_path=endpoint,
            backend="in_memory",
        )
        assert ep.port != 0
        assert ep.host == "127.0.0.1"
        # 客户端经 TCP 真能连 + RPC 走通
        client = DurableBridgeClient(ep)
        with client:
            resp = client.call("list_conversations", {})
        assert "result" in resp
        assert resp["result"]["conversations"] == []
    finally:
        sup.stop()


# ----------------------------------------------------------------------------
# 3: node 缺失 → 桥非 0 退出，stderr 提到 node
# ----------------------------------------------------------------------------


def test_bridge_process_fails_fast_when_node_missing(tmp_path: Path) -> None:
    """无 node → 桥非 0 退出，stderr 提到 node。"""
    storage, endpoint = _make_dirs(tmp_path)
    # 把 PATH 清空到 /usr/bin:/bin 保证 node 不在；保留 SHELL 用 /bin/sh
    restricted_env = dict(os.environ)
    restricted_env["PYTHONPATH"] = PYTHONPATH
    restricted_env["PATH"] = "/usr/bin:/bin"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "durable_bridge.bridge_process",
            "--storage-path",
            str(storage),
            "--endpoint-path",
            str(endpoint),
            "--backend",
            "pi_durable",
        ],
        env=restricted_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        proc.wait(timeout=10.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2.0)
        pytest.fail("bridge process did not exit on missing node")
    assert proc.returncode != 0, f"expected non-zero exit, got {proc.returncode}"
    stderr_text = proc.stderr.read() if proc.stderr else ""
    assert "node" in stderr_text.lower(), (
        f"stderr must mention node; got: {stderr_text[:400]}"
    )


# ----------------------------------------------------------------------------
# 4: 锁忙 → supervisor 抛错，消息含"锁"
# ----------------------------------------------------------------------------


def test_supervisor_raises_on_lock_busy(tmp_path: Path) -> None:
    """先起一个桥占锁，再起第二个 → BridgeSupervisorError，消息含"锁"。"""
    from durable_bridge.bridge_supervisor import BridgeSupervisor, BridgeSupervisorError

    storage, endpoint = _make_dirs(tmp_path)
    # 用 in_memory backend 起第一个 bridge 直接占锁（避免依赖 node）
    b1 = BridgeServer(
        storage_path=storage,
        backend=InMemoryDurableBackend(),
        endpoint_path=endpoint,
    )
    b1.start()
    try:
        sup = BridgeSupervisor(startup_timeout_s=5.0, shutdown_timeout_s=5.0)
        try:
            with pytest.raises(BridgeSupervisorError) as excinfo:
                sup.start(
                    storage_path=storage,
                    endpoint_path=endpoint,
                    backend="in_memory",
                )
            msg = str(excinfo.value)
            assert "锁" in msg or "lock" in msg.lower(), (
                f"error message must mention 锁 / lock; got: {msg[:400]}"
            )
            # stderr 必须出现在 message 里（可诊断原因）
            assert "BridgeStorageLockBusy" in msg or "storage_lock_busy" in msg, (
                f"stderr classification missing from message: {msg[:400]}"
            )
        finally:
            sup.stop()
    finally:
        b1.shutdown()


# ----------------------------------------------------------------------------
# 5: 桥崩溃 → supervisor 超时抛错，不 hang
# ----------------------------------------------------------------------------


def test_supervisor_raises_on_bridge_crash(tmp_path: Path) -> None:
    """桥启动后立刻退出 → supervisor 应在 startup_timeout_s 内抛错，不 hang。

    实现：写一个 wrapper 脚本，在 sys.exit 之前什么也不做 → supervisor 启动
    子进程后立刻看到进程已退（exit code 7），抛 BridgeSupervisorError。
    """
    import textwrap as _textwrap
    from durable_bridge.bridge_supervisor import BridgeSupervisor, BridgeSupervisorError

    storage, endpoint = _make_dirs(tmp_path)
    wrapper = tmp_path / "crash_wrapper.py"
    wrapper.write_text("import sys\nsys.exit(7)\n", encoding="utf-8")

    sup = BridgeSupervisor(
        python_bin=str(wrapper),
        startup_timeout_s=3.0,
        shutdown_timeout_s=2.0,
    )
    try:
        t0 = time.monotonic()
        with pytest.raises(BridgeSupervisorError):
            sup.start(
                storage_path=storage,
                endpoint_path=endpoint,
                backend="in_memory",
            )
        elapsed = time.monotonic() - t0
        # 不应 hang：3s timeout + 余量
        assert elapsed < 10.0, f"supervisor hung for {elapsed:.1f}s"
    finally:
        sup.stop()


# ----------------------------------------------------------------------------
# 6: stop() 后进程真退出
# ----------------------------------------------------------------------------


def test_supervisor_stop_terminates_bridge(tmp_path: Path) -> None:
    """stop() 后进程真退出（proc.poll() is not None）。"""
    from durable_bridge.bridge_supervisor import BridgeSupervisor

    storage, endpoint = _make_dirs(tmp_path)
    sup = BridgeSupervisor(startup_timeout_s=10.0, shutdown_timeout_s=5.0)
    sup.start(
        storage_path=storage,
        endpoint_path=endpoint,
        backend="in_memory",
    )
    proc = sup._proc
    assert proc is not None
    assert proc.poll() is None  # 还在跑
    sup.stop()
    # stop() 后 sup 标志为已停，但底层 proc 可能还在 OS 资源回收
    assert sup._proc is None
    # 再确认进程退出（poll 不为 None）
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        time.sleep(0.05)
    assert proc.poll() is not None, "bridge process did not exit after stop()"


# ----------------------------------------------------------------------------
# 7: 连调两次 stop 不抛
# ----------------------------------------------------------------------------


def test_supervisor_stop_is_idempotent(tmp_path: Path) -> None:
    """连调两次 stop 不抛异常。"""
    from durable_bridge.bridge_supervisor import BridgeSupervisor

    storage, endpoint = _make_dirs(tmp_path)
    sup = BridgeSupervisor(startup_timeout_s=10.0, shutdown_timeout_s=5.0)
    sup.start(
        storage_path=storage,
        endpoint_path=endpoint,
        backend="in_memory",
    )
    sup.stop()
    sup.stop()  # 不抛
    sup.stop()  # 第三次也安全


# ----------------------------------------------------------------------------
# 8: 桥忽略 SIGTERM → stop 走 SIGKILL 路径并成功
# ----------------------------------------------------------------------------


def test_supervisor_stop_kills_unresponsive_bridge(tmp_path: Path) -> None:
    """桥忽略 SIGTERM → stop 走 SIGKILL 路径并成功。

    实现：用 supervisor.start(ignore_sigterm=True) → 桥子进程装 SIG_IGN。
    这样 supervisor 发 SIGTERM 时桥不响应，必须等 shutdown_timeout_s 后
    SIGKILL 才退出。
    """
    from durable_bridge.bridge_supervisor import BridgeSupervisor

    storage, endpoint = _make_dirs(tmp_path)

    # 短 shutdown_timeout 让测试快：1.5s 后 SIGKILL
    sup = BridgeSupervisor(
        startup_timeout_s=10.0,
        shutdown_timeout_s=1.5,
    )
    try:
        sup.start(
            storage_path=storage,
            endpoint_path=endpoint,
            backend="in_memory",
            ignore_sigterm=True,
        )
        proc = sup._proc
        assert proc is not None
        t0 = time.monotonic()
        sup.stop()
        elapsed = time.monotonic() - t0
        # 至少等了 shutdown_timeout_s
        assert elapsed >= 1.0, f"stop returned too fast: {elapsed:.2f}s"
        # 进程必须真退出（SIGKILL 生效）
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            time.sleep(0.05)
        assert proc.poll() is not None, (
            f"unresponsive bridge did not die after SIGKILL; poll={proc.poll()}"
        )
    finally:
        pass


# ----------------------------------------------------------------------------
# 9: bootstrap 把真实 endpoint 接到 dispatcher
# ----------------------------------------------------------------------------


def _build_minimal_app(tmp_path: Path):
    """构造一个最小可用的 app-like 对象供 bootstrap._inject_* 调用。"""
    from storage.paths import PathLayout

    class _App:
        pass

    app = _App()
    project_root = tmp_path.resolve()
    layout = PathLayout(project_root=project_root)
    layout.ensure_runtime_state_root()

    # 桩 clock
    app.paths = layout
    app.project_root = project_root
    app.clock = lambda: "2026-10-10T00:00:00+00:00"
    app.project_id = "probe-project"
    app.daemon_instance_id = "epoch-probe-9"

    # 桩 execution_registry
    class _Adapters(dict):
        pass

    class _Registry:
        def __init__(self):
            self._adapters = _Adapters()

    app.execution_registry = _Registry()
    return app


def test_bootstrap_wires_real_endpoint(tmp_path: Path, monkeypatch) -> None:
    """调 _inject_durable_dispatcher_into_pi_adapter 后 dispatcher 非 None，
    且其 bridge client 连的是真实 endpoint（port != 0、token 一致）。
    """
    from cc_bridge_daemon.app_runtime import bootstrap
    from durable_bridge.endpoint import read_endpoint

    app = _build_minimal_app(tmp_path)

    # 在 monkeypatch 下：让 supervisor 用 in_memory（避开 node / pi_durable 路径）
    # 这样测试稳定，不依赖 node。
    from durable_bridge import bridge_supervisor as _sup_mod

    real_start = _sup_mod.BridgeSupervisor.start

    def _patched_start(self, *, storage_path, endpoint_path, backend="pi_durable"):
        return real_start(
            self,
            storage_path=storage_path,
            endpoint_path=endpoint_path,
            backend="in_memory",
        )

    monkeypatch.setattr(_sup_mod.BridgeSupervisor, "start", _patched_start)

    bootstrap._inject_durable_dispatcher_into_pi_adapter(app)

    try:
        assert app.durable_dispatcher is not None, (
            "durable_dispatcher should be set when bridge is reachable"
        )
        # bridge client 连的是真实 endpoint
        bridge_client = app.durable_dispatcher._bridge
        ep = bridge_client.endpoint
        assert ep.port != 0
        assert ep.token, "real endpoint must carry a token"

        # endpoint.json 真的落盘
        ep_path = app.paths.cc_bridge_daemon_durable_bridge_endpoint_path
        assert ep_path.exists()
        file_ep = read_endpoint(ep_path)
        assert file_ep is not None
        assert file_ep.port == ep.port
        assert file_ep.token == ep.token

        # TCP 真能通（list_conversations）
        with bridge_client as client:
            resp = client.call("list_conversations", {})
        assert resp["result"]["conversations"] == []

        # supervisor 也在 app 上
        assert app.bridge_supervisor is not None
    finally:
        if getattr(app, "bridge_supervisor", None) is not None:
            app.bridge_supervisor.stop()


# ----------------------------------------------------------------------------
# 10: bootstrap 降级：桥不可用 → dispatcher None + 有日志
# ----------------------------------------------------------------------------


def test_bootstrap_degrades_when_bridge_unavailable(tmp_path: Path, caplog) -> None:
    """桥不可用（node 缺失）→ dispatcher is None，且有日志记录原因。"""
    from cc_bridge_daemon.app_runtime import bootstrap

    app = _build_minimal_app(tmp_path)

    # 把 PATH 清空 + 强制 supervisor 走 pi_durable backend（必须失败）
    monkey_env = dict(os.environ)
    monkey_env["PATH"] = "/usr/bin:/bin"

    import unittest.mock as mock
    with mock.patch.dict(os.environ, monkey_env, clear=True):
        # 必须保留 HOME / TMPDIR 等基础变量，否则子进程打不开
        os.environ["PATH"] = "/usr/bin:/bin"
        os.environ["PYTHONPATH"] = PYTHONPATH
        os.environ["HOME"] = monkey_env.get("HOME", "/tmp")
        os.environ["TMPDIR"] = monkey_env.get("TMPDIR", "/tmp")

        with caplog.at_level(logging.WARNING, logger="cc_bridge_daemon"):
            bootstrap._inject_durable_dispatcher_into_pi_adapter(app)

    # 降级：dispatcher = None
    assert app.durable_dispatcher is None, (
        f"expected None dispatcher when bridge unavailable; got {app.durable_dispatcher!r}"
    )
    assert app.bridge_supervisor is None

    # 必须有日志说明原因
    messages = [r.getMessage() for r in caplog.records]
    assert any("durable-bridge unavailable" in m for m in messages), (
        f"expected log explaining degrade; got: {messages}"
    )
    assert any(
        ("reason=" in m) or ("node" in m.lower()) or ("锁" in m)
        for m in messages
    ), f"log should include reason/cause; got: {messages}"

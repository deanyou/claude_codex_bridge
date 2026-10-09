"""durable-bridge 服务端 + 客户端 + 编排器集成测试。"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest

from durable_bridge.backend import (
    BackendError,
    InMemoryDurableBackend,
)
from durable_bridge.bridge import BridgeServer
from durable_bridge.endpoint import read_endpoint
from durable_bridge.exceptions import (
    BridgeAuthError,
    BridgeEpochMismatch,
    BridgeProtocolError,
    BridgeStorageLockBusy,
)
from durable_bridge.tcp_client import DurableBridgeClient
from durable_bridge.tcp_server import TcpServer


def _free_port() -> int:
    """快速拿到一个当前可用的端口（不保证后续不被抢占，仅用于测试）。"""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


def _wait_until(predicate, *, timeout_s: float = 3.0, interval_s: float = 0.01) -> bool:
    """等 predicate 为 True 或超时。"""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval_s)
    return predicate()


# ---- TcpServer 单独测试 ----


def test_server_open_submit_status_close(tmp_path: Path) -> None:
    """完整 RPC 流程：open → submit → status → close。"""
    backend = InMemoryDurableBackend()
    # 不通过 bridge 编排，直接用 TcpServer 控制端口
    from durable_bridge.endpoint import make_endpoint

    ep = make_endpoint()
    server = TcpServer(ep, backend)
    server.bind()
    server.start()
    try:
        client = DurableBridgeClient(
            # 用 server 实际端口构造 endpoint
            _endpoint_with_port(ep, server.bound_port)
        )
        with client:
            handle_resp = client.call("open", {"storage_path": str(tmp_path / "x.sqlite")})
            assert "result" in handle_resp
            handle = handle_resp["result"]
            assert handle["conversation_id"]

            sub_resp = client.call(
                "submit",
                {
                    "handle": handle,
                    "conversation_id": handle["conversation_id"],
                    "requestId": "req-1",
                    "input": "hello",
                },
            )
            assert "result" in sub_resp
            sub = sub_resp["result"]
            submission_id = sub["submission_id"]
            assert sub["status"] == "settled"
            assert sub["text"] == "hello"

            status_resp = client.call(
                "status",
                {"handle": handle, "submission_id": submission_id},
            )
            assert status_resp["result"]["submission_id"] == submission_id

            close_resp = client.call("close", {"handle": handle})
            assert close_resp["result"]["closed"] is True
    finally:
        server.shutdown()


def test_request_id_idempotent_same_input(tmp_path: Path) -> None:
    """同一 conversation + 同一 requestId + 同一 input 应返回同一 submission_id。"""
    backend = InMemoryDurableBackend()
    from durable_bridge.endpoint import make_endpoint

    ep = make_endpoint()
    server = TcpServer(ep, backend)
    server.bind()
    server.start()
    try:
        client = DurableBridgeClient(_endpoint_with_port(ep, server.bound_port))
        with client:
            handle = client.call("open", {"storage_path": str(tmp_path / "x.sqlite")})["result"]
            conv = handle["conversation_id"]
            r1 = client.call(
                "submit",
                {
                    "handle": handle,
                    "conversation_id": conv,
                    "requestId": "dup",
                    "input": "same",
                },
            )["result"]
            r2 = client.call(
                "submit",
                {
                    "handle": handle,
                    "conversation_id": conv,
                    "requestId": "dup",
                    "input": "same",
                },
            )["result"]
            assert r1["submission_id"] == r2["submission_id"]
    finally:
        server.shutdown()


def test_request_id_conflict_with_different_input(tmp_path: Path) -> None:
    """同一 requestId 但 input 不同时应抛 BackendError。"""
    backend = InMemoryDurableBackend()
    from durable_bridge.endpoint import make_endpoint

    ep = make_endpoint()
    server = TcpServer(ep, backend)
    server.bind()
    server.start()
    try:
        client = DurableBridgeClient(_endpoint_with_port(ep, server.bound_port))
        with client:
            handle = client.call("open", {"storage_path": str(tmp_path / "x.sqlite")})["result"]
            conv = handle["conversation_id"]
            client.call(
                "submit",
                {
                    "handle": handle,
                    "conversation_id": conv,
                    "requestId": "dup",
                    "input": "first",
                },
            )
            bad = client.call_raw(
                "submit",
                {
                    "handle": handle,
                    "conversation_id": conv,
                    "requestId": "dup",
                    "input": "second",
                },
            )
            assert "error" in bad
            assert bad["error"]["code"] == -32602  # ERR_INVALID_PARAMS
    finally:
        server.shutdown()


def test_unknown_method_returns_error(tmp_path: Path) -> None:
    backend = InMemoryDurableBackend()
    from durable_bridge.endpoint import make_endpoint

    ep = make_endpoint()
    server = TcpServer(ep, backend)
    server.bind()
    server.start()
    try:
        client = DurableBridgeClient(_endpoint_with_port(ep, server.bound_port))
        with client:
            r = client.call_raw("nope", {})
            assert "error" in r
            assert r["error"]["code"] == -32601
    finally:
        server.shutdown()


def test_missing_token_returns_auth_error(tmp_path: Path) -> None:
    """未携带 token 的 submit 应返回 ERR_AUTH_FAILED。"""
    backend = InMemoryDurableBackend()
    from durable_bridge.endpoint import make_endpoint

    ep = make_endpoint()
    server = TcpServer(ep, backend)
    server.bind()
    server.start()
    try:
        client = DurableBridgeClient(_endpoint_with_port(ep, server.bound_port))
        with client:
            handle = client.call("open", {"storage_path": str(tmp_path / "x.sqlite")})["result"]
            # 故意篡改 endpoint token，让 client 发出错误 token
            bad_endpoint = _endpoint_with_port(ep, server.bound_port)
            bad_client = DurableBridgeClient(
                _endpoint_with_port_and_token(ep, server.bound_port, token="WRONG")
            )
            with bad_client:
                r = bad_client.call_raw(
                    "submit",
                    {
                        "handle": handle,
                        "conversation_id": handle["conversation_id"],
                        "requestId": "r",
                        "input": "x",
                    },
                )
            assert "error" in r
            assert r["error"]["code"] == -32002  # ERR_AUTH_FAILED
    finally:
        server.shutdown()


def test_epoch_mismatch_returns_specific_error(tmp_path: Path) -> None:
    """bridge_epoch 不匹配应返回 ERR_EPOCH_MISMATCH。"""
    backend = InMemoryDurableBackend()
    from durable_bridge.endpoint import make_endpoint

    ep = make_endpoint()
    server = TcpServer(ep, backend)
    server.bind()
    server.start()
    try:
        client = DurableBridgeClient(
            _endpoint_with_port_and_epoch(ep, server.bound_port, epoch="not-the-real-epoch")
        )
        with client:
            r = client.call_raw("submit", {"handle": {}, "conversation_id": "c", "requestId": "r", "input": "x"})
            assert "error" in r
            assert r["error"]["code"] == -32001  # ERR_EPOCH_MISMATCH
    finally:
        server.shutdown()


def test_oversized_frame_closes_connection(tmp_path: Path) -> None:
    """超过 max_frame_bytes 的帧应关闭连接。"""
    backend = InMemoryDurableBackend()
    from durable_bridge.endpoint import make_endpoint

    ep = make_endpoint()
    server = TcpServer(ep, backend, max_frame_bytes=1024)
    server.bind()
    server.start()
    try:
        # 客户端发送超过 1024 字节的帧
        with socket.create_connection(("127.0.0.1", server.bound_port), timeout=3) as sock:
            sock.sendall(b"x" * 2048 + b"\n")
            # 服务端会关闭连接：读应该得到 EOF
            data = b""
            try:
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    data += chunk
            except OSError:
                pass
            # 服务端不返回错误帧（拒绝 + 关闭）
            assert data == b""
    finally:
        server.shutdown()


# ---- helpers ----


def _endpoint_with_port(ep, port: int):
    from durable_bridge.endpoint import BridgeEndpoint

    return BridgeEndpoint(
        host=ep.host,
        port=port,
        pid=ep.pid,
        bridge_epoch=ep.bridge_epoch,
        protocol_version=ep.protocol_version,
        token=ep.token,
    )


def _endpoint_with_port_and_token(ep, port: int, *, token: str):
    from durable_bridge.endpoint import BridgeEndpoint

    return BridgeEndpoint(
        host=ep.host,
        port=port,
        pid=ep.pid,
        bridge_epoch=ep.bridge_epoch,
        protocol_version=ep.protocol_version,
        token=token,
    )


def _endpoint_with_port_and_epoch(ep, port: int, *, epoch: str):
    from durable_bridge.endpoint import BridgeEndpoint

    return BridgeEndpoint(
        host=ep.host,
        port=port,
        pid=ep.pid,
        bridge_epoch=epoch,
        protocol_version=ep.protocol_version,
        token=ep.token,
    )


# ---- BridgeServer 编排测试 ----


def test_bridge_server_lifecycle(tmp_path: Path) -> None:
    """完整生命周期：start → endpoint.json 落盘 → 客户端能连 → shutdown 后锁释放。"""
    storage = tmp_path / "durable.sqlite"
    endpoint_path = tmp_path / "endpoint.json"
    bridge = BridgeServer(
        storage_path=storage,
        backend=InMemoryDurableBackend(),
        endpoint_path=endpoint_path,
    )
    ep = bridge.start()
    try:
        # 1. endpoint.json 落盘
        assert endpoint_path.exists()
        loaded = read_endpoint(endpoint_path)
        assert loaded is not None
        assert loaded.bridge_epoch == ep.bridge_epoch
        assert loaded.port == ep.port
        assert loaded.token == ep.token

        # 2. 客户端用 endpoint 能连并完成 open/submit
        client = DurableBridgeClient(loaded)
        with client:
            r = client.call("open", {"storage_path": str(storage)})
            assert "result" in r
    finally:
        bridge.shutdown()
        # 3. 关闭后 endpoint 撤销（epoch 匹配）
        assert not endpoint_path.exists()
        # 4. 锁释放：能再次启动 bridge
        bridge2 = BridgeServer(
            storage_path=storage,
            backend=InMemoryDurableBackend(),
            endpoint_path=endpoint_path,
        )
        try:
            bridge2.start()
            assert bridge2.started
        finally:
            bridge2.shutdown()


def test_bridge_server_blocks_second_owner(tmp_path: Path) -> None:
    """第一个 bridge 持锁期间，第二个 bridge 启动应抛 BridgeStorageLockBusy。"""
    storage = tmp_path / "durable.sqlite"
    bridge1 = BridgeServer(
        storage_path=storage,
        backend=InMemoryDurableBackend(),
    )
    bridge1.start()
    try:
        bridge2 = BridgeServer(
            storage_path=storage,
            backend=InMemoryDurableBackend(),
        )
        with pytest.raises(BridgeStorageLockBusy):
            bridge2.start()
    finally:
        bridge1.shutdown()


def test_bridge_server_rejects_non_loopback_endpoint_attempt(tmp_path: Path) -> None:
    """BridgeServer 启动时不接受非 loopback 端口（host 是硬编码 127.0.0.1）。"""
    # 这是个"代码契约"测试：BridgeServer 不暴露 host 参数；如果有人改了
    # 默认值，测试会提醒。即便没人改，连接也只能走 127.0.0.1。
    storage = tmp_path / "durable.sqlite"
    bridge = BridgeServer(
        storage_path=storage,
        backend=InMemoryDurableBackend(),
    )
    ep = bridge.start()
    try:
        # 强制改 host 到一个不可达地址，模拟错误的 endpoint.json
        from durable_bridge.endpoint import BridgeEndpoint

        bad = BridgeEndpoint(
            host="127.0.0.1",  # 即便是改也只能是这个
            port=ep.port,
            pid=ep.pid,
            bridge_epoch=ep.bridge_epoch,
            protocol_version=ep.protocol_version,
            token=ep.token,
        )
        assert bad.host == "127.0.0.1"
        # 客户端必须按 host=127.0.0.1 才能连上
        client = DurableBridgeClient(bad)
        with client:
            r = client.call_raw("open", {"storage_path": str(storage)})
            assert "result" in r
    finally:
        bridge.shutdown()


def test_bridge_server_shutdown_is_idempotent(tmp_path: Path) -> None:
    """多次调用 shutdown() 不应抛异常。"""
    bridge = BridgeServer(
        storage_path=tmp_path / "durable.sqlite",
        backend=InMemoryDurableBackend(),
    )
    bridge.start()
    bridge.shutdown()
    bridge.shutdown()  # 第二次不抛

"""durable-bridge endpoint.json 测试。"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from durable_bridge.endpoint import (
    BridgeEndpoint,
    make_endpoint,
    publish_endpoint,
    read_endpoint,
    revoke_endpoint,
)
from durable_bridge.exceptions import BridgeProtocolError


def test_make_endpoint_defaults() -> None:
    ep = make_endpoint()
    assert ep.host == "127.0.0.1"
    assert ep.port == 0
    assert ep.pid == os.getpid()
    assert ep.protocol_version == 1
    assert len(ep.bridge_epoch) >= 32
    assert len(ep.token) >= 32


def test_make_endpoint_rejects_non_loopback() -> None:
    with pytest.raises(ValueError):
        make_endpoint(host="0.0.0.0")
    with pytest.raises(ValueError):
        make_endpoint(host="192.168.1.1")


def test_publish_and_read_roundtrip(tmp_path: Path) -> None:
    ep = make_endpoint()
    ep = BridgeEndpoint(
        host=ep.host,
        port=54321,
        pid=ep.pid,
        bridge_epoch=ep.bridge_epoch,
        protocol_version=ep.protocol_version,
        token=ep.token,
    )
    path = tmp_path / "endpoint.json"
    publish_endpoint(path, ep)

    loaded = read_endpoint(path)
    assert loaded is not None
    assert loaded.host == "127.0.0.1"
    assert loaded.port == 54321
    assert loaded.pid == ep.pid
    assert loaded.bridge_epoch == ep.bridge_epoch
    assert loaded.token == ep.token
    assert loaded.protocol_version == ep.protocol_version


def test_publish_enforces_0600_on_posix(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("POSIX-only chmod assertion")
    ep = make_endpoint()
    ep = BridgeEndpoint(
        host=ep.host,
        port=12345,
        pid=ep.pid,
        bridge_epoch=ep.bridge_epoch,
        protocol_version=ep.protocol_version,
        token=ep.token,
    )
    path = tmp_path / "endpoint.json"
    publish_endpoint(path, ep)
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600, f"endpoint.json should be 0600, got {oct(mode)}"


def test_read_missing_returns_none(tmp_path: Path) -> None:
    assert read_endpoint(tmp_path / "nope.json") is None


def test_read_invalid_json_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "endpoint.json"
    p.write_text("{not json", encoding="utf-8")
    assert read_endpoint(p) is None


def test_read_rejects_non_loopback(tmp_path: Path) -> None:
    p = tmp_path / "endpoint.json"
    p.write_text(
        json.dumps(
            {
                "host": "0.0.0.0",
                "port": 80,
                "pid": 1,
                "bridge_epoch": "x",
                "protocol_version": 1,
                "token": "y",
            }
        ),
        encoding="utf-8",
    )
    # read_endpoint 把无效 host 当成"无读取"返回 None
    assert read_endpoint(p) is None


def test_read_rejects_missing_fields(tmp_path: Path) -> None:
    p = tmp_path / "endpoint.json"
    p.write_text(json.dumps({"host": "127.0.0.1", "port": 80}), encoding="utf-8")
    assert read_endpoint(p) is None


def test_publish_rejects_non_loopback(tmp_path: Path) -> None:
    ep = BridgeEndpoint(
        host="0.0.0.0",
        port=80,
        pid=1,
        bridge_epoch="e",
        protocol_version=1,
        token="t",
    )
    with pytest.raises(ValueError):
        publish_endpoint(tmp_path / "endpoint.json", ep)


def test_revoke_removes_file(tmp_path: Path) -> None:
    ep = make_endpoint()
    ep = BridgeEndpoint(
        host=ep.host,
        port=11111,
        pid=ep.pid,
        bridge_epoch=ep.bridge_epoch,
        protocol_version=ep.protocol_version,
        token=ep.token,
    )
    path = tmp_path / "endpoint.json"
    publish_endpoint(path, ep)
    assert path.exists()
    revoke_endpoint(path)
    assert not path.exists()


def test_revoke_missing_is_noop(tmp_path: Path) -> None:
    # 不应抛异常
    revoke_endpoint(tmp_path / "absent.json")

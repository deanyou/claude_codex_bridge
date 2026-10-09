"""durable-bridge 协议层单元测试。"""

from __future__ import annotations

import json

import pytest

from durable_bridge.exceptions import (
    BridgeOversizedFrame,
    BridgeProtocolError,
)
from durable_bridge.protocol import (
    DEFAULT_MAX_FRAME_BYTES,
    PROTOCOL_VERSION,
    build_error_response,
    build_notification,
    build_request,
    build_result_response,
    encode_frame,
    parse_frame_line,
)


def test_build_request_basic() -> None:
    req = build_request("open", {"storage_path": "/x"})
    assert req["jsonrpc"] == "2.0"
    assert req["method"] == "open"
    assert req["params"] == {"storage_path": "/x"}
    assert isinstance(req["id"], str)
    assert len(req["id"]) > 0


def test_build_request_explicit_id() -> None:
    req = build_request("submit", {"x": 1}, request_id="abc")
    assert req["id"] == "abc"


def test_build_request_rejects_empty_method() -> None:
    with pytest.raises(BridgeProtocolError):
        build_request("")


def test_build_notification_no_id() -> None:
    n = build_notification("ping")
    assert n["jsonrpc"] == "2.0"
    assert n["method"] == "ping"
    assert "id" not in n


def test_build_result_response() -> None:
    r = build_result_response("abc", {"ok": True})
    assert r == {"jsonrpc": "2.0", "id": "abc", "result": {"ok": True}}


def test_build_error_response_with_data() -> None:
    r = build_error_response("abc", code=-32001, message="epoch", data={"got": "x"})
    assert r["jsonrpc"] == "2.0"
    assert r["id"] == "abc"
    assert r["error"]["code"] == -32001
    assert r["error"]["message"] == "epoch"
    assert r["error"]["data"] == {"got": "x"}


def test_encode_decode_roundtrip() -> None:
    req = build_request("foo", {"a": 1, "b": "中"}, request_id="id-1")
    data = encode_frame(req)
    assert data.endswith(b"\n")
    parsed = parse_frame_line(data)
    assert parsed == req


def test_parse_handles_crlf() -> None:
    req = build_request("foo", request_id="id-1")
    data = encode_frame(req).replace(b"\n", b"\r\n")
    parsed = parse_frame_line(data)
    assert parsed == req


def test_parse_rejects_oversized() -> None:
    huge = b"x" * (DEFAULT_MAX_FRAME_BYTES + 1) + b"\n"
    with pytest.raises(BridgeOversizedFrame):
        parse_frame_line(huge)


def test_parse_rejects_empty() -> None:
    with pytest.raises(BridgeProtocolError):
        parse_frame_line(b"\n")


def test_parse_rejects_invalid_json() -> None:
    with pytest.raises(BridgeProtocolError):
        parse_frame_line(b"{not-json}\n")


def test_parse_rejects_missing_jsonrpc_field() -> None:
    payload = json.dumps({"method": "x", "id": "1"}) + "\n"
    with pytest.raises(BridgeProtocolError):
        parse_frame_line(payload.encode("utf-8"))


def test_parse_rejects_non_dict_payload() -> None:
    with pytest.raises(BridgeProtocolError):
        parse_frame_line(b"42\n")


def test_parse_rejects_non_utf8() -> None:
    # 0xff 单独字节不是合法 UTF-8 起头
    with pytest.raises(BridgeProtocolError):
        parse_frame_line(b"\xff\xfe\x00bad\n")


def test_protocol_version_constant() -> None:
    assert PROTOCOL_VERSION == 1

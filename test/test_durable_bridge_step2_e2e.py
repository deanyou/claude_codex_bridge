"""步骤 2 端到端集成测试：bridge + backend + 绑定账本 + 会话恢复。"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from durable_bridge.backend import InMemoryDurableBackend
from durable_bridge.bridge import BridgeServer
from durable_bridge.binding_ledger import (
    BindingConflict,
    BindingLedger,
)
from durable_bridge.endpoint import make_endpoint, read_endpoint
from durable_bridge.tcp_client import DurableBridgeClient
from durable_bridge.tcp_server import TcpServer
from storage.paths import PathLayout


# ---- helpers ----


def _spawn_bridge_server(
    backend: InMemoryDurableBackend,
) -> tuple[TcpServer, BridgeEndpoint]:
    ep = make_endpoint()
    server = TcpServer(ep, backend)
    server.bind()
    server.start()
    final = ep.__class__(
        host=ep.host,
        port=server.bound_port,
        pid=ep.pid,
        bridge_epoch=ep.bridge_epoch,
        protocol_version=ep.protocol_version,
        token=ep.token,
    )
    server._endpoint = final
    return server, final


def _input_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


# ---- 端到端 happy path ----


def test_end_to_end_register_open_resume(tmp_path: Path) -> None:
    """完整链路：注入 conversation → open 拿 handle → submit → close handle →
    新 handle 同 conversation 重开 → 仍能查同一 submission。"""
    backend = InMemoryDurableBackend()
    server, ep = _spawn_bridge_server(backend)
    try:
        client = DurableBridgeClient(ep)
        with client:
            # 0. 注入一个"已知" conversation
            reg = client.call_raw("register_conversation", {"conversation_id": "conv-A"})
            assert reg["result"]["registered"] is True

            # 1. 用该 conversation 打开
            open1 = client.call_raw("open", {"storage_path": str(tmp_path / "x.sqlite"), "conversation_id": "conv-A"})
            assert "result" in open1
            h1 = open1["result"]
            assert h1["conversation_id"] == "conv-A"

            # 2. submit
            sub1 = client.call_raw(
                "submit",
                {
                    "handle": h1,
                    "conversation_id": "conv-A",
                    "requestId": "req-1",
                    "input": "hello",
                },
            )
            assert "result" in sub1
            sub_id_1 = sub1["result"]["submission_id"]

            # 3. 关闭 handle
            client.call_raw("close", {"handle": h1})

            # 4. 用同一 conversation 重新 open
            open2 = client.call_raw("open", {"storage_path": str(tmp_path / "x.sqlite"), "conversation_id": "conv-A"})
            assert "result" in open2
            h2 = open2["result"]
            assert h2["conversation_id"] == "conv-A"
            assert h2["handle_id"] != h1["handle_id"]

            # 5. 同一 (conv, reqId) → 同一 submission
            sub2 = client.call_raw(
                "submit",
                {
                    "handle": h2,
                    "conversation_id": "conv-A",
                    "requestId": "req-1",
                    "input": "hello",
                },
            )
            assert "result" in sub2
            assert sub2["result"]["submission_id"] == sub_id_1
    finally:
        server.shutdown()


def test_end_to_end_unknown_conversation_rejected(tmp_path: Path) -> None:
    """客户端传未注册的 conversation_id 必须在 open() 阶段被拒。"""
    backend = InMemoryDurableBackend()
    server, ep = _spawn_bridge_server(backend)
    try:
        client = DurableBridgeClient(ep)
        with client:
            r = client.call_raw(
                "open",
                {"storage_path": str(tmp_path / "x.sqlite"), "conversation_id": "never-registered"},
            )
            assert "error" in r
            # BackendNotFound 在 server 翻译为 ERR_INVALID_PARAMS（-32602）
            assert r["error"]["code"] == -32602
    finally:
        server.shutdown()


# ---- 账本 + 状态序列 ----


def test_ledger_records_state_sequence(tmp_path: Path) -> None:
    """daemon 视角：intent → submit → 补记 submission_id 是合规的 3 步。"""
    layout = PathLayout(project_root=tmp_path)
    ledger = BindingLedger(layout)

    # 第 1 步：record_intent（在 submit 之前落盘）
    intent = ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash=_input_hash("hello"),
        storage_path=str(tmp_path / "x.sqlite"),
        bridge_epoch="ep-test",
    )
    assert intent.delivery_phase == "intent"

    # 第 2 步：MailboxKernelService.claim()（步骤 3 接入；本测试用占位）
    # 假设 claim 成功。

    # 第 3 步：submit 通过 bridge
    backend = InMemoryDurableBackend()
    server, ep = _spawn_bridge_server(backend)
    try:
        client = DurableBridgeClient(ep)
        with client:
            client.call_raw("register_conversation", {"conversation_id": "conv-A"})
            h = client.call_raw("open", {"storage_path": str(tmp_path / "x.sqlite"), "conversation_id": "conv-A"})["result"]
            # v4 步骤 4：submit 之前先持久补 conversation
            bound = ledger.record_conversation_bound(
                "b-1",
                conversation_id=h["conversation_id"],
                bridge_epoch="ep-test",
            )
            assert bound.delivery_phase == "conversation_bound"
            assert bound.conversation_id == "conv-A"
            sub = client.call_raw(
                "submit",
                {
                    "handle": h,
                    "conversation_id": "conv-A",
                    "requestId": "req-1",
                    "input": "hello",
                },
            )["result"]
        # 第 4 步：持久补记 submission
        after = ledger.record_submission(
            "b-1",
            conversation_id="conv-A",
            submission_id=sub["submission_id"],
            bridge_epoch="ep-test",
        )
        assert after.delivery_phase == "submitted"
        assert after.conversation_id == "conv-A"
        assert after.submission_id == sub["submission_id"]
    finally:
        server.shutdown()

    # 重新读出（模拟进程重启）应得到一致结果
    fresh = BindingLedger(layout)
    found = fresh.lookup_by_submission_id(sub["submission_id"])
    assert found is not None
    assert found.delivery_phase == "submitted"
    assert found.inbound_event_id == "evt-1"


def test_ledger_blocks_resubmit_with_different_input(tmp_path: Path) -> None:
    """核心安全网：record_intent 用同 requestId + 不同 input 必须被拒。"""
    layout = PathLayout(project_root=tmp_path)
    ledger = BindingLedger(layout)
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="m",
        attempt_id="a",
        request_id="req-1",
        input_hash=_input_hash("first"),
        storage_path="/p",
        bridge_epoch="ep",
    )
    # 模拟 daemon 重启后从某处拉来一个"同一 requestId 但 input 变了"的请求
    with pytest.raises(BindingConflict):
        ledger.record_intent(
            "b-1",
            inbound_event_id="evt-1",
            message_id="m",
            attempt_id="a",
            request_id="req-1",
            input_hash=_input_hash("second"),
            storage_path="/p",
            bridge_epoch="ep",
        )


# ---- 跨进程恢复 ----


def test_ledger_visible_to_separate_process(tmp_path: Path) -> None:
    """通过真实子进程验证账本是文件系统级别的、跨进程可查。"""
    layout = PathLayout(project_root=tmp_path)
    write_ledger = BindingLedger(layout)
    write_ledger.record_intent(
        "b-1",
        inbound_event_id="evt-cross",
        message_id="m",
        attempt_id="a",
        request_id="r",
        input_hash="h",
        storage_path="/p",
        bridge_epoch="ep",
    )

    # 写一个 Python 脚本作为子进程：用独立 PathLayout 读
    script = tmp_path / "child.py"
    script.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str((Path.cwd() / 'lib').as_posix())!r})\n"
        "from pathlib import Path\n"
        f"root = Path({str(tmp_path.as_posix())!r})\n"
        "from storage.paths import PathLayout\n"
        "from durable_bridge.binding_ledger import BindingLedger\n"
        "layout = PathLayout(project_root=root)\n"
        "ledger = BindingLedger(layout)\n"
        "rec = ledger.lookup_by_inbound_event('evt-cross')\n"
        "assert rec is not None, 'cross-process lookup failed'\n"
        "assert rec.binding_id == 'b-1'\n"
        "print('OK', rec.binding_id, rec.delivery_phase)\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"child failed: {result.stderr}"
    assert "OK b-1 intent" in result.stdout

"""durable-bridge backend resume 语义测试（步骤 2）。"""

from __future__ import annotations

import pytest

from durable_bridge.backend import (
    BackendError,
    BackendNotFound,
    InMemoryDurableBackend,
    SubmissionState,
)


def test_open_creates_new_conversation_by_default() -> None:
    b = InMemoryDurableBackend()
    h = b.open("/tmp/x.sqlite")
    assert h["conversation_id"]
    assert h["storage_path"] == "/tmp/x.sqlite"
    # 同一进程两次 open 得到不同 conversation
    h2 = b.open("/tmp/x.sqlite")
    assert h2["conversation_id"] != h["conversation_id"]


def test_open_with_known_conversation_resumes() -> None:
    b = InMemoryDurableBackend()
    h1 = b.open("/tmp/x.sqlite")
    conv = h1["conversation_id"]
    b.close(h1)
    # 用原 conv 重新 open
    h2 = b.open("/tmp/x.sqlite", conversation_id=conv)
    assert h2["conversation_id"] == conv
    # handle_id 不同（每次都是新句柄），但 conversation 相同
    assert h2["handle_id"] != h1["handle_id"]


def test_open_with_unknown_conversation_rejects() -> None:
    b = InMemoryDurableBackend()
    with pytest.raises(BackendNotFound):
        b.open("/tmp/x.sqlite", conversation_id="never-existed")
    # 不能因为传入 conversation_id 就"以为新建了"——之后看 conversations 列表
    # 不应包含该 ID
    assert "never-existed" not in b.list_conversations()


def test_register_conversation_then_open() -> None:
    """显式注入已知 conversation 之后可被 open 找回。"""
    b = InMemoryDurableBackend()
    b.register_conversation("injected-conv-1")
    h = b.open("/tmp/y.sqlite", conversation_id="injected-conv-1")
    assert h["conversation_id"] == "injected-conv-1"


def test_submit_through_resumed_conversation_returns_same_submission() -> None:
    """同 conversation + 同 requestId 跨多个 open 都返回同一 submission_id。"""
    b = InMemoryDurableBackend()
    h1 = b.open("/tmp/x.sqlite")
    conv = h1["conversation_id"]
    s1 = b.submit(h1, conv, "req-1", "hello")
    b.close(h1)

    h2 = b.open("/tmp/x.sqlite", conversation_id=conv)
    s2 = b.submit(h2, conv, "req-1", "hello")
    assert s1.submission_id == s2.submission_id


def test_submit_conflict_on_resume_with_different_input() -> None:
    """恢复后用同 requestId 但不同 input 必须抛 BackendError。"""
    b = InMemoryDurableBackend()
    h1 = b.open("/tmp/x.sqlite")
    conv = h1["conversation_id"]
    b.submit(h1, conv, "req-1", "original")
    b.close(h1)

    h2 = b.open("/tmp/x.sqlite", conversation_id=conv)
    with pytest.raises(BackendError):
        b.submit(h2, conv, "req-1", "different")


def test_close_does_not_lose_conversation() -> None:
    """close 只清 handle；conversation 仍可恢复。"""
    b = InMemoryDurableBackend()
    h = b.open("/tmp/x.sqlite")
    conv = h["conversation_id"]
    b.close(h)
    assert conv in b.list_conversations()


def test_list_conversations_after_mixed_open() -> None:
    b = InMemoryDurableBackend()
    h1 = b.open("/tmp/a.sqlite")
    h2 = b.open("/tmp/b.sqlite")
    b.register_conversation("manual-1")
    convs = b.list_conversations()
    assert h1["conversation_id"] in convs
    assert h2["conversation_id"] in convs
    assert "manual-1" in convs


def test_open_rejects_empty_storage_path() -> None:
    b = InMemoryDurableBackend()
    with pytest.raises(BackendError):
        b.open("")
    with pytest.raises(BackendError):
        b.open(123)  # type: ignore[arg-type]


def test_open_rejects_empty_conversation_id() -> None:
    b = InMemoryDurableBackend()
    with pytest.raises(BackendError):
        b.open("/tmp/x.sqlite", conversation_id="")
    with pytest.raises(BackendError):
        b.open("/tmp/x.sqlite", conversation_id=42)  # type: ignore[arg-type]

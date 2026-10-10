"""durable-bridge backend 契约测试（v4 步骤 2 重构版）。

⚠️ 状态：contract prototype

本文件测试 DurableBackend 协议的关键不变量（v4 规格 09 节 RPC 表）：

  - 同一 (conversation_id, requestId) 的 submit 必返回同一 submission_id
  - 同一 input_hash 的 submit 必返回同一 submission_id
  - 不同 input_hash 但同 requestId 抛 BackendError
  - open() 不指定 conversation_id 时生成新会话；指定时必须已存在
  - close() 仅移除 handle；conversation + submission 仍可恢复
  - register_conversation() 注入已知会话；list_conversations() 用于索引重建

测试通过 backend_factory fixture 参数化。当前唯一注册的是
InMemoryDurableBackend（Python 占位）。当 PiDurableBackend（包装
Node 端 @earendil-works/pi-durable）就绪后，追加到 BACKEND_FACTORIES
即可让同一组测试在真 SQLite + 真跨进程恢复场景下运行。

未覆盖项（必须等真正后端就绪后另立测试）：
  - 跨进程 SQLite 持久化（当前 storage_path 仅为字符串，不验证恢复）
  - Node 子进程 @earendil-works/pi-durable 集成
  - 工具 replay: "safe" / interrupted 语义
  - dispatch_key 幂等去重
"""

from __future__ import annotations

import pytest

from durable_bridge.backend import (
    BackendError,
    BackendNotFound,
    InMemoryDurableBackend,
    SubmissionState,
)


# ---- backend factory registry ----
#
# 新增后端时追加：
#   "pi_durable": lambda: PiDurableBackend(...)
# pytest 会在所有注册后端上跑同一组测试。
# ----

BACKEND_FACTORIES = {
    "in_memory": lambda: InMemoryDurableBackend(),
    # "pi_durable": lambda: PiDurableBackend(...),  # TODO: not implemented
}


def _factory_ids():
    return list(BACKEND_FACTORIES.keys())


def _factory_values():
    return list(BACKEND_FACTORIES.values())


@pytest.fixture(params=_factory_values(), ids=_factory_ids())
def backend_factory(request):
    """每个测试用 fresh backend 实例。"""
    return request.param


# ---- open / handle ----


def test_open_creates_new_conversation_by_default(backend_factory):
    b = backend_factory()
    h = b.open("/tmp/x.sqlite")
    assert h["conversation_id"]
    assert h["storage_path"] == "/tmp/x.sqlite"
    h2 = b.open("/tmp/x.sqlite")
    assert h2["conversation_id"] != h["conversation_id"]


def test_open_with_known_conversation_resumes(backend_factory):
    b = backend_factory()
    h1 = b.open("/tmp/x.sqlite")
    conv = h1["conversation_id"]
    b.close(h1)
    h2 = b.open("/tmp/x.sqlite", conversation_id=conv)
    assert h2["conversation_id"] == conv
    assert h2["handle_id"] != h1["handle_id"]


def test_open_with_unknown_conversation_rejects(backend_factory):
    b = backend_factory()
    with pytest.raises(BackendNotFound):
        b.open("/tmp/x.sqlite", conversation_id="never-existed")
    assert "never-existed" not in b.list_conversations()


def test_register_conversation_then_open(backend_factory):
    b = backend_factory()
    b.register_conversation("injected-conv-1")
    h = b.open("/tmp/y.sqlite", conversation_id="injected-conv-1")
    assert h["conversation_id"] == "injected-conv-1"


# ---- submit / idempotency ----


def test_submit_through_resumed_conversation_returns_same_submission(backend_factory):
    b = backend_factory()
    h1 = b.open("/tmp/x.sqlite")
    conv = h1["conversation_id"]
    s1 = b.submit(h1, conv, "req-1", "hello")
    b.close(h1)
    h2 = b.open("/tmp/x.sqlite", conversation_id=conv)
    s2 = b.submit(h2, conv, "req-1", "hello")
    assert s1.submission_id == s2.submission_id


def test_submit_conflict_on_resume_with_different_input(backend_factory):
    b = backend_factory()
    h1 = b.open("/tmp/x.sqlite")
    conv = h1["conversation_id"]
    b.submit(h1, conv, "req-1", "original")
    b.close(h1)
    h2 = b.open("/tmp/x.sqlite", conversation_id=conv)
    with pytest.raises(BackendError):
        b.submit(h2, conv, "req-1", "different")


# ---- close / list ----


def test_close_does_not_lose_conversation(backend_factory):
    b = backend_factory()
    h = b.open("/tmp/x.sqlite")
    conv = h["conversation_id"]
    b.close(h)
    assert conv in b.list_conversations()


def test_list_conversations_after_mixed_open(backend_factory):
    b = backend_factory()
    h1 = b.open("/tmp/a.sqlite")
    h2 = b.open("/tmp/b.sqlite")
    b.register_conversation("manual-1")
    convs = b.list_conversations()
    assert h1["conversation_id"] in convs
    assert h2["conversation_id"] in convs
    assert "manual-1" in convs


# ---- input validation ----


def test_open_rejects_empty_storage_path(backend_factory):
    b = backend_factory()
    with pytest.raises(BackendError):
        b.open("")
    with pytest.raises(BackendError):
        b.open(123)  # type: ignore[arg-type]


def test_open_rejects_empty_conversation_id(backend_factory):
    b = backend_factory()
    with pytest.raises(BackendError):
        b.open("/tmp/x.sqlite", conversation_id="")
    with pytest.raises(BackendError):
        b.open("/tmp/x.sqlite", conversation_id=42)  # type: ignore[arg-type]

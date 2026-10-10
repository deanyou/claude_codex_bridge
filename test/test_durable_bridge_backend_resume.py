"""durable-bridge backend 契约测试（v4 步骤 2 接通 pi-durable）。

本文件通过 ``backend_factory`` fixture 参数化，两套 backend 同时跑：
  - ``[in_memory]`` — Python 进程内 InMemoryDurableBackend（base 占位）
  - ``[pi_durable]`` — Node 子进程 + @earendil-works/pi-durable 1.1.0
    真 SQLite 持久化、跨 reopen 幂等、跨进程恢复证据

覆盖 DurableBackend Protocol 的关键不变量（v4 规格 09 节 RPC 表）：

  - 同一 (conversation_id, requestId) 的 submit 必返回同一 submission_id
  - 同一 input_hash 的 submit 必返回同一 submission_id
  - 不同 input_hash 但同 requestId 抛 BackendError
  - open() 不指定 conversation_id 时生成新会话；指定时必须已存在
  - close() 仅移除 handle；conversation + submission 仍可恢复
  - register_conversation() 注入已知会话；list_conversations() 用于索引重建

[pi_durable] 的环境要求（不满足时整组 skip，不 fail）：

  - ``node`` 进程必须能在 PATH 上找到（engines>=22.19.0）
  - ``tools/pi_durable_bridge/node_modules/@earendil-works/pi-durable`` 必须存在
  - 见 ``test_durable_bridge_pi_durable.py::test_skipif_predicate_*`` 验证该判定

仍未覆盖的项（Step 3/4/5 范畴）：
  - replay: "safe" / interrupted 语义（Step 4）
  - dispatch_key 幂等去重（Step 4）
  - 替换生产路径默认 backend（Step 5）
  - 进程级 advisory lock 协调同一 SQLite 多 backend 共存（Step 3）

跨进程恢复的强证据见 ``test_durable_bridge_pi_durable.py::test_pi_durable_cross_process_recovery``，
那条测试用 subprocess 启动独立 child Python 写 SQLite、父进程 brand new PiDurableBackend 读回。
"""

from __future__ import annotations

import pytest

from durable_bridge.backend import (
    BackendError,
    BackendNotFound,
    InMemoryDurableBackend,
    SubmissionState,
)


def _pi_durable_factory():
    """Lazy factory for PiDurableBackend.

    Skips via ``pytest.skip`` are handled in test_pi_durable_worker_starts below;
    here we just instantiate so the parametrized suite can run on machines that
    have node + @earendil-works/pi-durable.
    """
    from durable_bridge.pi_durable_backend import PiDurableBackend
    return PiDurableBackend()


def _in_memory_factory():
    return InMemoryDurableBackend()


def _pi_durable_skipif_predicate() -> bool:
    """Pytest collection-time guard: True iff pi-durable environment is OK.

    Mirrors ``durable_bridge.pi_durable_backend._worker_deps_available`` so the
    parametrize ``skipif`` mark is satisfiable from a helper import without
    re-implementing the logic.
    """
    from durable_bridge.pi_durable_backend import _worker_deps_available
    return not _worker_deps_available()


_skipif_no_pi_durable = pytest.mark.skipif(
    _pi_durable_skipif_predicate(),
    reason=(
        "pi-durable backend needs: "
        "``node`` on PATH + tools/pi_durable_bridge/node_modules/@earendil-works/pi-durable"
    ),
)


@pytest.fixture(
    params=[
        pytest.param(_in_memory_factory, id="in_memory"),
        pytest.param(_pi_durable_factory, id="pi_durable", marks=_skipif_no_pi_durable),
    ]
)
def backend_factory(request):
    """每个测试用 fresh backend 实例.

    ``request.param`` 是零参 factory（callable），测试代码用
    ``backend_factory()`` 拿到 fresh backend 实例。

    在缺少 ``node`` 或 ``@earendil-works/pi-durable`` 的环境下，``[pi_durable]``
    参数化变体会自动 skip（而非 fail）；``[in_memory]`` 永远跑。
    """
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

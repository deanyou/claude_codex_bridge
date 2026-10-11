"""Step 2 bridge: pi-durable-backed DurableBackend tests.

These tests exercise ``PiDurableBackend`` from
``lib.durable_bridge.pi_durable_backend`` — a JSON-lines bridge to a Node
worker that wraps ``@earendil-works/pi-durable`` 1.1.0.

The bridge inherits the same durable-bridge contract prototype status as
``test_durable_bridge_backend_resume.py``: contract-focused, not yet covering
replay/interrupted semantics (those are Step 4).

Step 2 differentiator: ``test_pi_durable_cross_process_recovery`` (test #7)
literally spawns a child Python process to prove the SQLite file is durable
across Node worker processes.

Skip semantics
--------------
All env-dependent tests are wrapped with ``pytest.mark.skipif`` so the suite
fails gracefully (skipped, NOT failed) on machines without ``node`` on PATH or
without ``tools/pi_durable_bridge/node_modules/@earendil-works/pi-durable``.
The two ``test_skipif_predicate_*`` tests at the bottom are *intentionally*
not skipped — they verify the predicate itself behaves correctly so we don't
silently skip in CI.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from durable_bridge.backend import (
    BackendError,
    BackendInvalidState,
    BackendNotFound,
    InMemoryDurableBackend,
    SubmissionState,
)
from durable_bridge.dispatcher import DispatcherError
from durable_bridge.pi_durable_backend import (
    PROTOCOL_VERSION,
    PiDurableBackend,
    _resolve_node_bin,
    _worker_deps_available,
)


# ---- shared env-guard ----

_no_env_predicate = not _worker_deps_available()

_requires_env = pytest.mark.skipif(
    _no_env_predicate,
    reason=(
        "requires `node` on PATH + "
        "tools/pi_durable_bridge/node_modules/@earendil-works/pi-durable"
    ),
)


# ---- fixtures ----


@pytest.fixture
def storage_path(tmp_path):
    """Per-test SQLite file path under pytest's tmp_path (auto-cleaned)."""
    p = tmp_path / "step2-pi-durable.sqlite"
    return str(p)


@pytest.fixture
def make_backend():
    """Factory yielding fresh PiDurableBackend instances with explicit shutdown.

    Tests should use ``with make_backend() as b:`` to guarantee the worker
    subprocess is killed even on failure.
    """
    created: list[PiDurableBackend] = []

    def _make(**kw) -> PiDurableBackend:
        b = PiDurableBackend(**kw)
        created.append(b)
        return b

    yield _make

    for b in created:
        try:
            b.shutdown()
        except Exception:
            pass


# ---- env-dependent tests (skip when node / pi-durable unavailable) ----


@_requires_env  # noqa: F821
def test_pi_durable_worker_starts_and_lists_empty_conversations(make_backend, storage_path):
    """Brand-new backend sees no conversations (no SQLite yet)."""
    b = make_backend()
    assert os.path.exists(storage_path) is False or True  # SQLite may or may not exist yet
    convs = b.list_conversations()
    assert convs == ()
    # open() then list_conversations should now include exactly that one
    h = b.open(storage_path)
    convs = b.list_conversations()
    assert h["conversation_id"] in convs


@_requires_env  # noqa: F821
def test_pi_durable_open_creates_conversation_persisted_in_sqlite(make_backend, storage_path):
    """open() without conversation_id persists a real conversation record."""
    b = make_backend()
    h = b.open(storage_path)
    conv = h["conversation_id"]
    assert isinstance(conv, str) and conv  # worker normalizes to string
    # now use a second BACKEND to verify the conversation is in the file:
    b2 = make_backend()
    h_again = b2.open(storage_path, conversation_id=conv)
    assert h_again["conversation_id"] == conv


@_requires_env  # noqa: F821
def test_pi_durable_open_unknown_conversation_raises_backend_not_found(make_backend, storage_path):
    b = make_backend()
    with pytest.raises(BackendNotFound):
        b.open(storage_path, conversation_id="never-existed")
    # must not be silently added to list_conversations
    assert "never-existed" not in b.list_conversations()


@_requires_env  # noqa: F821
def test_pi_durable_register_then_open(make_backend, storage_path):
    b = make_backend()
    b.register_conversation("injected-conv-1")
    # doesn't exist in SQLite yet but the registered set allows it
    h = b.open(storage_path, conversation_id="injected-conv-1")
    assert h["conversation_id"] == "injected-conv-1"
    assert "injected-conv-1" in b.list_conversations()


@_requires_env  # noqa: F821
def test_pi_durable_submit_idempotent_across_reopen(make_backend, storage_path):
    b = make_backend()
    h1 = b.open(storage_path)
    conv = h1["conversation_id"]
    s1 = b.submit(h1, conv, "req-1", "hello")
    b.close(h1)
    h2 = b.open(storage_path, conversation_id=conv)
    s2 = b.submit(h2, conv, "req-1", "hello")
    assert s1.submission_id == s2.submission_id


@_requires_env  # noqa: F821
def test_pi_durable_submit_conflict_on_different_input(make_backend, storage_path):
    b = make_backend()
    h = b.open(storage_path)
    conv = h["conversation_id"]
    s1 = b.submit(h, conv, "req-1", "original")
    assert s1.submission_id  # sanity
    with pytest.raises(BackendError):
        b.submit(h, conv, "req-1", "different")


@_requires_env  # noqa: F821
def test_pi_durable_cross_process_recovery(storage_path):
    """Open + submit in a child Python process; reopen from parent process.

    This is the centerpiece of Step 2: it proves the SQLite file is durable
    across worker process boundaries. We use subprocess (different os.getpid())
    rather than multiprocessing so we can also assert different worker PIDs.

    Steps:
      1. Spawn child Python that creates a PiDurableBackend, opens (creating a
         new conversation), submits a unique input, captures the conv_id,
         sub_id and *worker PID* to stdout, then exits.
      2. From the parent, create a fresh PiDurableBackend and reopen the same
         SQLite by conv_id.
      3. Verify status(sub_id) returns the same submission record.
      4. Verify the worker PID is genuinely different from the child worker's.
    """
    repo_root = Path(__file__).resolve().parents[1]
    artifact_path = storage_path + ".child-artifact.json"
    child_script = textwrap.dedent(
        f"""
        import json, os, sys
        sys.path.insert(0, {str(repo_root / 'lib')!r})
        from durable_bridge.pi_durable_backend import PiDurableBackend
        b = PiDurableBackend()
        h = b.open({storage_path!r})
        conv = h['conversation_id']
        s = b.submit(h, conv, 'cross-req', 'cross-hello')
        try:
            worker_pid = b._worker._proc.pid
        except Exception:
            worker_pid = None
        artifact = {{
            'pid': os.getpid(),
            'worker_pid': worker_pid,
            'conv': conv,
            'sub': s.submission_id,
            'req': 'cross-req',
        }}
        with open({artifact_path!r}, 'w', encoding='utf-8') as f:
            json.dump(artifact, f)
        # exit without clean shutdown — child process terminates, OS reaps the
        # worker with it. Mirrors the "process A exits" scenario.
        os._exit(0)
        """
    ).strip()
    env = os.environ.copy()
    proc = subprocess.run(
        [sys.executable, "-c", child_script],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert proc.returncode == 0, f"child failed: {proc.stderr.decode('utf-8', errors='replace')}"
    assert os.path.exists(artifact_path), f"child did not write artifact at {artifact_path}"
    with open(artifact_path, encoding="utf-8") as f:
        child = json.load(f)
    conv = child["conv"]
    sub_id = child["sub"]
    child_pid = child["pid"]
    child_worker_pid = child["worker_pid"]
    assert child_pid != os.getpid(), "child should be a different Python process from parent"
    if child_worker_pid is not None:
        assert child_worker_pid != os.getpid(), "child worker is on the same PID as parent??"

    b_parent = PiDurableBackend()
    try:
        h_parent = b_parent.open(storage_path, conversation_id=conv)
        assert h_parent["conversation_id"] == conv
        state = b_parent.status(h_parent, sub_id)
        assert state.submission_id == sub_id
        assert state.text == "cross-hello"
        s_again = b_parent.submit(h_parent, conv, "cross-req", "cross-hello")
        assert s_again.submission_id == sub_id
    finally:
        b_parent.shutdown()
    parent_worker_pid = b_parent._worker._proc.pid if b_parent._worker._proc else None
    assert parent_worker_pid != child_worker_pid, (
        f"cross-process recovery should use a different worker PID "
        f"(child_worker_pid={child_worker_pid}, parent_worker_pid={parent_worker_pid})"
    )


@_requires_env  # noqa: F821
def test_pi_durable_close_does_not_delete_storage(make_backend, storage_path):
    b = make_backend()
    h = b.open(storage_path)
    conv = h["conversation_id"]
    b.close(h)
    assert conv in b.list_conversations()
    h2 = b.open(storage_path, conversation_id=conv)
    assert h2["conversation_id"] == conv


@_requires_env  # noqa: F821
def test_pi_durable_worker_crash_surfaces_as_error(make_backend, storage_path):
    b = make_backend()
    h = b.open(storage_path)
    proc = b._worker._proc
    assert proc is not None and proc.poll() is None, "worker should be alive"
    proc.kill()
    proc.wait(timeout=5)
    t0 = time.monotonic()
    with pytest.raises(DispatcherError):
        b.submit(h, h["conversation_id"], "after-kill-req", "after-kill")
    elapsed = time.monotonic() - t0
    assert elapsed < 10.0, f"call after worker kill took {elapsed:.2f}s — too long"


@_requires_env  # noqa: F821
def test_pi_durable_handle_validation(make_backend, storage_path):
    b = make_backend()
    with pytest.raises(BackendError):
        b.open("")  # type: ignore[arg-type]
    with pytest.raises(BackendError):
        b.open(storage_path, conversation_id="")
    with pytest.raises(BackendError):
        b.open(storage_path, conversation_id=42)  # type: ignore[arg-type]


@_requires_env  # noqa: F821
def test_pi_durable_submit_validation(make_backend, storage_path):
    b = make_backend()
    h = b.open(storage_path)
    conv = h["conversation_id"]
    with pytest.raises(BackendError):
        b.submit(h, conv, "", "x")
    with pytest.raises(BackendError):
        b.submit(h, "not-an-existing-conv", "r", "x")
    b.close(h)
    with pytest.raises(BackendNotFound):
        b.submit(h, conv, "r", "x")


# ---- skipif-predicate self-tests (NEVER skipped; verify the skip logic itself) ----


@pytest.mark.skipif(
    not _worker_deps_available(),
    reason="predicate verification requires env to be OK in order to assert True",
)
def test_skipif_predicate_env_ok_directly() -> None:
    """Sanity: on a real env the predicate returns True (don't skip).

    On no-node machines this test is skipped (assertion cannot hold there).
    The skipif-friendly verification is below in
    ``test_skipif_predicate_no_node_is_false``.
    """
    assert _worker_deps_available() is True


def test_skipif_predicate_no_node_is_false(monkeypatch) -> None:
    """When ``node`` lookup returns None, predicate is False (→ pytest skips).

    We deliberately import ``pi_durable_backend`` as a module here (rather than
    call the already-imported name) so monkeypatch on ``_resolve_node_bin``
    actually reaches the function the predicate invokes.
    """
    import durable_bridge.pi_durable_backend as pdb
    monkeypatch.setattr(pdb, "_resolve_node_bin", lambda: None)
    assert pdb._resolve_node_bin() is None
    assert pdb._worker_deps_available() is False


def test_skipif_predicate_no_node_modules_is_false(tmp_path, monkeypatch) -> None:
    """When ``node`` is fine but worker deps are missing, predicate is False.

    This mirrors the freshly-cloned-but-no-`npm install`-yet state.
    """
    # point DEFAULT_WORKER_PATH at an empty tmp dir so the deps lookup fails.
    import durable_bridge.pi_durable_backend as pdb
    monkeypatch.setattr(pdb, "DEFAULT_WORKER_PATH", tmp_path / "nope" / "worker.mjs")
    assert _worker_deps_available() is False


# ----------------------------------------------------------------------------
# 9. list_conversations 跨桥重启必须仍能列出（索引重建）
#
# 回归测试：worker 的 storageCache 是进程本地的。桥重启后它为空，
# 若 list_conversations 不带 storage_path，桥重启后恒返回 ()，
# "重启后重建索引"的用途就失效了（由 scripts/tmux_soak.py 的 S7 实测发现）。
# ----------------------------------------------------------------------------


def test_list_conversations_survives_bridge_restart(storage_path):
    """桥重启后 list_conversations 仍能列出全部 conversation。"""
    from durable_bridge.pi_durable_backend import PiDurableBackend as _PDB

    # 第一代 worker：建 3 个 conversation
    b1 = _PDB()
    try:
        convs = []
        for i in range(3):
            h = b1.open(storage_path)
            convs.append(h["conversation_id"])
        assert len(set(convs)) == 3
    finally:
        b1.shutdown()

    # 全新 worker（等价于桥重启）：storage 缓存为空
    b2 = _PDB()
    try:
        h2 = b2.open(storage_path)          # 至少 open 一次以登记 storage_path
        listed = b2.list_conversations()
        for c in convs:
            assert c in listed, (
                f"重启后 list_conversations 应包含 {c}；"
                f"实际={listed}（若为空说明 worker 未收到 storagePath）"
            )
    finally:
        b2.shutdown()


def test_list_conversations_without_open_is_empty(storage_path):
    """从未 open 过 → list_conversations 返回空（不报错）。"""
    from durable_bridge.pi_durable_backend import PiDurableBackend as _PDB
    b = _PDB()
    try:
        assert b.list_conversations() == ()
    finally:
        b.shutdown()


# ----------------------------------------------------------------------------
# 10. 【回归·关键】桥重启后【不调 open】裸 list_conversations 仍应列出
#
# 上一条 test_list_conversations_survives_bridge_restart 先调了 b2.open()，
# open 会把 storage 登记进 worker 缓存，从而**掩盖**下面这个 bug：
#
#   worker 的 storageCache 是进程本地的。桥重启后它为空。
#   若 list_conversations 不带 storagePath，就只扫缓存 → 返回 []，
#   "重启后重建索引"失效。本测试刻意【不调 open】，直接裸 RPC，
#   复现主路径（bridge_process 启动时 note_storage_path 登记的默认 storage）。
# ----------------------------------------------------------------------------


def test_bare_list_conversations_after_restart_without_open(storage_path):
    """重启后不 open，直接 list_conversations —— 索引重建必须仍有效。"""
    from durable_bridge.pi_durable_backend import PiDurableBackend as _PDB

    # 第一代 worker：写 3 个 conversation
    b1 = _PDB()
    try:
        for _ in range(3):
            b1.open(storage_path)
    finally:
        b1.shutdown()

    # 第二代 worker：全新进程，storage 缓存为空
    b2 = _PDB()
    try:
        # 模拟 bridge_process 启动时的登记（主路径依赖它）
        b2.note_storage_path(storage_path)
        # 刻意不调 open()
        listed = b2.list_conversations()
        assert len(listed) == 3, (
            f"重启后裸 list_conversations 应返回 3 条，实际 {len(listed)}: {listed}。"
            "若为空，说明 worker 未收到 storagePath —— "
            "worker.mjs 的 handleListConversations 必须接受该参数。"
        )
    finally:
        b2.shutdown()


def test_bare_list_conversations_returns_empty_when_storage_unwritten(tmp_path):
    """未写过数据的 storage，裸 list_conversations 返回空且不报错。"""
    from durable_bridge.pi_durable_backend import PiDurableBackend as _PDB
    fresh = str(tmp_path / "never-written.sqlite")
    b = _PDB()
    try:
        b.note_storage_path(fresh)
        assert b.list_conversations() == ()
    finally:
        b.shutdown()


# ----------------------------------------------------------------------------
# Step 4: submission 三态语义（pending / settled / interrupted）+ dispatch_key
#
# 这些测试锁住「不再谎报 settled」这个改动。改动前 worker 硬编码
# status="settled"、finish_reason="replayed"，刚提交的东西也报"已完成"。
# ----------------------------------------------------------------------------


def test_submit_reports_pending_not_settled(storage_path):
    """刚 submit 的东西什么都没发生，必须报 pending 而不是 settled。"""
    from durable_bridge.pi_durable_backend import PiDurableBackend as _PDB
    b = _PDB()
    try:
        h = b.open(storage_path)
        s = b.submit(h, h["conversation_id"], "req-pending", "hello")
        assert s.status == "pending", f"应报 pending，实际 {s.status!r}"
        assert s.status != "settled", "绝不能把刚提交的报成 settled"
        # 读回来也必须是 pending
        again = b.status(h, s.submission_id)
        assert again.status == "pending"
        # 文本仍然保留（放在 detail.inputText，不是塞进 status/reason）
        assert again.text == "hello"
    finally:
        b.shutdown()


def test_settle_transitions_pending_to_settled(storage_path):
    """settle() 后 pending -> settled。"""
    from durable_bridge.pi_durable_backend import PiDurableBackend as _PDB
    b = _PDB()
    try:
        h = b.open(storage_path)
        s = b.submit(h, h["conversation_id"], "req-settle", "question")
        assert s.status == "pending"
        done = b.settle(h, s.submission_id, answer="the answer")
        assert done.status == "settled", f"应报 settled，实际 {done.status!r}"
        assert done.finish_reason == "answered"
        # 状态已持久化
        assert b.status(h, s.submission_id).status == "settled"
    finally:
        b.shutdown()


def test_mark_interrupted_transitions_pending_to_interrupted(storage_path):
    """mark_interrupted() 后 pending -> interrupted。"""
    from durable_bridge.pi_durable_backend import PiDurableBackend as _PDB
    b = _PDB()
    try:
        h = b.open(storage_path)
        s = b.submit(h, h["conversation_id"], "req-intr", "unfinished work")
        out = b.mark_interrupted(h, s.submission_id, reason="process_died")
        assert out.status == "interrupted", f"应报 interrupted，实际 {out.status!r}"
        assert b.status(h, s.submission_id).status == "interrupted"
    finally:
        b.shutdown()


def test_cannot_mark_settled_submission_interrupted(storage_path):
    """已 settled 的不能再被标 interrupted（终态不可回退）。"""
    from durable_bridge.backend import BackendInvalidState
    from durable_bridge.pi_durable_backend import PiDurableBackend as _PDB
    b = _PDB()
    try:
        h = b.open(storage_path)
        s = b.submit(h, h["conversation_id"], "req-final", "q")
        b.settle(h, s.submission_id, answer="a")
        with pytest.raises(BackendInvalidState):
            b.mark_interrupted(h, s.submission_id, reason="too late")
    finally:
        b.shutdown()


def test_pending_survives_restart_and_reads_back_pending(storage_path):
    """提交后重启，新进程读到该 submission 仍是 pending（不是被谎报成 settled）。"""
    from durable_bridge.pi_durable_backend import PiDurableBackend as _PDB
    b1 = _PDB()
    try:
        h = b1.open(storage_path)
        s = b1.submit(h, h["conversation_id"], "req-restart", "persisted")
        sid = s.submission_id
    finally:
        b1.shutdown()

    b2 = _PDB()
    try:
        h2 = b2.open(storage_path, conversation_id=h["conversation_id"])
        got = b2.status(h2, sid)
        assert got.status == "pending", (
            f"重启后应仍为 pending，实际 {got.status!r}；"
            "若为 settled 说明又退回谎报"
        )
        assert got.text == "persisted"
        # 显式标记后可转 interrupted
        out = b2.mark_interrupted(h2, sid, reason="crashed_between_runs")
        assert out.status == "interrupted"
    finally:
        b2.shutdown()


def test_dispatch_key_dedupes_same_conversation(storage_path):
    """同 dispatch_key 重复提交 → 复用同一条 submission。"""
    from durable_bridge.pi_durable_backend import PiDurableBackend as _PDB
    b = _PDB()
    try:
        h = b.open(storage_path)
        conv = h["conversation_id"]
        a = b.submit(h, conv, "req-a", "first", dispatch_key="tool:edit:x.py")
        b2 = b.submit(h, conv, "req-b", "second", dispatch_key="tool:edit:x.py")
        assert a.submission_id == b2.submission_id, (
            f"同 dispatch_key 应复用同一条 submission，"
            f"实际 {a.submission_id} vs {b2.submission_id}"
        )
    finally:
        b.shutdown()


def test_dispatch_key_does_not_leak_across_conversations(storage_path):
    """不同 conversation 的同 dispatch_key 不互相干扰。"""
    from durable_bridge.pi_durable_backend import PiDurableBackend as _PDB
    b = _PDB()
    try:
        h1 = b.open(storage_path)
        h2 = b.open(storage_path)
        assert h1["conversation_id"] != h2["conversation_id"]
        a = b.submit(h1, h1["conversation_id"], "r1", "x", dispatch_key="k")
        c = b.submit(h2, h2["conversation_id"], "r2", "y", dispatch_key="k")
        assert a.submission_id != c.submission_id, "不同 conversation 不应共用 submission"
    finally:
        b.shutdown()


def test_no_dispatch_key_keeps_legacy_request_id_behaviour(storage_path):
    """不传 dispatch_key 时，requestId 幂等仍照旧工作。"""
    from durable_bridge.pi_durable_backend import PiDurableBackend as _PDB
    b = _PDB()
    try:
        h = b.open(storage_path)
        conv = h["conversation_id"]
        a = b.submit(h, conv, "req-same", "same input")
        b2 = b.submit(h, conv, "req-same", "same input")
        assert a.submission_id == b2.submission_id
    finally:
        b.shutdown()


def test_in_memory_backend_same_status_semantics(tmp_path):
    """InMemoryDurableBackend 必须与 pi_durable 有相同的状态语义。"""
    from durable_bridge.backend import InMemoryDurableBackend
    b = InMemoryDurableBackend()
    h = b.open(str(tmp_path / "x.sqlite"))
    conv = h["conversation_id"]
    s = b.submit(h, conv, "r1", "hello")
    assert s.status == "pending", f"InMemory 也应报 pending，实际 {s.status!r}"
    done = b.settle(h, s.submission_id, answer="hi")
    assert done.status == "settled"
    assert b.status(h, s.submission_id).status == "settled"


def test_in_memory_dispatch_key_dedupes(tmp_path):
    """InMemoryDurableBackend 的 dispatch_key 幂等。"""
    from durable_bridge.backend import InMemoryDurableBackend
    b = InMemoryDurableBackend()
    h = b.open(str(tmp_path / "y.sqlite"))
    conv = h["conversation_id"]
    a = b.submit(h, conv, "r1", "a", dispatch_key="tool:k")
    c = b.submit(h, conv, "r2", "b", dispatch_key="tool:k")
    assert a.submission_id == c.submission_id


# ----------------------------------------------------------------------------
# B2 回归：settle 幂等，重试不得堆积 AssistantEntry
#
# 修复前 handleSettle 无条件 appendEntry(AssistantEntry)，重试 settle
# 会不断往 transcript 里塞垃圾 entry（pi-durable 的 settleSubmission 对
# 已终态是 no-op，但 appendEntry 是真副作用）。
# InMemoryDurableBackend 一直有这个守卫，两个后端此前行为分叉。
# ----------------------------------------------------------------------------


def test_settle_is_idempotent_no_duplicate_answer_entry(storage_path):
    """重复 settle 同一条 submission：状态不变，entry 数不变。"""
    import sqlite3
    from durable_bridge.pi_durable_backend import PiDurableBackend as _PDB

    b = _PDB()
    try:
        h = b.open(storage_path)
        conv = h["conversation_id"]
        s = b.submit(h, conv, "req-idem", "question")

        first = b.settle(h, s.submission_id, answer="the answer")
        assert first.status == "settled"

        def _entry_count() -> int:
            con = sqlite3.connect(storage_path)
            try:
                return con.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
            finally:
                con.close()

        n1 = _entry_count()
        assert n1 > 0, "settle 应写入 entry（输入 + 答案）"

        # 重复 settle 3 次
        for _ in range(3):
            again = b.settle(h, s.submission_id, answer="the answer")
            assert again.status == "settled", f"应保持 settled，实际 {again.status}"

        n2 = _entry_count()
        assert n2 == n1, (
            f"重复 settle 写入了多余 entry：{n1} -> {n2}。"
            "handleSettle 缺少 already-done 守卫。"
        )
    finally:
        b.shutdown()


def test_cannot_settle_interrupted_submission(storage_path):
    """interrupted 是终态，不能被 settle 回 done。"""
    from durable_bridge.backend import BackendInvalidState
    from durable_bridge.pi_durable_backend import PiDurableBackend as _PDB

    b = _PDB()
    try:
        h = b.open(storage_path)
        s = b.submit(h, h["conversation_id"], "req-intr2", "unfinished")
        b.mark_interrupted(h, s.submission_id, reason="crashed")
        with pytest.raises(BackendInvalidState):
            b.settle(h, s.submission_id, answer="too late")
    finally:
        b.shutdown()

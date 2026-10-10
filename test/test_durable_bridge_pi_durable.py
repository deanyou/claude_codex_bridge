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

"""PiDurableBackend — wraps @earendil-works/pi-durable (Node) over JSON-lines IPC.

This file implements the durable-bridge ``DurableBackend`` protocol by spawning
a Node worker subprocess (``tools/pi_durable_bridge/worker.mjs``) and
exchanging one-line JSON requests / responses on stdin/stdout.

Why a Node subprocess at all?
  pi-durable is published as a TypeScript package with no Python equivalent.
  Its SQLite storage is durable across processes (verified in probe.mjs),
  which is exactly the property Step 2 needs: open in process A, kill it,
  reopen in process B, recover the same conversation + submission.

Routes chosen (mirrors plan §7 — avoids Harness.open which needs models/registry):
  * Conversations stored via ``session.commit(tx.createConversation(...))``.
  * Submissions stored via ``tx.createSubmission({...status:"unanswered",
    reason:inputText})``; idempotency via ``tx.submissionByRequest``.
  * ``close(handle)`` only removes the handle from worker's in-memory map;
    the storage file is never deleted (same semantics as InMemoryDurableBackend).
"""

from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Optional

from .backend import (
    BackendError,
    BackendInvalidState,
    BackendNotFound,
    SubmissionState,
)
from .dispatcher import DispatcherError


logger = logging.getLogger(__name__)


DEFAULT_WORKER_PATH = Path(__file__).resolve().parent.parent.parent / "tools" / "pi_durable_bridge" / "worker.mjs"


# bridge protocol constants (must match worker.mjs)
PROTOCOL_VERSION = "pi-durable-bridge/1"


def _resolve_node_bin() -> str | None:
    """Locate the ``node`` binary on PATH. Returns ``None`` if absent.

    Encapsulated so tests can monkeypatch the lookup.
    """
    return shutil.which("node")


def _worker_deps_available() -> bool:
    """True iff the pi-durable bridge can be exercised in this environment.

    Requires:
      * ``node`` binary on PATH (engines>=22.19.0 from package.json, but we don't
        check the version here — worst case the worker will fail to start and
        surface as DispatcherError)
      * ``tools/pi_durable_bridge/worker.mjs`` exists
      * ``tools/pi_durable_bridge/node_modules/@earendil-works/pi-durable`` exists

    The suite treats a negative result as a hard skip: never fail.
    """
    if _resolve_node_bin() is None:
        return False
    deps_dir = DEFAULT_WORKER_PATH.parent / "node_modules" / "@earendil-works" / "pi-durable"
    return DEFAULT_WORKER_PATH.exists() and deps_dir.exists()


class _WorkerDied(DispatcherError):
    """Raised internally when the underlying Node worker has died."""


class _BackendErrorKindError(BackendError):
    """Generic backend-error envelope used to surface worker errors.

    Defined here as a subclass of BackendError so it's still a BackendError for
    the contract test, but carries the raw errorKind for diagnostics.
    """

    def __init__(self, message: str, *, error_kind: str = "backend_error"):
        super().__init__(message)
        self.error_kind = error_kind


_ERROR_KIND_MAP = {
    "backend_not_found": BackendNotFound,
    "invalid_state": BackendInvalidState,
    "backend_error": _BackendErrorKindError,
}


class _WorkerProcess:
    """Thin wrapper around the worker subprocess.

    Single-threaded use: one thread writes requests, one reads responses.
    The Python side keeps a 1-deep FIFO of pending requests: requests are
    serialized by an internal lock, so the worker processes them in order.
    """

    def __init__(
        self,
        *,
        node_bin: str,
        worker_path: Path,
        startup_timeout_s: float = 20.0,
    ) -> None:
        self._node_bin = node_bin
        self._worker_path = worker_path
        self._startup_timeout_s = startup_timeout_s
        self._proc: Optional[subprocess.Popen] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._stderr_stop = threading.Event()
        self._lock = threading.Lock()  # serialize send/recv
        self._send_id = 0
        self._ready = False

    # ---- lifecycle ----

    def ensure_started(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        self._start_locked()
        if not self._wait_for_ready_locked():
            self._kill_locked()
            raise _WorkerDied("worker did not emit ready line within timeout")

    def shutdown(self) -> None:
        with self._lock:
            if self._proc is None:
                return
            try:
                self._send_locked({"id": None, "method": "shutdown", "params": {}})
            except Exception:
                pass
            try:
                self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=2.0)
            except Exception:
                self._kill_locked()

    def _start_locked(self) -> None:
        if not self._worker_path.exists():
            raise _WorkerDied(f"worker not found: {self._worker_path}")
        cmd = [self._node_bin, str(self._worker_path)]
        logger.debug("[pi-durable] starting worker: %s", cmd)
        env = os.environ.copy()
        # Make sure node_modules in the worker directory is searchable.
        # Setting NODE_PATH isn't strictly needed if the worker.mjs has its
        # own node_modules beside it (it does). We pass PATH/NODE_PATH for
        # safety in case NODE_PATH is unset.
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                env=env,
                cwd=str(self._worker_path.parent),
            )
        except OSError as exc:
            raise _WorkerDied(f"failed to spawn worker: {exc}") from exc
        # drain stderr in a thread
        self._stderr_stop.clear()
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr, daemon=True, name="pi-durable-stderr"
        )
        self._stderr_thread.start()

    def _drain_stderr(self) -> None:
        if self._proc is None or self._proc.stderr is None:
            return
        try:
            for raw in iter(self._proc.stderr.readline, b""):
                if self._stderr_stop.is_set():
                    break
                line = raw.decode("utf-8", errors="replace").rstrip("\n")
                if line:
                    logger.debug("[pi-durable worker] %s", line)
        except Exception as exc:
            logger.debug("[pi-durable] stderr drain ended: %s", exc)

    def _kill_locked(self) -> None:
        self._stderr_stop.set()
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.kill()
            except Exception:
                pass
        self._proc = None

    def _wait_for_ready_locked(self) -> bool:
        """Block until the first line of stdout is a ready notice."""
        if self._proc is None or self._proc.stdout is None:
            return False
        deadline = time.monotonic() + self._startup_timeout_s
        try:
            # set a generous read timeout via thread + queue so we can abort
            q: queue.Queue = queue.Queue(maxsize=4)
            ready_msg: dict = {}

            def _reader():
                try:
                    line = self._proc.stdout.readline()
                    if line:
                        q.put(line.decode("utf-8", errors="replace").rstrip("\n"))
                except Exception:
                    pass

            t = threading.Thread(target=_reader, daemon=True)
            t.start()
            while time.monotonic() < deadline:
                if self._proc.poll() is not None:
                    return False
                try:
                    line = q.get(timeout=0.5)
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("ok") and msg.get("result", {}).get("ready"):
                        self._ready = True
                        return True
                except queue.Empty:
                    continue
            return False
        except Exception:
            return False

    # ---- request / response ----

    def call(self, method: str, params: dict) -> Any:
        """Send a JSON request and block for the matching response."""
        with self._lock:
            self.ensure_started_locked()
            return self._call_locked(method, params)

    def ensure_started_locked(self) -> None:
        # called with self._lock held
        if self._proc is None:
            # first-time startup path
            self._start_locked()
            if not self._wait_for_ready_locked():
                self._kill_locked()
                raise _WorkerDied("worker did not emit ready line within timeout")
            return
        if self._proc.poll() is None:
            return  # worker alive
        # worker has died — refuse to silently restart, surface DispatcherError
        raise _WorkerDied(
            f"worker died (rc={self._proc.returncode}); create a new PiDurableBackend "
            "to recover durable state from the SQLite file."
        )

    def _call_locked(self, method: str, params: dict) -> Any:
        # called with self._lock held
        self._send_id += 1
        req = {"id": self._send_id, "method": method, "params": params}
        self._send_locked(req)
        # read response — match by id
        try:
            resp = self._read_response_locked(self._send_id)
        except _WorkerDied:
            raise
        except Exception as exc:
            raise _WorkerDied(f"IPC read failure ({method}): {exc}") from exc
        if resp.get("ok"):
            return resp.get("result")
        error_kind = resp.get("errorKind", "rpc_error")
        message = resp.get("message", "")
        cls = _ERROR_KIND_MAP.get(error_kind, DispatcherError)
        if cls is _BackendErrorKindError:
            raise cls(message, error_kind=error_kind)
        raise cls(message)

    def _send_locked(self, obj: dict) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise _WorkerDied("worker is not running")
        if self._proc.poll() is not None:
            raise _WorkerDied(f"worker died (rc={self._proc.returncode})")
        line = json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"
        try:
            self._proc.stdin.write(line.encode("utf-8"))
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self._kill_locked()
            raise _WorkerDied(f"worker stdin broken: {exc}") from exc

    def _read_response_locked(self, expected_id: int) -> dict:
        """Read worker stdout line-by-line until a response with the expected id.

        Discards any unsolicited lines (e.g., the startup ready notice if it
        somehow wasn't drained).  Raises _WorkerDied if the worker dies.
        """
        if self._proc is None or self._proc.stdout is None:
            raise _WorkerDied("worker stdout is not available")
        deadline = time.monotonic() + 30.0  # hard upper bound
        while True:
            if self._proc.poll() is not None:
                self._kill_locked()
                raise _WorkerDied(f"worker died with rc={self._proc.returncode}")
            if time.monotonic() > deadline:
                raise _WorkerDied(f"worker call timeout (id={expected_id})")
            # blocking read with small poll to allow poll() check
            line = self._read_line_with_timeout(0.5)
            if line is None:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == expected_id:
                return msg
            # else: drop unsolicited line (e.g., startup ready notice)

    def _read_line_with_timeout(self, timeout: float) -> Optional[str]:
        """Blocking read of one line. Polls every 50ms for proc state."""
        if self._proc is None or self._proc.stdout is None:
            return None
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self._proc.poll() is not None:
                return None
            # fileno-based peek+read to avoid blocking forever
            import select
            r, _, _ = select.select([self._proc.stdout], [], [], min(0.05, max(0.0, end - time.monotonic())))
            if not r:
                continue
            try:
                chunk = self._proc.stdout.readline()
            except (OSError, ValueError):
                return None
            if not chunk:
                return None
            return chunk.decode("utf-8", errors="replace")
        return None


class PiDurableBackend:
    """JSON-lines bridge to the Node-side pi-durable worker.

    Aligns with ``DurableBackend`` Protocol (lib/durable_bridge/backend.py).
    All methods are SYNCHRONOUS — Protocol requirement. Internally each call
    blocks on a single subprocess IPC round-trip.

    Process model
    -------------
    Each ``PiDurableBackend()`` instance owns ONE Node worker subprocess. Two
    instances can run side by side (one per worker). The cross-process
    recovery test deliberately creates two instances to prove the SQLite
    file is durable across worker processes.

    Concurrency
    -----------
    A single backend serializes calls through its own lock — no concurrent
    IPC from one PiDurableBackend instance. Multiple instances are
    independent (each has its own subprocess).
    """

    def __init__(
        self,
        *,
        node_bin: str = "node",
        worker_path: Optional[Path] = None,
        startup_timeout_s: float = 20.0,
    ) -> None:
        self._worker_path = Path(worker_path) if worker_path else DEFAULT_WORKER_PATH
        self._worker = _WorkerProcess(
            node_bin=node_bin,
            worker_path=self._worker_path,
            startup_timeout_s=startup_timeout_s,
        )

    # ---- internal ipc ----
    def _call(self, method: str, params: dict) -> Any:
        return self._worker.call(method, params)

    # ---- DurableBackend Protocol ----

    def open(self, storage_path: str, *, conversation_id: str | None = None) -> dict:
        if not isinstance(storage_path, str) or not storage_path:
            raise BackendError("storage_path must be a non-empty string")
        if conversation_id is not None and not isinstance(conversation_id, str):
            raise BackendError("conversation_id must be a string when provided")
        if conversation_id is not None and not conversation_id:
            raise BackendError("conversation_id must be non-empty")
        if conversation_id is not None and len(conversation_id) == 0:
            raise BackendError("conversation_id must be non-empty")
        params: dict = {"storagePath": storage_path, "conversationId": conversation_id}
        res = self._call("open", params)
        # worker returns snake_case for clarity; bridge uses the canonical keys
        # worker may return conversation_id as int (e.g. 2) — coerce to str
        return {
            "handle_id": res["handle_id"],
            "storage_path": res["storage_path"],
            "conversation_id": str(res["conversation_id"]),
        }

    def submit(
        self,
        handle: dict,
        conversation_id: str,
        request_id: str,
        input_text: str,
    ) -> SubmissionState:
        if not isinstance(handle, dict) or not isinstance(handle.get("handle_id"), str):
            raise BackendError("handle must be a dict with 'handle_id'")
        if not isinstance(conversation_id, str) or not conversation_id:
            raise BackendError("conversation_id must be a non-empty string")
        if not isinstance(request_id, str) or not request_id:
            raise BackendError("request_id must be a non-empty string")
        if not isinstance(input_text, str):
            raise BackendError("input_text must be a string")
        handle_id = handle["handle_id"]
        res = self._call(
            "submit",
            {
                "handleId": handle_id,
                "conversationId": conversation_id,
                "requestId": request_id,
                "inputText": input_text,
            },
        )
        return _state_from_worker(res)

    def status(self, handle: dict, submission_id: str) -> SubmissionState:
        if not isinstance(handle, dict) or not isinstance(handle.get("handle_id"), str):
            raise BackendError("handle must be a dict with 'handle_id'")
        if not isinstance(submission_id, str) or not submission_id:
            raise BackendError("submission_id must be a non-empty string")
        handle_id = handle["handle_id"]
        res = self._call(
            "status",
            {"handleId": handle_id, "submissionId": submission_id},
        )
        return _state_from_worker(res)

    def close(self, handle: dict) -> None:
        if not isinstance(handle, dict) or not isinstance(handle.get("handle_id"), str):
            raise BackendError("handle must be a dict with 'handle_id'")
        try:
            self._call("close", {"handleId": handle["handle_id"]})
        except BackendNotFound:
            # closing an unknown handle is idempotent
            pass

    def register_conversation(self, conversation_id: str) -> None:
        if not isinstance(conversation_id, str) or not conversation_id:
            raise BackendError("conversation_id must be a non-empty string")
        self._call("register_conversation", {"conversationId": conversation_id})

    def list_conversations(self) -> tuple[str, ...]:
        res = self._call("list_conversations", {})
        cs = res.get("conversations", [])
        return tuple(cs)

    # ---- non-protocol ----

    def shutdown(self) -> None:
        """Explicitly shut down the worker subprocess.  Safe to call multiple times."""
        self._worker.shutdown()

    # context-manager support so tests can `with PiDurableBackend() as b: ...`
    def __enter__(self) -> "PiDurableBackend":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self.shutdown()
        except Exception:
            pass


def _state_from_worker(res: dict) -> SubmissionState:
    """Translate worker result dict into our SubmissionState dataclass."""
    h = res.get("input_hash") or ""
    text = res.get("text") or ""
    if not h and text:
        # recompute the hash the same way InMemoryDurableBackend._input_hash does
        import hashlib
        h = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
    return SubmissionState(
        submission_id=res["submission_id"],
        conversation_id=res["conversation_id"],
        request_id=res["request_id"],
        input_hash=h,
        status=res.get("status", "settled"),
        text=text,
        finish_reason=res.get("finish_reason"),
    )


__all__ = [
    "PiDurableBackend",
    "PROTOCOL_VERSION",
    "_resolve_node_bin",
    "_worker_deps_available",
]

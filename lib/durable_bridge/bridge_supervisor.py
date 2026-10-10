"""daemon 侧桥进程 supervisor（Step 3′）。

职责：
- 启动一个独立 Python 子进程承载 BridgeServer（bridge_process.py）
- 等 BRIDGE_READY 行出现后再返回真实 endpoint（**绝不靠猜时间**）
- 失败一律抛 BridgeSupervisorError，**绝不 fallback 到 make_endpoint() 占位**
- stop()：SIGTERM → 等确认退出 → 超时 SIGKILL，幂等
- 5 条错误路径每条可观测：
  1. node / npm 缺失：桥非 0 退出 + stderr 提 node → 抛错含 stderr
  2. 锁被占：桥非 0 退出 + stderr 提"storage_lock_busy" → 抛错明确区分"锁"
  3. 桥启动后立刻崩（无 BRIDGE_READY）：超时 → 抛错含 stderr
  4. endpoint.json 一直不出现：同 3
  5. stop() 时桥不响应 SIGTERM：等 shutdown_timeout_s → SIGKILL → 等退出

设计要点：
- 用 subprocess.Popen + BUFSIZE=1 行缓冲 + text=True，逐行读 stdout/stderr
- 把 stderr 累积到 buffer，start() 失败时一起塞进异常消息
- stop() 不可重入：内部用 threading.Lock + is_stopped 标志
"""

from __future__ import annotations

import logging
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import IO, Optional

from .endpoint import BridgeEndpoint


_log = logging.getLogger("durable_bridge.bridge_supervisor")


class BridgeSupervisorError(RuntimeError):
    """supervisor 启动 / 监管桥进程失败。"""


def _parse_ready_line(line: str) -> BridgeEndpoint:
    """解析 ``BRIDGE_READY {...}`` 行。失败抛 BridgeSupervisorError。"""
    line = line.rstrip("\n").rstrip("\r")
    if not line.startswith("BRIDGE_READY "):
        raise BridgeSupervisorError(
            f"unexpected stdout line (missing BRIDGE_READY prefix): {line!r}"
        )
    import json
    try:
        payload = json.loads(line[len("BRIDGE_READY "):])
    except json.JSONDecodeError as exc:
        raise BridgeSupervisorError(
            f"BRIDGE_READY payload not valid JSON: {exc}; line={line!r}"
        ) from exc
    required = {"host", "port", "pid", "bridge_epoch", "protocol_version"}
    missing = required - set(payload.keys())
    if missing:
        raise BridgeSupervisorError(
            f"BRIDGE_READY payload missing fields: {sorted(missing)}; got={payload!r}"
        )
    return BridgeEndpoint(
        host=str(payload["host"]),
        port=int(payload["port"]),
        pid=int(payload["pid"]),
        bridge_epoch=str(payload["bridge_epoch"]),
        protocol_version=int(payload["protocol_version"]),
        # token 由 endpoint.json 后续读出来填入；BRIDGE_READY 不携带（不外泄）
        token="",
    )




def _classify_startup_failure(*, exit_code: int, stderr_text: str) -> str:
    """根据退出码 + stderr 把启动失败分类成可识别的提示前缀。

    返回的字符串以 ``reason=`` 开头，便于上层做断言 / 上报。
    """
    head = stderr_text.lower() if stderr_text else ""
    if exit_code == 3 or "storage_lock_busy" in head or "bridgestoragelockbusy" in head:
        return (
            "reason=storage_lock_busy 锁被占（旧桥仍持有 storage lock），"
            "refusing to start a second bridge (fail-closed)"
        )
    if exit_code == 2 or "backend_init_failed" in head:
        if "node" in head:
            return (
                "reason=node_missing pi_durable backend 要求 node / npm 依赖，"
                "当前环境缺失"
            )
        return "reason=backend_init_failed backend 构造失败"
    if exit_code == 4:
        return "reason=start_failed BridgeServer.start() 抛了未预期异常"
    if exit_code == 5:
        return "reason=ready_emit_failed BRIDGE_READY 行写不出"
    return "reason=unknown"


class BridgeSupervisor:
    """监管一个桥进程实例。"""

    def __init__(
        self,
        *,
        python_bin: Optional[str] = None,
        startup_timeout_s: float = 20.0,
        shutdown_timeout_s: float = 10.0,
        log: Optional[logging.Logger] = None,
    ) -> None:
        self._python_bin = python_bin or sys.executable
        self._startup_timeout_s = float(startup_timeout_s)
        self._shutdown_timeout_s = float(shutdown_timeout_s)
        self._log = log or _log
        self._proc: Optional[subprocess.Popen] = None
        self._endpoint: Optional[BridgeEndpoint] = None
        self._endpoint_path: Optional[Path] = None
        # 累积 stderr 行，错误路径诊断用
        self._stderr_buffer: list[str] = []
        self._stderr_lock = threading.Lock()
        self._stopped = False
        self._stop_lock = threading.Lock()
        # 后台线程把 stderr 持续累积进 buffer
        self._stderr_thread: Optional[threading.Thread] = None

    # ---------------- properties ----------------

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @property
    def endpoint(self) -> Optional[BridgeEndpoint]:
        return self._endpoint

    @property
    def endpoint_path(self) -> Optional[Path]:
        return self._endpoint_path

    @property
    def pid(self) -> Optional[int]:
        return self._proc.pid if self._proc is not None else None

    # ---------------- stderr capture ----------------

    def _stderr_pump(self, stream: IO[str]) -> None:
        """持续读 stderr，写进 buffer；同时按行透传到 logging。"""
        try:
            for raw in stream:
                line = raw.rstrip("\n").rstrip("\r")
                with self._stderr_lock:
                    # 保留最近 ~200 行，避免 buffer 失控
                    if len(self._stderr_buffer) >= 400:
                        del self._stderr_buffer[:200]
                    self._stderr_buffer.append(line)
                if line:
                    self._log.warning("bridge stderr: %s", line)
        except (ValueError, OSError):
            # 流关闭或解码异常 → 退出
            pass

    def _snapshot_stderr(self) -> str:
        with self._stderr_lock:
            return "\n".join(self._stderr_buffer)

    # ---------------- subprocess env ----------------

    def _build_subprocess_env(self) -> dict:
        """构造桥子进程环境变量。

        关键点：把 ``durable_bridge`` 所在目录加进 PYTHONPATH。
        桥子进程要 ``import durable_bridge.bridge_process``（即调用方本身），
        如果 PYTHONPATH 不包含 lib，子进程找不到模块就直接 ModuleNotFoundError。
        """
        env = dict(os.environ)
        # 找出 durable_bridge 包所在目录（=lib/）
        pkg_root = Path(__file__).resolve().parent.parent  # lib/durable_bridge/.. → lib
        existing = env.get("PYTHONPATH", "")
        parts = [str(pkg_root)]
        if existing:
            parts.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(parts)
        return env

    # ---------------- start ----------------

    def start(
        self,
        *,
        storage_path: Path,
        endpoint_path: Path,
        backend: str = "pi_durable",
        ignore_sigterm: bool = False,
    ) -> BridgeEndpoint:
        """起桥、等就绪、返回真实 endpoint。失败抛 BridgeSupervisorError。

        必须满足：返回的 endpoint ``port != 0``，且 endpoint.json 真实落盘。

        ignore_sigterm=True：让桥进程不响应 SIGTERM（用于 supervisor 的
        SIGKILL 路径测试）。生产不应使用。
        """
        if self._proc is not None:
            raise BridgeSupervisorError("supervisor already has a running bridge")
        storage_path = Path(storage_path).expanduser().resolve()
        endpoint_path = Path(endpoint_path).expanduser().resolve()
        endpoint_path.parent.mkdir(parents=True, exist_ok=True)
        # 防御：endpoint.json 已存在（上次没清理）也不阻塞启动；
        # 桥进程启动时会原子覆盖。

        argv = [
            self._python_bin,
            "-m",
            "durable_bridge.bridge_process",
            "--storage-path",
            str(storage_path),
            "--endpoint-path",
            str(endpoint_path),
            "--backend",
            backend,
        ]
        if ignore_sigterm:
            argv.append("--ignore-sigterm")
        self._log.info(
            "starting bridge subprocess: argv=%s cwd=%s",
            " ".join(shlex.quote(a) for a in argv),
            os.getcwd(),
        )
        try:
            env = self._build_subprocess_env()
            popen_kwargs = dict(
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                bufsize=1,
                text=True,
                env=env,
                # start_new_session：让 supervisor 可以 SIGTERM 整组；SIGKILL 也走进程组
                start_new_session=True,
            )
            proc = subprocess.Popen(argv, **popen_kwargs)
        except OSError as exc:
            raise BridgeSupervisorError(
                f"failed to spawn bridge subprocess: {exc!r}"
            ) from exc

        self._proc = proc
        self._endpoint_path = endpoint_path

        # stderr 泵到后台线程
        assert proc.stderr is not None
        self._stderr_thread = threading.Thread(
            target=self._stderr_pump,
            args=(proc.stderr,),
            name="bridge-stderr-pump",
            daemon=True,
        )
        self._stderr_thread.start()

        # 等 BRIDGE_READY
        deadline = time.monotonic() + self._startup_timeout_s
        assert proc.stdout is not None
        while True:
            if time.monotonic() > deadline:
                self._terminate_and_reap(proc, reason="startup_timeout")
                stderr_text = self._snapshot_stderr()
                raise BridgeSupervisorError(
                    f"bridge did not emit BRIDGE_READY within "
                    f"{self._startup_timeout_s}s; stderr:\n{stderr_text or '<empty>'}"
                )
            poll = proc.poll()
            if poll is not None:
                # 进程已退出（通常非 0）：构造带 stderr 的诊断
                # 等泵线程把剩余 stderr 收完
                self._stderr_thread.join(timeout=1.0)
                stderr_text = self._snapshot_stderr()
                self._proc = None
                # 分类：区分"锁忙"与其它启动失败
                classified = _classify_startup_failure(
                    exit_code=poll, stderr_text=stderr_text,
                )
                raise BridgeSupervisorError(
                    f"bridge subprocess exited during startup "
                    f"(code={poll}, backend={backend}); {classified}; "
                    f"stderr:\n{stderr_text or '<empty>'}"
                )
            # 用 poll + 短 sleep 而不是阻塞 readline：留出窗口给 poll()
            # 检查进程死亡 + 收集 stdout
            line = self._readline_with_timeout(proc.stdout, timeout_s=0.2)
            if line is None:
                continue
            stripped = line.rstrip("\n").rstrip("\r")
            if not stripped:
                continue
            if stripped.startswith("BRIDGE_READY "):
                try:
                    ep = _parse_ready_line(stripped)
                except BridgeSupervisorError:
                    # 协议错 = 立即停
                    self._terminate_and_reap(proc, reason="bad_ready_line")
                    raise
                # 等待 endpoint.json 落盘（桥内 publish_endpoint 是同步的，
                # 但我们仍读一次确认 port 已经写进去）
                if not self._wait_for_endpoint_file(endpoint_path):
                    self._terminate_and_reap(proc, reason="endpoint_file_missing")
                    raise BridgeSupervisorError(
                        f"BRIDGE_READY received but endpoint.json never appeared at "
                        f"{endpoint_path}; stderr:\n{self._snapshot_stderr() or '<empty>'}"
                    )
                # 从 endpoint.json 读出含 token 的完整 endpoint
                from .endpoint import read_endpoint
                full = read_endpoint(endpoint_path)
                if full is None:
                    self._terminate_and_reap(proc, reason="endpoint_file_unreadable")
                    raise BridgeSupervisorError(
                        f"endpoint.json at {endpoint_path} could not be parsed; "
                        f"stderr:\n{self._snapshot_stderr() or '<empty>'}"
                    )
                if full.port == 0:
                    self._terminate_and_reap(proc, reason="endpoint_port_zero")
                    raise BridgeSupervisorError(
                        f"endpoint.json port is 0 (placeholder); refusing to advertise "
                        f"a non-listening bridge; stderr:\n{self._snapshot_stderr() or '<empty>'}"
                    )
                self._endpoint = full
                self._log.info(
                    "bridge ready: host=%s port=%d pid=%d epoch=%s",
                    full.host, full.port, full.pid, full.bridge_epoch,
                )
                return full
            # 非 BRIDGE_READY 行（异常 stdout）：继续等，但记下来
            self._log.warning("unexpected bridge stdout line: %r", stripped)

        # unreachable
        raise BridgeSupervisorError("unreachable: start() loop exited unexpectedly")

    @staticmethod
    def _readline_with_timeout(stream: IO[str], *, timeout_s: float) -> Optional[str]:
        """非阻塞读一行：到时间还没数据返回 None。"""
        # Python 没有真正的非阻塞 readline；这里用 select 检查可读性
        import select
        fd = stream.fileno()
        ready, _, _ = select.select([fd], [], [], timeout_s)
        if not ready:
            return None
        return stream.readline()

    def _wait_for_endpoint_file(self, path: Path, *, timeout_s: float = 2.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if path.exists():
                return True
            time.sleep(0.05)
        return path.exists()

    # ---------------- stop ----------------

    def stop(self) -> None:
        """SIGTERM → 等确认退出 → 超时 SIGKILL。幂等。"""
        with self._stop_lock:
            if self._stopped:
                return
            self._stopped = True
            proc = self._proc
            if proc is None:
                return
            if proc.poll() is not None:
                # 已经退了
                self._proc = None
                return
            try:
                # 优先 SIGTERM 整组（start_new_session=True），让 worker.mjs 也退
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    # 进程组已不存在，fall back 到直接 SIGTERM
                    proc.terminate()
            except ProcessLookupError:
                self._proc = None
                return
            except Exception as exc:  # noqa: BLE001
                self._log.warning("terminate failed: %r; escalating to SIGKILL", exc)
                self._kill_now(proc)
                self._reap(proc)
                self._proc = None
                return

            # 等确认退出
            deadline = time.monotonic() + self._shutdown_timeout_s
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    self._proc = None
                    return
                time.sleep(0.05)

            # 超时未退：SIGKILL
            self._log.warning(
                "bridge did not exit within %ss after SIGTERM; sending SIGKILL",
                self._shutdown_timeout_s,
            )
            self._kill_now(proc)
            self._reap(proc)
            self._proc = None

    @staticmethod
    def _kill_now(proc: subprocess.Popen) -> None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
        try:
            proc.kill()
        except (OSError, ProcessLookupError):
            pass

    @staticmethod
    def _reap(proc: subprocess.Popen) -> None:
        try:
            proc.wait(timeout=5.0)
        except (subprocess.TimeoutExpired, OSError):
            pass

    def _terminate_and_reap(self, proc: subprocess.Popen, *, reason: str) -> None:
        """诊断路径上用的硬终止：SIGKILL 后等退出，不抛。"""
        self._log.warning("bridge subprocess terminated by supervisor: reason=%s", reason)
        self._kill_now(proc)
        self._reap(proc)
        if self._proc is proc:
            self._proc = None

    # ---------------- context manager ----------------

    def __enter__(self) -> "BridgeSupervisor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()


__all__ = ["BridgeSupervisor", "BridgeSupervisorError"]

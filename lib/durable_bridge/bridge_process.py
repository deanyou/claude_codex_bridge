"""常驻桥进程入口（Step 3′）。

可独立执行：
    python3 -m durable_bridge.bridge_process \
        --storage-path /path/to/storage.sqlite \
        --endpoint-path /path/to/endpoint.json \
        [--backend {pi_durable,in_memory}]

行为（与提案 fail-closed 对齐）：
1. 解析 backend；pi_durable 但 node / 依赖缺失 → stderr + 非 0 退出
2. BridgeServer.start()：拿锁失败（BridgeStorageLockBusy）→ stderr + 非 0 退出
3. 成功后打印 ``BRIDGE_READY host=... port=... pid=... epoch=...`` 到 stdout 并 flush
   （supervisor 用这行做就绪判定，绝不靠猜时间）
4. 阻塞等 SIGTERM；收到后 shutdown()，0 退出

绝不静默降级。任何失败一律 stderr 可诊断原因 + 非 0 退出码。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from pathlib import Path
from typing import Any

from .bridge import BridgeServer
from .exceptions import BridgeStorageLockBusy


_log = logging.getLogger("durable_bridge.bridge_process")


def _build_backend(backend_name: str) -> Any:
    """按名字构造 backend；缺失依赖立即抛异常。"""
    if backend_name == "in_memory":
        from .backend import InMemoryDurableBackend
        return InMemoryDurableBackend()
    if backend_name == "pi_durable":
        # 延迟 import：node 缺失时 import 阶段不应崩
        try:
            from .pi_durable_backend import PiDurableBackend
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"pi_durable backend unavailable (import failed: {exc!r})"
            ) from exc
        # 校验 node + npm 依赖：缺失立刻报，**绝不**静默降级到 in_memory
        from .pi_durable_backend import (
            _resolve_node_bin,
            _worker_deps_available,
            DEFAULT_WORKER_PATH,
        )
        node_bin = _resolve_node_bin()
        if node_bin is None:
            raise RuntimeError(
                "node binary not found on PATH; cannot start pi_durable backend "
                "(refusing to fall back to in_memory: durable storage would be lost)"
            )
        if not _worker_deps_available():
            raise RuntimeError(
                f"pi_durable worker not ready: expected {DEFAULT_WORKER_PATH} and "
                f"node_modules/@earendil-works/pi-durable; refusing to fall back"
            )
        return PiDurableBackend()
    raise ValueError(f"unknown backend: {backend_name!r}")


def _emit_ready_line(endpoint: Any) -> None:
    """打印 BRIDGE_READY 行（stdout，flush），supervisor 据此判定就绪。"""
    payload = {
        "host": endpoint.host,
        "port": int(endpoint.port),
        "pid": int(endpoint.pid),
        "bridge_epoch": endpoint.bridge_epoch,
        "protocol_version": int(endpoint.protocol_version),
    }
    line = "BRIDGE_READY " + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _emit_diag(prefix: str, message: str) -> None:
    """诊断信息走 stderr，便于 supervisor 捕获并上抛。"""
    sys.stderr.write(f"[bridge_process] {prefix}: {message}\n")
    sys.stderr.flush()


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="durable_bridge.bridge_process",
        description="常驻 durable-bridge 桥进程入口（Step 3′）",
    )
    parser.add_argument(
        "--storage-path",
        required=True,
        type=Path,
        help="桥独占的 durable storage 文件路径（不存在则创建）",
    )
    parser.add_argument(
        "--endpoint-path",
        required=True,
        type=Path,
        help="原子发布的 endpoint.json 路径",
    )
    parser.add_argument(
        "--backend",
        default="pi_durable",
        choices=("pi_durable", "in_memory"),
        help="backend 类型；默认 pi_durable；in_memory 用于本地链路验证",
    )
    parser.add_argument(
        "--ignore-sigterm",
        action="store_true",
        help=(
            "桥进程忽略 SIGTERM（不装优雅关闭 handler）。"
            "用于诊断 / supervisor SIGKILL 路径测试；生产不应使用。"
        ),
    )
    return parser.parse_args(argv)


def main(argv=None):
    """桥进程入口；返回进程退出码。"""
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    storage_path = Path(args.storage_path).expanduser().resolve()
    endpoint_path = Path(args.endpoint_path).expanduser().resolve()

    # 1. backend 构造：缺失依赖立即非 0 退出（绝不静默）
    try:
        backend = _build_backend(args.backend)
    except Exception as exc:  # noqa: BLE001
        _emit_diag(
            "backend_init_failed",
            f"backend={args.backend} storage={storage_path} error={exc!r}",
        )
        _emit_diag("traceback", traceback.format_exc())
        return 2

    # 2. 构造 server 并启动（拿锁失败非 0 退出）
    server = BridgeServer(
        storage_path=storage_path,
        backend=backend,
        endpoint_path=endpoint_path,
    )
    try:
        endpoint = server.start()
    except BridgeStorageLockBusy as exc:
        _emit_diag(
            "storage_lock_busy",
            f"another bridge already holds storage lock at {storage_path}: {exc!r}",
        )
        return 3
    except Exception as exc:  # noqa: BLE001
        _emit_diag(
            "start_failed",
            f"storage={storage_path} endpoint={endpoint_path} error={exc!r}",
        )
        _emit_diag("traceback", traceback.format_exc())
        return 4

    # 3. 安装 SIGTERM handler 并打印就绪行
    if args.ignore_sigterm:
        # 测试 / 诊断用：明确不装优雅关闭 handler，让 SIGTERM 不响应。
        # 这样上层 supervisor 必须走 SIGKILL 路径才能回收。
        try:
            import signal as _sig
            _sig.signal(_sig.SIGTERM, _sig.SIG_IGN)
        except (ValueError, OSError):
            pass
    else:
        server.install_signal_handlers()
    try:
        _emit_ready_line(endpoint)
    except Exception as exc:  # noqa: BLE001
        _emit_diag("ready_emit_failed", repr(exc))
        # 就绪行写不出 = supervisor 永远等不到 → 立刻关
        try:
            server.shutdown()
        except Exception:  # noqa: BLE001
            pass
        return 5

    # 4. 阻塞等 SIGTERM；timeout=None 让进程跑下去直到 shutdown
    server.wait_for_shutdown(timeout_s=None)

    # 5. 优雅退出
    try:
        server.shutdown()
    except Exception as exc:  # noqa: BLE001
        _emit_diag("shutdown_warning", repr(exc))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

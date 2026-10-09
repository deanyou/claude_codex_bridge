#!/usr/bin/env python3
"""Standalone BridgeServer harness for tmux live testing.

启动一个 BridgeServer（InMemoryDurableBackend + 真实 TCP loopback），
写到 /private/tmp/durable-bridge-test/ 目录。接收 SIGTERM 优雅停止。
"""
from __future__ import annotations

import logging
import signal
import sys
import time
from pathlib import Path

_LIB_ROOT = Path(__file__).resolve().parents[1] / 'lib'
if str(_LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LIB_ROOT))

from durable_bridge.backend import InMemoryDurableBackend
from durable_bridge.bridge import BridgeServer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [bridge] %(levelname)s %(message)s',
)
log = logging.getLogger('tmux-bridge')


def main():
    storage_dir = Path('/private/tmp/durable-bridge-test')
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / 'durable.sqlite'

    log.info('starting BridgeServer at %s', storage_path)

    backend = InMemoryDurableBackend()
    server = BridgeServer(
        storage_path=storage_path,
        backend=backend,
        endpoint_path=storage_dir / 'durable-bridge.endpoint.json',
    )
    server.install_signal_handlers()
    endpoint = server.start()

    log.info('bridge started: %s:%d (pid=%d, bridge_epoch=%s)',
             endpoint.host, endpoint.port, endpoint.pid, endpoint.bridge_epoch[:8])
    log.info('endpoint file: %s', server.endpoint_path)
    log.info('waiting for SIGTERM...')

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        log.info('SIGINT received, shutting down')
    finally:
        server.shutdown()
        log.info('bridge stopped')


if __name__ == '__main__':
    main()

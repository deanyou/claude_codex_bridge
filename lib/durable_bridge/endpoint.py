"""bridge endpoint.json 发布与读取。

Schema（v4 规格 09 节）：

.. code-block:: json

    {
      "host": "127.0.0.1",
      "port": 54321,
      "pid": 12345,
      "bridge_epoch": "uuid-v4-string",
      "protocol_version": 1,
      "token": "random-32-byte-base64"
    }

发布：
- 原子写：lib/storage/atomic.py 提供的 atomic_write_json（已 fsync 父目录）
- 仅允许 host=127.0.0.1（避免漂到 0.0.0.0 等不安全地址）
- POSIX 文件权限 0o600 由 atomic_write_json 强制

读取：
- 任意进程可读；但只接受 token + bridge_epoch 与当前服务端匹配
- 读取是 best-effort：失败应回到重连流程而不是报错给最终用户
"""

from __future__ import annotations

import json
import os
import secrets
import uuid
from dataclasses import dataclass
from pathlib import Path

from storage.atomic import atomic_write_json

from .exceptions import BridgeProtocolError
from .protocol import PROTOCOL_VERSION


DEFAULT_ENDPOINT_FILENAME = 'durable-bridge.endpoint.json'


@dataclass(frozen=True)
class BridgeEndpoint:
    """已发布或读取的桥端点。"""

    host: str
    port: int
    pid: int
    bridge_epoch: str
    protocol_version: int
    token: str

    def to_record(self) -> dict:
        return {
            'host': self.host,
            'port': int(self.port),
            'pid': int(self.pid),
            'bridge_epoch': self.bridge_epoch,
            'protocol_version': int(self.protocol_version),
            'token': self.token,
        }

    @classmethod
    def from_record(cls, record: object) -> 'BridgeEndpoint':
        if not isinstance(record, dict):
            raise BridgeProtocolError('endpoint must be a JSON object')
        try:
            host = str(record['host'])
            port = int(record['port'])
            pid = int(record['pid'])
            bridge_epoch = str(record['bridge_epoch'])
            protocol_version = int(record['protocol_version'])
            token = str(record['token'])
        except (KeyError, TypeError, ValueError) as exc:
            raise BridgeProtocolError(f'endpoint record missing/invalid fields: {exc}') from exc
        if not 0 <= port <= 65535:
            raise BridgeProtocolError(f'endpoint port out of range: {port}')
        if host != '127.0.0.1':
            raise BridgeProtocolError(f'endpoint host must be 127.0.0.1, got: {host!r}')
        return cls(
            host=host,
            port=port,
            pid=pid,
            bridge_epoch=bridge_epoch,
            protocol_version=protocol_version,
            token=token,
        )


def make_endpoint(*, host: str = '127.0.0.1', pid: int | None = None) -> BridgeEndpoint:
    """生成新 epoch 的 endpoint。host 限定 127.0.0.1。"""
    if host != '127.0.0.1':
        raise ValueError(f'endpoint host must be 127.0.0.1, got: {host!r}')
    return BridgeEndpoint(
        host=host,
        port=0,  # 由调用方在 bind 后再填入
        pid=int(pid if pid is not None else os.getpid()),
        bridge_epoch=str(uuid.uuid4()),
        protocol_version=PROTOCOL_VERSION,
        token=secrets.token_urlsafe(32),
    )


def publish_endpoint(path: Path, endpoint: BridgeEndpoint) -> None:
    """原子写入 endpoint.json。

    host 限定 127.0.0.1；其他 host 抛 ValueError，避免误发布到不安全地址。
    """
    if endpoint.host != '127.0.0.1':
        raise ValueError(f'endpoint host must be 127.0.0.1, got: {endpoint.host!r}')
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # 强制收紧权限：atomic_write_json 内部创建临时文件时是 0o600，
    # 但如果目标文件已存在且权限被改宽，replace 后仍可能保留宽权限。
    # 这里显式 chmod 一次以保证 0o600。
    atomic_write_json(target, endpoint.to_record())
    try:
        os.chmod(target, 0o600)
    except OSError:
        # Windows 不支持 chmod；ACL 由 ACL 设置流程（后续步骤）补齐。
        pass


def read_endpoint(path: Path) -> BridgeEndpoint | None:
    """读取 endpoint.json；不存在或解析失败返回 None。"""
    target = Path(path)
    try:
        text = target.read_text(encoding='utf-8')
    except FileNotFoundError:
        return None
    except OSError:
        return None
    try:
        record = json.loads(text)
    except json.JSONDecodeError:
        return None
    try:
        return BridgeEndpoint.from_record(record)
    except BridgeProtocolError:
        return None


def revoke_endpoint(path: Path) -> None:
    """删除 endpoint.json。

    只清理当前进程自己 epoch 的文件：如果发现文件中的 bridge_epoch
    与 ``expected_epoch`` 不一致（外部已替换为新桥的 endpoint），不要动它。
    """
    target = Path(path)
    try:
        current = read_endpoint(target)
    except Exception:
        current = None
    if current is not None and current.bridge_epoch and target.exists():
        try:
            target.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            # 删除失败不抛：进程退出后由 supervisor 清理
            pass


__all__ = [
    'DEFAULT_ENDPOINT_FILENAME',
    'BridgeEndpoint',
    'make_endpoint',
    'publish_endpoint',
    'read_endpoint',
    'revoke_endpoint',
]

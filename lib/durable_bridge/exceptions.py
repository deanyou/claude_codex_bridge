"""durable-bridge 异常类型。

按失败语义分层：
- DurableBridgeError: 全部异常的根
- 协议层：BridgeProtocolError（帧格式/JSON 解析）, BridgeOversizedFrame（超长帧）
- 鉴权层：BridgeAuthError（token 错）, BridgeEpochMismatch（epoch 错）
- 资源层：BridgeStorageLockBusy（锁被他人持有）, BridgeBusyError（资源不足）
"""

from __future__ import annotations


class DurableBridgeError(Exception):
    """所有 durable-bridge 异常的根。"""


class BridgeProtocolError(DurableBridgeError):
    """帧格式或 JSON 解析失败。

    协议层错误视为不可重试：客户端连接应被关闭而不是无限重试。
    """


class BridgeOversizedFrame(DurableBridgeError):
    """单帧超过配置上限。

    实现层防御：恶意或异常客户端不应能拉爆内存。
    """


class BridgeAuthError(DurableBridgeError):
    """token 鉴权失败。"""


class BridgeEpochMismatch(DurableBridgeError):
    """bridge_epoch 与服务端当前 epoch 不一致。

    服务端每次重启或主动让出会换 epoch，客户端拿到旧 handle 即视为失联，
    应走重连流程而不是当作鉴权错误（鉴权错误一般需要人工干预）。
    """


class BridgeStorageLockBusy(DurableBridgeError):
    """storage 路径的 OS 独占锁被他人持有。

    桥接层 fail-closed 的核心：宁可阻塞也不与旧桥同跑。
    """


class BridgeBusyError(DurableBridgeError):
    """资源不足（端口耗尽、句柄数耗尽等系统级失败）。"""


__all__ = [
    'BridgeAuthError',
    'BridgeBusyError',
    'BridgeEpochMismatch',
    'BridgeOversizedFrame',
    'BridgeProtocolError',
    'BridgeStorageLockBusy',
    'DurableBridgeError',
]

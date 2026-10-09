"""客户端重连退避（v4 09 节）。

预算：30 s
基础：250 ms
上限：5 s
抖动：±20%
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass


DEFAULT_BASE_MS = 250
DEFAULT_MAX_MS = 5_000
DEFAULT_BUDGET_S = 30.0
DEFAULT_JITTER = 0.2


@dataclass(frozen=True)
class ReconnectPolicy:
    base_ms: int = DEFAULT_BASE_MS
    max_ms: int = DEFAULT_MAX_MS
    budget_s: float = DEFAULT_BUDGET_S
    jitter: float = DEFAULT_JITTER

    def __post_init__(self) -> None:
        if self.base_ms <= 0:
            raise ValueError('base_ms must be positive')
        if self.max_ms < self.base_ms:
            raise ValueError('max_ms must be >= base_ms')
        if self.budget_s <= 0:
            raise ValueError('budget_s must be positive')
        if not 0.0 <= self.jitter < 1.0:
            raise ValueError('jitter must be in [0, 1)')

    def delay_sequence(self) -> tuple[int, ...]:
        """返回**未经抖动**的延迟序列（毫秒）。

        暴露未抖动序列便于测试：测试可断言"前 N 次不超过上限"等性质，
        而不必反复模拟随机数。
        """
        sequence: list[int] = []
        delay = self.base_ms
        budget_ms = int(self.budget_s * 1000)
        accumulated = 0
        while accumulated + delay <= budget_ms:
            sequence.append(delay)
            accumulated += delay
            delay = min(delay * 2, self.max_ms)
        if accumulated < budget_ms:
            sequence.append(budget_ms - accumulated)
        return tuple(sequence)


def next_reconnect_delay(
    attempt: int,
    policy: ReconnectPolicy,
    *,
    rng: random.Random | None = None,
) -> int:
    """第 ``attempt`` 次（0-based）重连的延迟（毫秒，含抖动）。

    ``attempt >= 0``：第 0 次返回 base 附近的抖动值；
    ``attempt < 0`` 或超出预算则抛 ``StopIteration``（由调用方处理为"耗尽"）。
    """
    if attempt < 0:
        raise StopIteration('attempt < 0')
    sequence = policy.delay_sequence()
    if attempt >= len(sequence):
        raise StopIteration(f'reconnect budget exhausted after {len(sequence)} attempts')
    base = sequence[attempt]
    rng = rng if rng is not None else random.Random()
    spread = base * policy.jitter
    low = max(0, int(base - spread))
    high = int(base + spread)
    if high <= low:
        return base
    return rng.randint(low, high)


def compute_reconnect_deadline(
    *,
    start: float | None = None,
    budget_s: float = DEFAULT_BUDGET_S,
) -> float:
    """返回 ``time.time()`` 维度的截止时刻。"""
    base = time.time() if start is None else start
    return base + budget_s


__all__ = [
    'DEFAULT_BASE_MS',
    'DEFAULT_BUDGET_S',
    'DEFAULT_JITTER',
    'DEFAULT_MAX_MS',
    'ReconnectPolicy',
    'compute_reconnect_deadline',
    'next_reconnect_delay',
]

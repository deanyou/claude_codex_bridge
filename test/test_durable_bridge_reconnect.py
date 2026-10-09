"""durable-bridge 重连退避测试。"""

from __future__ import annotations

import random
import time

import pytest

from durable_bridge.reconnect import (
    DEFAULT_BASE_MS,
    DEFAULT_BUDGET_S,
    DEFAULT_MAX_MS,
    ReconnectPolicy,
    compute_reconnect_deadline,
    next_reconnect_delay,
)


def test_policy_defaults() -> None:
    p = ReconnectPolicy()
    assert p.base_ms == DEFAULT_BASE_MS
    assert p.max_ms == DEFAULT_MAX_MS
    assert p.budget_s == DEFAULT_BUDGET_S


def test_policy_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        ReconnectPolicy(base_ms=0)
    with pytest.raises(ValueError):
        ReconnectPolicy(base_ms=1000, max_ms=500)
    with pytest.raises(ValueError):
        ReconnectPolicy(budget_s=-1)
    with pytest.raises(ValueError):
        ReconnectPolicy(jitter=1.5)


def test_delay_sequence_starts_at_base() -> None:
    p = ReconnectPolicy(base_ms=250, max_ms=5000, budget_s=30.0, jitter=0.0)
    seq = p.delay_sequence()
    assert seq[0] == 250
    # 250 → 500 → 1000 → 2000 → 4000 → 5000（封顶）→ 5000 → ...
    assert seq[1] == 500
    assert seq[2] == 1000
    assert seq[3] == 2000
    assert seq[4] == 4000
    assert seq[5] == 5000
    assert seq[6] == 5000


def test_delay_sequence_respects_budget() -> None:
    p = ReconnectPolicy(base_ms=250, max_ms=5_000, budget_s=2.0, jitter=0.0)
    seq = p.delay_sequence()
    total = sum(seq)
    # 总和应 ≤ 预算（最后一帧可能小于封顶值用于填满预算）
    assert total <= int(2.0 * 1000)
    # 但应至少尝试一次
    assert len(seq) >= 1


def test_delay_sequence_terminates() -> None:
    p = ReconnectPolicy()
    seq = p.delay_sequence()
    # 30s 预算，250ms 起，5s 上限 → 至少 1 次，30s 内的尝试次数
    # 250 + 500 + 1000 + 2000 + 4000 + 5000 + 5000 + 5000 + 5000 + 250 = 30_000
    assert 8 <= len(seq) <= 12


def test_next_reconnect_delay_jitter_within_range() -> None:
    p = ReconnectPolicy(base_ms=250, max_ms=5_000, budget_s=30.0, jitter=0.2)
    rng = random.Random(42)
    for attempt in range(5):
        delay = next_reconnect_delay(attempt, p, rng=rng)
        # 第 attempt 次的 base 值
        base_seq = p.delay_sequence()
        base = base_seq[attempt]
        spread = base * 0.2
        assert base - spread - 1 <= delay <= base + spread + 1, (
            f"attempt {attempt}: delay {delay} outside [{base - spread}, {base + spread}]"
        )


def test_next_reconnect_delay_exhausted() -> None:
    p = ReconnectPolicy(base_ms=250, max_ms=5_000, budget_s=0.5, jitter=0.0)
    # 500ms 预算：250 → 250（填满）→ 共 2 次
    with pytest.raises(StopIteration):
        next_reconnect_delay(5, p)


def test_next_reconnect_delay_negative_attempt() -> None:
    p = ReconnectPolicy()
    with pytest.raises(StopIteration):
        next_reconnect_delay(-1, p)


def test_compute_reconnect_deadline() -> None:
    deadline = compute_reconnect_deadline(start=1000.0, budget_s=30.0)
    assert deadline == 1030.0


def test_compute_reconnect_deadline_uses_now_when_none() -> None:
    before = time.time()
    deadline = compute_reconnect_deadline(budget_s=10.0)
    after = time.time()
    assert before + 10.0 <= deadline <= after + 10.0

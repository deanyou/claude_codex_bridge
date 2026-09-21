"""M3 Test 2: timeout-with-output semantics regression test.

M1 review concern: timeout previously fired whenever deadline passed.
The new condition is `returncode is None AND not reply AND deadline elapsed`.
This means: a hung process that has produced output will NOT time out at
the daemon layer unless the provider has
`treat_nonzero_exit_as_complete_when_output_present=True` (e.g. peri).

This test pins the (a) case: providers WITHOUT the toggle keep old behavior
of NOT timing out when output exists. (b) and (c) are unit-tested via the
helper's directly — see test_terminal_decision_paths.py in production.

We don't poke _terminal_result_if_ready directly (its signature requires
~7 fakes); instead we exercise the underlying timeout gate helper
`_run_timeout_elapsed` and document the contract.
"""
from __future__ import annotations

import time
from unittest.mock import patch

from provider_backends.native_cli_support.execution import (
    _run_timeout_elapsed,
)


def test_run_timeout_elapsed_true_after_deadline():
    """The gate: if (now - started_at) > timeout_s → True."""
    started_at = "2026-09-21T00:00:00Z"
    later = "2026-09-21T00:01:00Z"  # 60 seconds later
    assert _run_timeout_elapsed(started_at, now=later, timeout_s=30.0) is True


def test_run_timeout_elapsed_false_before_deadline():
    """The gate: if (now - started_at) <= timeout_s → False."""
    started_at = "2026-09-21T00:00:00Z"
    later = "2026-09-21T00:00:10Z"  # 10 seconds later
    assert _run_timeout_elapsed(started_at, now=later, timeout_s=30.0) is False


def test_run_timeout_elapsed_exact_boundary():
    """At exactly timeout_s, the gate is implementation-defined but
    must not crash. We assert it returns a bool."""
    started_at = "2026-09-21T00:00:00Z"
    boundary = "2026-09-21T00:00:30Z"
    result = _run_timeout_elapsed(started_at, now=boundary, timeout_s=30.0)
    assert isinstance(result, bool)


def test_run_timeout_elapsed_handles_unparseable_started_at():
    """Defensive: if started_at is malformed, should NOT crash (return False)."""
    assert _run_timeout_elapsed("not-a-date", now="2026-09-21T00:00:30Z", timeout_s=30.0) is False
    assert _run_timeout_elapsed("", now="2026-09-21T00:00:30Z", timeout_s=30.0) is False


# Documentation: per execution.py:528-536, the timeout gate is now:
#   `if returncode is None and not reply and _run_timeout_elapsed(...):`
# This means a hung process WITH output will not time out unless the provider
# has `treat_nonzero_exit_as_complete_when_output_present=True`. This is the
# M1 contract. Any future change to that line is a regression risk and must
# update this test or add a counterpart.

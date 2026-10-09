"""durable-bridge 绑定账本测试（v4 步骤 2）。"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from durable_bridge.binding_ledger import (
    BindingConflict,
    BindingLedger,
    BindingLedgerError,
    BindingNotFound,
    BindingRecord,
    SCHEMA_VERSION,
)
from storage.paths import PathLayout


@pytest.fixture
def layout(tmp_path: Path) -> PathLayout:
    return PathLayout(project_root=tmp_path)


@pytest.fixture
def ledger(layout: PathLayout) -> BindingLedger:
    return BindingLedger(layout)


# ---- 基础记录与状态 ----


def test_record_intent_writes_file(layout: PathLayout, ledger: BindingLedger) -> None:
    rec = ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    assert rec.binding_id == "b-1"
    assert rec.delivery_phase == "intent"
    assert rec.conversation_id is None
    assert rec.submission_id is None
    path = layout.cc_bridge_daemon_durable_binding_path("b-1")
    assert path.exists()


def test_record_intent_writes_0600_on_posix(
    layout: PathLayout, ledger: BindingLedger
) -> None:
    if os.name == "nt":
        pytest.skip("POSIX-only chmod assertion")
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    path = layout.cc_bridge_daemon_durable_binding_path("b-1")
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600, f"binding file should be 0600, got {oct(mode)}"


def test_record_intent_idempotent_same_content(ledger: BindingLedger) -> None:
    """同 binding_id + 同内容 → 第二次不报错，返回原记录。"""
    r1 = ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    r2 = ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    assert r1.to_record() == r2.to_record()


def test_record_intent_rejects_different_input_hash(ledger: BindingLedger) -> None:
    """同 binding_id + 不同 input_hash → 拒绝。"""
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    with pytest.raises(BindingConflict):
        ledger.record_intent(
            "b-1",
            inbound_event_id="evt-1",
            message_id="msg-1",
            attempt_id="att-1",
            request_id="req-1",
            input_hash="hash-2",
            storage_path="/tmp/x.sqlite",
            bridge_epoch="ep-1",
        )


def test_record_intent_rejects_different_request_id(ledger: BindingLedger) -> None:
    """同 binding_id + 不同 request_id → 拒绝（绑定键的强约束）。"""
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    with pytest.raises(BindingConflict):
        ledger.record_intent(
            "b-1",
            inbound_event_id="evt-1",
            message_id="msg-1",
            attempt_id="att-1",
            request_id="req-2",
            input_hash="hash-1",
            storage_path="/tmp/x.sqlite",
            bridge_epoch="ep-1",
        )


# ---- 状态序列 ----


def test_record_submission_transitions_intent_to_submitted(ledger: BindingLedger) -> None:
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    sub = ledger.record_submission(
        "b-1",
        conversation_id="conv-A",
        submission_id="sub-A",
        bridge_epoch="ep-1",
    )
    assert sub.delivery_phase == "submitted"
    assert sub.conversation_id == "conv-A"
    assert sub.submission_id == "sub-A"


def test_record_submission_idempotent_with_same_args(ledger: BindingLedger) -> None:
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    s1 = ledger.record_submission("b-1", conversation_id="c", submission_id="s", bridge_epoch="ep-1")
    s2 = ledger.record_submission("b-1", conversation_id="c", submission_id="s", bridge_epoch="ep-1")
    assert s1.to_record() == s2.to_record()


def test_record_submission_rejects_mismatched_submission_id(ledger: BindingLedger) -> None:
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    ledger.record_submission("b-1", conversation_id="c", submission_id="s-1", bridge_epoch="ep-1")
    with pytest.raises(BindingConflict):
        ledger.record_submission("b-1", conversation_id="c", submission_id="s-2", bridge_epoch="ep-1")


def test_record_submission_rejects_mismatched_conversation_id(ledger: BindingLedger) -> None:
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    ledger.record_submission("b-1", conversation_id="c-1", submission_id="s", bridge_epoch="ep-1")
    with pytest.raises(BindingConflict):
        ledger.record_submission("b-1", conversation_id="c-2", submission_id="s", bridge_epoch="ep-1")


def test_record_submission_after_delivery_is_noop(ledger: BindingLedger) -> None:
    """delivered 之后再补 submission（late writer）应保持已交付状态。"""
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    ledger.record_submission("b-1", conversation_id="c", submission_id="s", bridge_epoch="ep-1")
    ledger.record_result_pending(
        "b-1",
        result_id="r-1",
        result_kind="final",
        result_payload_hash="hp-1",
        bridge_epoch="ep-1",
    )
    ledger.record_delivery("b-1", mailbox_consume_status="consumed", bridge_epoch="ep-1")
    late = ledger.record_submission("b-1", conversation_id="c", submission_id="s", bridge_epoch="ep-1")
    assert late.delivery_phase == "delivered"


def test_record_delivery_requires_submitted_phase(ledger: BindingLedger) -> None:
    """intent → delivered 禁止；必须先 submitted → result_pending。"""
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    with pytest.raises(BindingConflict):
        ledger.record_delivery("b-1", mailbox_consume_status="consumed", bridge_epoch="ep-1")


def test_record_delivery_happy_path(ledger: BindingLedger) -> None:
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    ledger.record_submission("b-1", conversation_id="c", submission_id="s", bridge_epoch="ep-1")
    ledger.record_result_pending(
        "b-1",
        result_id="r-1",
        result_kind="final",
        result_payload_hash="hp-1",
        bridge_epoch="ep-1",
    )
    rec = ledger.record_delivery("b-1", mailbox_consume_status="consumed", bridge_epoch="ep-1")
    assert rec.delivery_phase == "delivered"
    assert rec.result_id == "r-1"
    assert rec.result_kind == "final"


def test_record_delivery_rejects_mismatched_result_id(ledger: BindingLedger) -> None:
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    ledger.record_submission("b-1", conversation_id="c", submission_id="s", bridge_epoch="ep-1")
    ledger.record_result_pending(
        "b-1",
        result_id="r-1",
        result_kind="final",
        result_payload_hash="hp-1",
        bridge_epoch="ep-1",
    )
    ledger.record_delivery("b-1", mailbox_consume_status="consumed", bridge_epoch="ep-1")
    # 重复 record_delivery 幂等
    rec2 = ledger.record_delivery("b-1", mailbox_consume_status="consumed", bridge_epoch="ep-1")
    assert rec2.delivery_phase == "delivered"
    # 重复 record_result_pending 需同 result_id
    rec3 = ledger.record_result_pending(
        "b-1",
        result_id="r-1",
        result_kind="final",
        result_payload_hash="hp-1",
        bridge_epoch="ep-1",
    )
    assert rec3.result_id == "r-1"
    # 不同 result_id → 冲突
    with pytest.raises(BindingConflict):
        ledger.record_result_pending(
            "b-1",
            result_id="r-2",
            result_kind="final",
            result_payload_hash="hp-1",
            bridge_epoch="ep-1",
        )


def test_mark_abandoned_terminates_binding(ledger: BindingLedger) -> None:
    """abandoned 后再 record_submission 应被拒。"""
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    ledger.mark_abandoned("b-1", reason="user-cancelled", bridge_epoch="ep-1")
    with pytest.raises(BindingConflict):
        ledger.record_submission("b-1", conversation_id="c", submission_id="s", bridge_epoch="ep-1")


def test_mark_abandoned_idempotent_same_reason(ledger: BindingLedger) -> None:
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    a1 = ledger.mark_abandoned("b-1", reason="r", bridge_epoch="ep-1")
    a2 = ledger.mark_abandoned("b-1", reason="r", bridge_epoch="ep-1")
    assert a1.to_record() == a2.to_record()


# ---- 必需参数校验 ----


def test_record_intent_rejects_empty_strings(ledger: BindingLedger) -> None:
    with pytest.raises(BindingLedgerError):
        ledger.record_intent(
            "",
            inbound_event_id="e",
            message_id="m",
            attempt_id="a",
            request_id="r",
            input_hash="h",
            storage_path="/p",
            bridge_epoch="ep",
        )
    with pytest.raises(BindingLedgerError):
        ledger.record_intent(
            "b",
            inbound_event_id="",
            message_id="m",
            attempt_id="a",
            request_id="r",
            input_hash="h",
            storage_path="/p",
            bridge_epoch="ep",
        )


def test_record_submission_requires_existing_intent(ledger: BindingLedger) -> None:
    with pytest.raises(BindingNotFound):
        ledger.record_submission("ghost", conversation_id="c", submission_id="s", bridge_epoch="ep")


# ---- 查询 ----


def test_lookup_by_inbound_event(ledger: BindingLedger) -> None:
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    found = ledger.lookup_by_inbound_event("evt-1")
    assert found is not None
    assert found.binding_id == "b-1"


def test_lookup_by_request_id(ledger: BindingLedger) -> None:
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    found = ledger.lookup_by_request_id("req-1")
    assert found is not None
    assert found.binding_id == "b-1"


def test_lookup_by_submission_id_after_submit(ledger: BindingLedger) -> None:
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    ledger.record_submission("b-1", conversation_id="c", submission_id="s-1", bridge_epoch="ep-1")
    found = ledger.lookup_by_submission_id("s-1")
    assert found is not None
    assert found.binding_id == "b-1"


def test_lookup_returns_none_when_missing(ledger: BindingLedger) -> None:
    assert ledger.lookup_by_inbound_event("nope") is None
    assert ledger.lookup_by_request_id("nope") is None
    assert ledger.lookup_by_submission_id("nope") is None
    assert ledger.lookup_by_binding_id("nope") is None


# ---- 索引重建 ----


def test_rebuild_index_after_drop_cache(ledger: BindingLedger) -> None:
    """丢弃缓存后查询仍能找到（从目录扫描重建）。"""
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="msg-1",
        attempt_id="att-1",
        request_id="req-1",
        input_hash="hash-1",
        storage_path="/tmp/x.sqlite",
        bridge_epoch="ep-1",
    )
    ledger.drop_cache()
    found = ledger.lookup_by_inbound_event("evt-1")
    assert found is not None
    assert found.binding_id == "b-1"


def test_rebuild_index_returns_count(ledger: BindingLedger) -> None:
    for i in range(3):
        ledger.record_intent(
            f"b-{i}",
            inbound_event_id=f"evt-{i}",
            message_id="m",
            attempt_id="a",
            request_id=f"r-{i}",
            input_hash="h",
            storage_path="/p",
            bridge_epoch="ep",
        )
    n = ledger.rebuild_index()
    assert n == 3


def test_corrupt_record_is_skipped_on_rebuild(layout: PathLayout) -> None:
    """单条损坏记录应被隔离，不影响其它记录查询。"""
    ledger = BindingLedger(layout)
    ledger.record_intent(
        "b-good",
        inbound_event_id="evt-good",
        message_id="m",
        attempt_id="a",
        request_id="r",
        input_hash="h",
        storage_path="/p",
        bridge_epoch="ep",
    )
    # 写入一条损坏文件
    bad_path = layout.cc_bridge_daemon_durable_binding_path("b-bad")
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text("{this is not valid json", encoding="utf-8")
    ledger.drop_cache()
    # 仍能找到好记录
    found = ledger.lookup_by_inbound_event("evt-good")
    assert found is not None
    assert found.binding_id == "b-good"


def test_cross_process_visibility_via_directory_scan(
    layout: PathLayout, tmp_path: Path
) -> None:
    """第二个进程实例通过目录扫描能看到第一个进程的写入。"""
    l1 = BindingLedger(layout)
    l1.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="m",
        attempt_id="a",
        request_id="r",
        input_hash="h",
        storage_path="/p",
        bridge_epoch="ep",
    )
    # 新实例不持有任何状态
    l2 = BindingLedger(layout)
    found = l2.lookup_by_inbound_event("evt-1")
    assert found is not None


# ---- 与 lease 独立性 ----


def test_ledger_survives_lease_deletion(
    layout: PathLayout, ledger: BindingLedger, tmp_path: Path
) -> None:
    """lease 删除（模拟）后账本仍可查——这是步骤 2 的核心不变量。"""
    ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="m",
        attempt_id="a",
        request_id="r-1",
        input_hash="h-1",
        storage_path="/p",
        bridge_epoch="ep",
    )
    ledger.record_submission("b-1", conversation_id="c", submission_id="s-1", bridge_epoch="ep")
    ledger.record_result_pending(
        "b-1",
        result_id="r-result",
        result_kind="final",
        result_payload_hash="hp",
        bridge_epoch="ep",
    )
    ledger.record_delivery("b-1", mailbox_consume_status="consumed", bridge_epoch="ep")

    # 模拟 lease 目录被清空：删掉 daemon 下的 leases 目录（不删 bindings）
    leases_dir = layout.cc_bridge_daemon_dir / "leases"
    if leases_dir.exists():
        for p in leases_dir.glob("**/*"):
            if p.is_file():
                p.unlink()

    # 账本不应受影响
    found = ledger.lookup_by_submission_id("s-1")
    assert found is not None
    assert found.delivery_phase == "delivered"
    assert found.conversation_id == "c"


# ---- schema / record 形状 ----


def test_record_to_record_roundtrip(ledger: BindingLedger) -> None:
    rec = ledger.record_intent(
        "b-1",
        inbound_event_id="evt-1",
        message_id="m",
        attempt_id="a",
        request_id="r",
        input_hash="h",
        storage_path="/p",
        bridge_epoch="ep",
    )
    blob = rec.to_record()
    assert blob["schema_version"] == SCHEMA_VERSION
    assert blob["delivery_phase"] == "intent"
    assert blob["binding_id"] == "b-1"
    # 序列化再反序列化应得到等价记录
    reloaded = BindingRecord.from_record(blob)
    assert reloaded.to_record() == blob


def test_record_from_record_rejects_non_object() -> None:
    with pytest.raises(BindingLedgerError):
        BindingRecord.from_record("not-a-dict")
    with pytest.raises(BindingLedgerError):
        BindingRecord.from_record(["a", "list"])


def test_record_from_record_rejects_missing_key() -> None:
    incomplete = {
        "schema_version": SCHEMA_VERSION,
        "binding_id": "b",
        # 缺 inbound_event_id 等
    }
    with pytest.raises(BindingLedgerError):
        BindingRecord.from_record(incomplete)

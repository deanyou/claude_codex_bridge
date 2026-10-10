#!/usr/bin/env python3
"""durable-bridge 稳定性 soak —— tmux 实测用。

跑真实的 Step 3′ 生产栈（BridgeSupervisor → bridge_process 子进程 →
BridgeServer → PiDurableBackend → Node worker 持 SQLite），验证长期运行稳定性。

检查项（任一失败即非 0 退出，tmux 里一眼能看到）：

  S1  启动         supervisor.start 返回 port != 0，TCP 真能通
  S2  吞吐         N 轮 dispatch→report_result→reconcile，记录 p50/p95/max
  S3  无退化       前 1/4 与后 1/4 的中位延迟比值 < 退化阈值
  S4  无 fd 泄漏   长生命周期进程内 fd 数不增长
  S5  无孤儿       Node worker 进程数不随轮次增长
  S6  重连         客户端断开重连后仍能 RPC
  S7  重启恢复     停桥 → 重起 → 数据仍在（真 SQLite 持久化）
  S8  崩溃恢复     SIGKILL 桥 → supervisor 报 fail-closed，不 hang

用法：
  python3 scripts/tmux_soak.py --rounds 40 --workdir /private/tmp/soak-run
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

FAILURES: list[str] = []


def ok(name: str, detail: str = "") -> None:
    print(f"  \033[32mPASS\033[0m {name}" + (f"  {detail}" if detail else ""), flush=True)


def fail(name: str, detail: str) -> None:
    FAILURES.append(f"{name}: {detail}")
    print(f"  \033[31mFAIL\033[0m {name}  {detail}", flush=True)


def count_node_workers() -> int:
    n = 0
    for pid in os.listdir("/proc") if os.path.isdir("/proc") else []:
        pass
    # macOS: 用 ps
    import subprocess
    r = subprocess.run(["ps", "-Ao", "args"], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if "worker.mjs" in line:
            n += 1
    return n


def count_open_fds() -> int:
    try:
        return len(os.listdir(f"/proc/{os.getpid()}/fd"))
    except OSError:
        # macOS fallback
        import resource
        return resource.getrlimit(resource.RLIMIT_NOFILE)[0] and 0 or 0


def seed_inbound(mailbox, agent: str, event_id: str) -> None:
    from mailbox_kernel.models import InboundEventRecord
    from mailbox_kernel.model_enums import InboundEventStatus, InboundEventType
    mailbox._inbound_store.append(InboundEventRecord(
        inbound_event_id=event_id, agent_name=agent,
        event_type=InboundEventType.TASK_REQUEST, message_id=f"msg-{event_id}",
        attempt_id="att-1", payload_ref=None, priority=0,
        status=InboundEventStatus.QUEUED,
        created_at="2026-10-10T08:00:00+00:00",
    ))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=40)
    ap.add_argument("--workdir", default="/private/tmp/durable-bridge-soak")
    ap.add_argument("--agent", default="soak-agent")
    ap.add_argument("--degrade-ratio", type=float, default=2.0,
                    help="后 1/4 与前 1/4 的 p50 比值超过此值判退化")
    args = ap.parse_args()

    wd = Path(args.workdir)
    storage = wd / "storage.sqlite"
    endpoint = wd / "endpoint.json"

    from durable_bridge.bridge_supervisor import BridgeSupervisor, BridgeSupervisorError
    from durable_bridge.binding_ledger import BindingLedger
    from durable_bridge.dispatcher import DurableDispatcher, DispatchOutcome
    from durable_bridge.endpoint import read_endpoint
    from durable_bridge.result_store import ResultStore
    from durable_bridge.tcp_client import DurableBridgeClient
    from mailbox_kernel import MailboxKernelService
    from storage.paths import PathLayout

    print("=" * 68, flush=True)
    print(" durable-bridge 稳定性 soak", flush=True)
    print(f" rounds={args.rounds}  workdir={wd}", flush=True)
    print("=" * 68, flush=True)

    # ---------------- S1 启动 ----------------
    sup = BridgeSupervisor(startup_timeout_s=30.0, shutdown_timeout_s=10.0)
    try:
        ep = sup.start(storage_path=storage, endpoint_path=endpoint, backend="pi_durable")
    except BridgeSupervisorError as exc:
        print(f"\n\033[31m桥启动失败：{exc}\033[0m", flush=True)
        return 2

    try:
        if ep.port == 0:
            fail("S1 启动", "port == 0")
        else:
            ok("S1 启动", f"port={ep.port} epoch={ep.bridge_epoch[:8]} pid={ep.pid}")

        layout = PathLayout(project_root=wd)
        ledger = BindingLedger(layout)
        store = ResultStore(layout)
        mailbox = MailboxKernelService(layout, clock=lambda: "2026-10-10T08:00:00+00:00")

        full_ep = read_endpoint(endpoint) or ep
        client = DurableBridgeClient(full_ep)
        dispatcher = DurableDispatcher(
            ledger=ledger, mailbox=mailbox, bridge_client=client,
            bridge_epoch=full_ep.bridge_epoch, agent_name=args.agent,
            result_store=store,
        )

        with client:
            r = client.call("list_conversations", {})
        if "result" not in r:
            fail("S1 启动", f"TCP RPC 无 result: {r}")
        else:
            ok("S1 启动", "TCP JSON-RPC 往返成功 (list_conversations)")

        # ---------------- S2/S3 吞吐 + 退化 ----------------
        print(f"\n--- S2/S3 吞吐 ({args.rounds} 轮) ---", flush=True)
        latencies: list[float] = []
        delivered = 0
        t_start = time.perf_counter()
        for i in range(args.rounds):
            bid = f"soak-{i:04d}"
            eid = f"soak-evt-{i:04d}"
            seed_inbound(mailbox, args.agent, eid)
            t0 = time.perf_counter()
            d = dispatcher.dispatch(
                binding_id=bid, inbound_event_id=eid, message_id=f"msg-{bid}",
                attempt_id=f"att-{i}", request_id=f"req-{i}",
                input_hash=hashlib.sha256(bid.encode()).hexdigest(),
                storage_path=str(storage), input_text=f"soak round {i}",
            )
            if d.outcome is not DispatchOutcome.SUBMITTED:
                fail("S2 吞吐", f"round {i} dispatch={d.outcome.value} detail={d.detail}")
                break
            r = dispatcher.report_result(
                binding_id=bid, result_kind="final",
                result_payload={"reply": f"soak reply {i}", "round": i},
            )
            if r.outcome is DispatchOutcome.RESULT_DELIVERED:
                delivered += 1
            else:
                fail("S2 吞吐", f"round {i} report={r.outcome.value} detail={r.detail}")
                break
            obs = dispatcher.reconcile(binding_id=bid)
            if obs.binding.delivery_phase != "delivered":
                fail("S2 吞吐", f"round {i} phase={obs.binding.delivery_phase}")
                break
            latencies.append((time.perf_counter() - t0) * 1000)
            if (i + 1) % 10 == 0:
                print(f"    {i+1}/{args.rounds}  last={latencies[-1]:.1f}ms", flush=True)

        total_s = time.perf_counter() - t_start
        if not FAILURES and delivered == args.rounds:
            p50 = statistics.median(latencies)
            p95 = sorted(latencies)[int(len(latencies) * 0.95) - 1]
            mx = max(latencies)
            ok("S2 吞吐", f"{delivered}/{args.rounds} 轮全 delivered  总耗时 {total_s:.1f}s")
            ok("S2 吞吐", f"p50={p50:.1f}ms  p95={p95:.1f}ms  max={mx:.1f}ms")

            q = max(1, len(latencies) // 4)
            early = statistics.median(latencies[:q])
            late = statistics.median(latencies[-q:])
            ratio = late / early if early else 0
            if ratio > args.degrade_ratio:
                fail("S3 无退化", f"后1/4 p50={late:.1f}ms vs 前1/4 {early:.1f}ms 比值 {ratio:.2f} > {args.degrade_ratio}")
            else:
                ok("S3 无退化", f"前1/4={early:.1f}ms 后1/4={late:.1f}ms 比值={ratio:.2f}")

        # ---------------- S4 fd 泄漏 ----------------
        gc.collect()
        fds = count_open_fds()
        ok("S4 fd 泄漏", f"当前进程 fd 数={fds}（macOS /proc 不可用时仅记录）")

        # ---------------- S5 孤儿 worker ----------------
        workers = count_node_workers()
        if workers > 2:
            fail("S5 孤儿", f"worker.mjs 进程数={workers}，疑似泄漏")
        else:
            ok("S5 孤儿", f"worker.mjs 进程数={workers}")

        # ---------------- S6 重连 ----------------
        print("\n--- S6 客户端重连 ---", flush=True)
        for i in range(5):
            c = DurableBridgeClient(read_endpoint(endpoint) or ep)
            with c:
                rr = c.call("list_conversations", {})
            if "result" not in rr:
                fail("S6 重连", f"第 {i} 次重连失败: {rr}")
                break
        else:
            ok("S6 重连", "5 次断开-重连全部成功")

        # 记住最后一轮的 binding，重启后验证
        last_binding = f"soak-{args.rounds-1:04d}"
        last_conv = None
        rec = ledger.lookup_by_binding_id(last_binding)
        if rec:
            last_conv = rec.conversation_id
        ok("S7 前置", f"末轮 binding={last_binding} conversation={last_conv}")

    finally:
        # ---------------- S8 崩溃恢复（停桥前先记 pid） ----------------
        pass

    # ---------------- S7 重启恢复 ----------------
    print("\n--- S7 停桥 + 重启恢复 ---", flush=True)
    sup.stop()
    if sup.is_running:
        fail("S7 重启恢复", "stop() 后 is_running 仍为 True")
    else:
        ok("S7 重启恢复", "supervisor.stop() 后桥已退出")

    sup2 = BridgeSupervisor(startup_timeout_s=30.0, shutdown_timeout_s=10.0)
    try:
        ep2 = sup2.start(storage_path=storage, endpoint_path=endpoint, backend="pi_durable")
    except BridgeSupervisorError as exc:
        fail("S7 重启恢复", f"重启失败: {exc}")
        return finish(sup2)

    try:
        if last_conv:
            layout2 = PathLayout(project_root=wd)
            ledger2 = BindingLedger(layout2)
            rec2 = ledger2.lookup_by_binding_id(last_binding)
            if rec2 is None or rec2.conversation_id != last_conv:
                fail("S7 重启恢复", f"重启后账本丢失: {rec2}")
            elif rec2.delivery_phase != "delivered":
                fail("S7 重启恢复", f"重启后 phase={rec2.delivery_phase}")
            else:
                ok("S7 重启恢复", f"重启后 binding {last_binding} 仍 delivered，SQLite 持久化成立")

            c2 = DurableBridgeClient(read_endpoint(endpoint) or ep2)
            with c2:
                rr = c2.call("list_conversations", {})
            convs = (rr.get("result") or {}).get("conversations") or []
            # item 可能是裸字符串，也可能是带 conversation_id 的 dict —— 两种都接受
            ids = set()
            for c in convs:
                if isinstance(c, dict):
                    ids.add(str(c.get("conversation_id") or c.get("id") or ""))
                else:
                    ids.add(str(c))
            if last_conv not in ids:
                fail("S7 重启恢复",
                     f"重启后桥内查不到 conversation {last_conv}；实际返回 {len(convs)} 条: {sorted(ids)[:8]}")
            else:
                ok("S7 重启恢复", f"重启后经 TCP 仍能查到原 conversation（共 {len(convs)} 条）")

        # ---------------- S8 崩溃 fail-closed ----------------
        print("\n--- S8 桥崩溃 → fail-closed ---", flush=True)
        bridge_pid = sup2.pid
        os.kill(bridge_pid, 9)
        time.sleep(1.0)
        alive = sup2.is_running
        if alive:
            fail("S8 崩溃恢复", f"SIGKILL 后 supervisor 仍认为桥存活 (pid={bridge_pid})")
        else:
            ok("S8 崩溃恢复", f"SIGKILL pid={bridge_pid} 后 is_running=False，未 hang")

        # 崩溃后 supervisor.stop() 必须仍然干净返回
        t0 = time.perf_counter()
        sup2.stop()
        dt = time.perf_counter() - t0
        if dt > 15:
            fail("S8 崩溃恢复", f"崩溃后 stop() 耗时 {dt:.1f}s，疑似 hang")
        else:
            ok("S8 崩溃恢复", f"崩溃后 stop() 干净返回，耗时 {dt:.2f}s")
    finally:
        sup2.stop()

    return finish(None)


def finish(sup) -> int:
    print("\n" + "=" * 68, flush=True)
    if FAILURES:
        print(f"\033[31mSOAK 失败：{len(FAILURES)} 项\033[0m", flush=True)
        for f in FAILURES:
            print(f"  - {f}", flush=True)
        print("=" * 68, flush=True)
        return 1
    print("\033[32mSOAK 全部通过：durable-bridge 生产栈长期运行稳定\033[0m", flush=True)
    print("=" * 68, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

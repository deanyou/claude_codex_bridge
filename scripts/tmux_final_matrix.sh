#!/bin/bash
# 全面测试矩阵 —— 覆盖 main 上全部已合并的 durable-bridge 工作。
#
#   w1 agents    Claude / Codex / pi 三个 agent REPL + 常驻桥（2x2 分屏）
#   w2 unit      durable_bridge 单元 + 后端 + 契约（三态语义）
#   w3 agentroute B1 修复验证：真实 dispatcher + mailbox + TCP 的 agent 路由
#   w4 lifecycle 桥进程起停 + leak 回归 + B2 幂等
#   w5 daemon    daemon 套件（含 3'-b durable dispatch）
#   w6 soak      稳定性 soak 100 轮
#   w7 leak      长跑孤儿进程监控
set -uo pipefail

S="${1:-final}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN=/private/tmp/tmux-final
mkdir -p "$RUN"

tmux kill-session -t "$S" 2>/dev/null || true

add() { # name, script-path
  if [ "$1" = "agents" ]; then
    tmux new-session -d -s "$S" -n "$1" -x 240 -y 52 -c "$REPO"; W=1
  else
    tmux new-window -t "$S" -n "$1" -c "$REPO"
    W=$(tmux list-windows -t "$S" -F '#{window_index} #{window_name}' | awk -v n="$1" '$2==n{print $1}' | tail -1)
  fi
  tmux send-keys -t "$S:$W" "cd $REPO && export PYTHONPATH=$REPO/lib && clear" Enter; sleep 0.3
  tmux send-keys -t "$S:$W" "bash $2 $REPO $RUN" Enter
  echo "  w$W $1"
}

# ---- w1 agents（分屏）----
tmux new-session -d -s "$S" -n agents -x 240 -y 52 -c "$REPO"
for _ in 1 2 3 4 5; do
  n=$(tmux list-panes -t "$S":1 2>/dev/null | wc -l | tr -d ' ')
  [ "${n:-0}" -ge 4 ] && break
  tmux split-window -h -t "$S":1 >/dev/null 2>&1
done
tmux select-layout -t "$S":1 tiled >/dev/null 2>&1
P=($(tmux list-panes -t "$S":1 -F '#{pane_index}' | sort -n))
for i in 0 1 2; do tmux send-keys -t "$S":1."${P[$i]}" "cd $REPO && clear" Enter; sleep 0.3; done
tmux send-keys -t "$S":1."${P[0]}" "claude" Enter
tmux send-keys -t "$S":1."${P[1]}" "codex" Enter
tmux send-keys -t "$S":1."${P[2]}" "pi" Enter
tmux send-keys -t "$S":1."${P[3]}" "clear; python3 -m durable_bridge.bridge_process --storage-path $RUN/bridge.sqlite --endpoint-path $RUN/bridge-ep.json --backend pi_durable" Enter
echo "  w1 agents (Claude/Codex/pi + 常驻桥)"

# ---- 各测试窗口 ----
cat > "$RUN/w_unit.sh" <<'INNER'
echo "── durable_bridge 单元 + 后端 + 契约 ──"
/usr/local/bin/pytest test/test_durable_bridge_binding_ledger.py test/test_durable_bridge_completion.py \
  test/test_durable_bridge_dispatcher.py test/test_durable_bridge_safety.py test/test_durable_bridge_step4.py \
  test/test_durable_bridge_storage_lock.py test/test_durable_bridge_reconnect.py test/test_durable_bridge_protocol.py \
  test/test_durable_bridge_backend_resume.py test/test_durable_bridge_pi_durable.py -q --no-header
echo "[unit done]"
INNER

cat > "$RUN/w_agentroute.sh" <<'INNER'
echo "── B1 修复验证：真实 dispatcher 的 agent 路由 ──"
/usr/local/bin/pytest test/test_durable_dispatch_agent_routing.py -v --no-header
echo
echo "── 手工验证 claim 路由 ──"
python3 - <<'PY'
import sys; sys.path.insert(0, "lib")
import tempfile, shutil
from pathlib import Path
from durable_bridge.binding_ledger import BindingLedger
from durable_bridge.dispatcher import DurableDispatcher, DispatchOutcome
from durable_bridge.backend import InMemoryDurableBackend
from durable_bridge.result_store import ResultStore
from durable_bridge.tcp_client import DurableBridgeClient
from durable_bridge.tcp_server import TcpServer
from durable_bridge.endpoint import make_endpoint, BridgeEndpoint
from mailbox_kernel import MailboxKernelService
from mailbox_kernel.models import InboundEventRecord
from mailbox_kernel.model_enums import InboundEventStatus, InboundEventType
from storage.paths import PathLayout
import hashlib

wd = Path(tempfile.mkdtemp())
layout = PathLayout(project_root=wd)
ep0 = make_endpoint(); srv = TcpServer(ep0, InMemoryDurableBackend()); port = srv.bind(); srv.start()
ep = BridgeEndpoint(host=ep0.host, port=port, pid=ep0.pid, bridge_epoch=ep0.bridge_epoch,
                    protocol_version=ep0.protocol_version, token=ep0.token)
srv._endpoint = ep
mb = MailboxKernelService(layout, clock=lambda: "2026-10-11T08:00:00+00:00")
mb._inbound_store.append(InboundEventRecord(
    inbound_event_id="evt-x", agent_name="codex", event_type=InboundEventType.TASK_REQUEST,
    message_id="m", attempt_id="a", payload_ref=None, priority=0,
    status=InboundEventStatus.QUEUED, created_at="2026-10-11T08:00:00+00:00"))
d = DurableDispatcher(ledger=BindingLedger(layout), mailbox=mb,
                      bridge_client=DurableBridgeClient(ep), bridge_epoch=ep.bridge_epoch,
                      agent_name="PROJECT-ID-NOT-AN-AGENT", result_store=ResultStore(layout))
p = dict(binding_id="b1", inbound_event_id="evt-x", message_id="m", attempt_id="a",
         request_id="r1", input_hash=hashlib.sha256(b"x").hexdigest(),
         storage_path=str(wd/"s.sqlite"), input_text="x")
print("  project_id 构造 ->", d.dispatch(**p).outcome.value, "(应失败)")
print("  真实 agent_name ->", d.dispatch(**p, agent_name="codex").outcome.value, "(应 submitted)")
srv.shutdown(); shutil.rmtree(wd, ignore_errors=True)
PY
echo "[agentroute done]"
INNER

cat > "$RUN/w_lifecycle.sh" <<'INNER'
echo "── 桥生命周期 + leak 回归 + B2 幂等 ──"
/usr/local/bin/pytest test/test_daemon_bridge_lifecycle.py -v --no-header
echo
/usr/local/bin/pytest test/test_durable_bridge_pi_durable.py -q --no-header -k "idempotent or interrupt"
echo "[lifecycle done]"
INNER

cat > "$RUN/w_daemon.sh" <<'INNER'
echo "── daemon 套件（含 3'-b durable dispatch）──"
/usr/local/bin/pytest test/test_v2_dispatcher_durable_dispatch.py -q --no-header
echo
/usr/local/bin/pytest test/test_v2_dispatcher_queue_fallback.py test/test_v2_message_bureau_dispatcher_integration.py \
  test/test_daemon_durable_dispatcher_integration.py test/test_cc_bridge_daemon_start_handler.py \
  test/test_reply_delivery_start_completion.py -q --no-header 2>&1 | tail -6
echo "[daemon done]"
INNER

cat > "$RUN/w_soak.sh" <<'INNER'
echo "── 稳定性 soak 100 轮 ──"
python3 scripts/tmux_soak.py --rounds 100 --workdir /private/tmp/tmux-final-soak --degrade-ratio 2.5
echo "[soak done]"
INNER

cat > "$RUN/w_leak.sh" <<'INNER'
echo "── 孤儿进程监控（30s 采样）──"
for i in 1 2 3 4 5 6; do
  n=$(ps -Ao command | grep -cE "worker\.mjs|durable_bridge\.bridge_process" || true)
  echo "  t=$((i*5))s  worker+bridge 进程数 = $n"
  sleep 5
done
echo "[leak watch done — 数字应保持平稳，不持续增长]"
INNER

add unit       "$RUN/w_unit.sh"
add agentroute "$RUN/w_agentroute.sh"
add lifecycle  "$RUN/w_lifecycle.sh"
add daemon     "$RUN/w_daemon.sh"
add soak       "$RUN/w_soak.sh"
add leak       "$RUN/w_leak.sh"

echo
echo "tmux '$S' ready — 全面测试矩阵（main @ b6d35225）"
echo "  attach : tmux attach -t $S"
echo "  windows: 1=agents 2=unit 3=agentroute 4=lifecycle 5=daemon 6=soak 7=leak"
echo "  切换   : Ctrl-b <n>"

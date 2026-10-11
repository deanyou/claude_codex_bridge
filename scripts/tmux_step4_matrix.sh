#!/bin/bash
# Step 4 全面测试矩阵（tmux）
#   w1 semantics  三态语义 + 重启保持 + InMemory 一致性
#   w2 backend    durable_bridge 后端全量
#   w3 bridge     桥进程 + supervisor
#   w4 soak       稳定性 soak 100 轮
set -uo pipefail
S="${1:-step4}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN=/private/tmp/tmux-step4
tmux kill-session -t "$S" 2>/dev/null || true
mkdir -p "$RUN"

add() { # name, script
  if [ "$1" = "semantics" ]; then tmux new-session -d -s "$S" -n "$1" -x 200 -y 50 -c "$REPO"; W=1
  else tmux new-window -t "$S" -n "$1" -c "$REPO"; W=$(tmux list-windows -t "$S" -F '#{window_index} #{window_name}' | awk -v n="$1" '$2==n{print $1}' | tail -1); fi
  tmux send-keys -t "$S:$W" "cd $REPO && export PYTHONPATH=$REPO/lib && clear" Enter; sleep 0.3
  tmux send-keys -t "$S:$W" "bash $2" Enter
  echo "  window $W ($1)"
}

cat > "$RUN/w_semantics.sh" <<'INNER'
python3 /private/tmp/step4_soak_probe.py
echo "[semantics done]"
INNER
add semantics "$RUN/w_semantics.sh"

cat > "$RUN/w_backend.sh" <<'INNER'
echo "── durable_bridge 后端全量 ──"
/usr/local/bin/pytest test/test_durable_bridge_pi_durable.py test/test_durable_bridge_backend_resume.py test/test_durable_bridge_binding_ledger.py test/test_durable_bridge_dispatcher.py test/test_durable_bridge_completion.py test/test_durable_bridge_safety.py test/test_durable_bridge_real_mailbox.py test/test_durable_bridge_server.py test/test_durable_bridge_endpoint.py test/test_durable_bridge_step2_e2e.py test/test_durable_bridge_step4.py test/test_durable_bridge_storage_lock.py test/test_provider_pi_completion_wiring.py test/test_daemon_durable_dispatcher_integration.py test/test_pi_pane_execution.py -q --no-header
echo "[backend done]"
INNER
cat > "$RUN/w_bridge.sh" <<'INNER'
echo "── 桥进程 + supervisor ──"
/usr/local/bin/pytest test/test_durable_bridge_bridge_process.py -q --no-header
echo
echo "── 手工起桥 ──"
python3 -m durable_bridge.bridge_process --storage-path /private/tmp/tmux-step4/bridge.sqlite --endpoint-path /private/tmp/tmux-step4/bridge-ep.json --backend pi_durable &
BR=$!; sleep 3
python3 - <<'PY'
import sys; sys.path.insert(0,"lib")
from pathlib import Path
from durable_bridge.endpoint import read_endpoint
from durable_bridge.tcp_client import DurableBridgeClient
ep = read_endpoint(Path("/private/tmp/tmux-step4/bridge-ep.json"))
c = DurableBridgeClient(ep)
with c: r = c.call("list_conversations", {})
print("  桥 TCP 往返 OK, conversations =", r["result"]["conversations"])
PY
kill $BR 2>/dev/null; wait $BR 2>/dev/null
echo "[bridge done]"
INNER
cat > "$RUN/w_soak.sh" <<'INNER'
echo "── 稳定性 soak 100 轮 ──"
python3 scripts/tmux_soak.py --rounds 100 --workdir /private/tmp/tmux-step4/soak --degrade-ratio 2.5
echo "[soak done]"
INNER

add backend "$RUN/w_backend.sh"
add bridge  "$RUN/w_bridge.sh"
add soak    "$RUN/w_soak.sh"

echo
echo "tmux '$S' ready — Step 4 全面测试"
echo "  attach : tmux attach -t $S"
echo "  windows: 1=semantics 2=backend 3=bridge 4=soak"

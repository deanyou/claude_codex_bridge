#!/bin/bash
# 全面测试矩阵 —— tmux 多 window 并发跑真实生产栈。
#
# window 1 agents   Claude / Codex / pi 三个 agent REPL（分屏）
# window 2 bridge   常驻桥 + durable dispatch 实时观察
# window 3 daemon   daemon 套件测试（含 3'-b durable dispatch）
# window 4 backend  durable_bridge 后端/桥/soak 全量
# window 5 soak     稳定性 soak 100 轮
#
# 用法: bash scripts/tmux_full_matrix.sh [session]
set -uo pipefail

SESSION="${1:-matrix}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN=/private/tmp/tmux-matrix
DAEMON_TESTS="test/test_v2_dispatcher_durable_dispatch.py test/test_v2_dispatcher_queue_fallback.py test/test_daemon_durable_dispatcher_integration.py test/test_cc_bridge_daemon_start_handler.py test/test_reply_delivery_start_completion.py test/test_v2_message_bureau_dispatcher_integration.py"
BACKEND_TESTS="test/test_durable_bridge_pi_durable.py test/test_durable_bridge_bridge_process.py test/test_durable_bridge_backend_resume.py test/test_durable_bridge_binding_ledger.py test/test_durable_bridge_dispatcher.py test/test_durable_bridge_completion.py test/test_durable_bridge_safety.py test/test_durable_bridge_real_mailbox.py test/test_durable_bridge_server.py test/test_durable_bridge_endpoint.py test/test_durable_bridge_step2_e2e.py test/test_durable_bridge_step4.py test/test_durable_bridge_storage_lock.py test/test_provider_pi_completion_wiring.py test/test_daemon_durable_dispatcher_integration.py test/test_pi_pane_execution.py"

tmux kill-session -t "$SESSION" 2>/dev/null || true
mkdir -p "$RUN"

win() {  # $1=name  $2=script-body-file
  tmux new-window -t "$SESSION" -n "$1" -c "$REPO"
  W=$(tmux list-windows -t "$SESSION" -F '#{window_index} #{window_name}' | awk -v n="$1" '$2==n{print $1}' | tail -1)
  tmux send-keys -t "$SESSION:$W" "cd $REPO && export PYTHONPATH=$REPO/lib && clear" Enter
  sleep 0.3
  tmux send-keys -t "$SESSION:$W" "bash $2 $REPO $RUN $SESSION" Enter
  echo "  window $W ($1)"
}

# ---- 1. agents 分屏 ----
tmux new-session -d -s "$SESSION" -n agents -x 240 -y 52 -c "$REPO"
for _ in 1 2 3 4 5; do
  n=$(tmux list-panes -t "$SESSION":1 2>/dev/null | wc -l | tr -d ' ')
  [ "${n:-0}" -ge 4 ] && break
  tmux split-window -h -t "$SESSION":1 >/dev/null 2>&1
done
tmux select-layout -t "$SESSION":1 tiled >/dev/null 2>&1
P=($(tmux list-panes -t "$SESSION":1 -F '#{pane_index}' | sort -n))
for i in 0 1 2; do
  tmux send-keys -t "$SESSION":1."${P[$i]}" "cd $REPO && clear" Enter; sleep 0.3
done
tmux send-keys -t "$SESSION":1."${P[0]}" "claude" Enter
tmux send-keys -t "$SESSION":1."${P[1]}" "codex" Enter
tmux send-keys -t "$SESSION":1."${P[2]}" "pi" Enter
tmux send-keys -t "$SESSION":1."${P[3]}" "echo '── 常驻桥 + durable dispatch 实时观察 ──'; python3 -m durable_bridge.bridge_process --storage-path $RUN/storage.sqlite --endpoint-path $RUN/endpoint.json --backend pi_durable" Enter
echo "  window 1 (agents: Claude/Codex/pi + 桥)"

# ---- 2..5 其余矩阵 ----
cat > "$RUN/w_daemon.sh" <<'INNER'
echo "── daemon 套件（含 3'-b durable dispatch）──"
/usr/local/bin/pytest test/test_v2_dispatcher_durable_dispatch.py -q --no-header
echo
echo "── daemon 回归对比（预期 2 个 pre-existing 失败）──"
/usr/local/bin/pytest test/test_v2_dispatcher_queue_fallback.py test/test_v2_message_bureau_dispatcher_integration.py test/test_daemon_durable_dispatcher_integration.py test/test_cc_bridge_daemon_start_handler.py test/test_reply_delivery_start_completion.py -q --no-header 2>&1 | tail -6
echo "[daemon done]"
INNER
cat > "$RUN/w_backend.sh" <<'INNER'
echo "── durable_bridge 后端/桥 全量 ──"
/usr/local/bin/pytest test/test_durable_bridge_pi_durable.py test/test_durable_bridge_bridge_process.py test/test_durable_bridge_backend_resume.py test/test_durable_bridge_binding_ledger.py test/test_durable_bridge_dispatcher.py test/test_durable_bridge_completion.py test/test_durable_bridge_safety.py test/test_durable_bridge_real_mailbox.py test/test_durable_bridge_server.py test/test_durable_bridge_endpoint.py test/test_durable_bridge_step2_e2e.py test/test_durable_bridge_step4.py test/test_durable_bridge_storage_lock.py test/test_provider_pi_completion_wiring.py test/test_daemon_durable_dispatcher_integration.py test/test_pi_pane_execution.py -q --no-header
echo "[backend done]"
INNER
cat > "$RUN/w_soak.sh" <<'INNER'
echo "── 稳定性 soak 100 轮 ──"
python3 scripts/tmux_soak.py --rounds 100 --workdir "$2/soak" --degrade-ratio 2.5
echo "[soak done]"
INNER

win daemon  "$RUN/w_daemon.sh"
win backend "$RUN/w_backend.sh"
win soak    "$RUN/w_soak.sh"

echo
echo "tmux '$SESSION' ready — 全面测试矩阵"
echo "  attach : tmux attach -t $SESSION"
echo "  windows: 1=agents(Claude/Codex/pi+桥) 2=daemon 3=backend 4=soak"
echo "  切换   : Ctrl-b <n>"

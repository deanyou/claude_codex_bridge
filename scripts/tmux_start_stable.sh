#!/bin/bash
# tmux 稳定运行 harness —— 用 Step 3′ 真实生产栈。
# 用法: bash scripts/tmux_start_stable.sh [session-name]
set -uo pipefail

SESSION="${1:-durable-stable}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN=/private/tmp/tmux-stable

tmux kill-session -t "$SESSION" 2>/dev/null || true
mkdir -p "$RUN"

# ---- window 1: 桥（常驻子进程）+ soak ----
tmux new-session -d -s "$SESSION" -n bridge -x 240 -y 50 -c "$REPO"
tmux send-keys -t "$SESSION":1 "cd $REPO && export PYTHONPATH=$REPO/lib && clear" Enter
sleep 0.4
tmux send-keys -t "$SESSION":1 "echo '=== 桥（真实生产栈: BridgeSupervisor → bridge_process → BridgeServer → PiDurableBackend → Node worker）==='" Enter
sleep 0.3
tmux send-keys -t "$SESSION":1 "python3 -m durable_bridge.bridge_process --storage-path $RUN/storage.sqlite --endpoint-path $RUN/endpoint.json --backend pi_durable" Enter

# ---- window 2: soak 稳定性验证 ----
tmux new-window -t "$SESSION" -n soak -c "$REPO"
tmux send-keys -t "$SESSION":2 "cd $REPO && export PYTHONPATH=$REPO/lib && clear" Enter
sleep 0.4
tmux send-keys -t "$SESSION":2 "echo '=== 稳定性 soak（100 轮 + 重启恢复 + 崩溃 fail-closed）==='" Enter
sleep 0.3
# 注意：tmux 里的默认 shell 可能是 fish/bash/zsh，不能假设 bash 语法。
# 用显式 `bash -c` 包一层，并把命令写进临时脚本，避免引号地狱。
cat > "$RUN/soak_cmd.sh" <<'INNER'
set -uo pipefail
cd "$1"
export PYTHONPATH="$1/lib"
python3 scripts/tmux_soak.py --rounds 100 --workdir "$2/soak" --degrade-ratio 2.5 2>&1 | tee "$2/soak.log"
echo "[soak exit=${PIPESTATUS[0]}]"
INNER
tmux send-keys -t "$SESSION":2 "bash $RUN/soak_cmd.sh $REPO $RUN" Enter

# ---- window 3: 测试套件 ----
tmux new-window -t "$SESSION" -n tests -c "$REPO"
tmux send-keys -t "$SESSION":3 "cd $REPO && export PYTHONPATH=$REPO/lib && clear" Enter
sleep 0.4
tmux send-keys -t "$SESSION":3 "echo '=== durable_bridge 全量测试 ==='" Enter
sleep 0.3
tmux send-keys -t "$SESSION":3 "/usr/local/bin/pytest test/test_durable_bridge_*.py test/test_daemon_durable_dispatcher_integration.py test/test_provider_pi_completion_wiring.py test/test_pi_pane_execution.py -q --no-header" Enter

echo "tmux session '$SESSION' ready."
echo "  attach : tmux attach -t $SESSION"
echo "  windows: bridge(1) soak(2) tests(3)"
echo "  切换  : Ctrl-b <n>   (n=1,2,3)"

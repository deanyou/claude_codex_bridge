#!/bin/bash
# tmux 默认形态：分屏 + agent 对话。
#
# 布局（2x2 分屏，不是 window）：
#   ┌─────────────────────┬─────────────────────┐
#   │ Claude Code         │ Codex               │   ← agent 对话
#   ├─────────────────────┼─────────────────────┤
#   │ pi                  │ 桥 + soak (基础设施)│
#   └─────────────────────┴─────────────────────┘
#
# 用法: bash scripts/tmux_start_agents.sh [session-name]
set -uo pipefail

SESSION="${1:-agents}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN=/private/tmp/tmux-agents

tmux kill-session -t "$SESSION" 2>/dev/null || true
mkdir -p "$RUN"

# ---- 会话 + 2x2 分屏 ----
# 注意：本机 tmux 的 window 索引从 1 开始，不能硬编码 :0
tmux new-session -d -s "$SESSION" -x 240 -y 52 -c "$REPO"
W=$(tmux list-windows -t "$SESSION" -F '#{window_index}' | head -1)
T="$SESSION:$W"

for _ in 1 2 3 4 5 6; do
  n=$(tmux list-panes -t "$T" 2>/dev/null | wc -l | tr -d ' ')
  [ "${n:-0}" -ge 4 ] && break
  tmux split-window -h -t "$T" >/dev/null 2>&1
done
tmux select-layout -t "$T" tiled >/dev/null 2>&1

P=($(tmux list-panes -t "$T" -F '#{pane_index}' | sort -n))
echo "window=$W panes=${P[*]}"

prep() {  # $1=pane index
  tmux send-keys -t "$T"."$1" "cd $REPO && export PYTHONPATH=$REPO/lib && clear" Enter
  sleep 0.35
}

banner() { # $1=pane  $2=text
  tmux send-keys -t "$T"."$1" "echo '$2'" Enter
  sleep 0.25
}

# ---- pane 0: Claude Code ----
prep "${P[0]}"
banner "${P[0]}" "── Claude Code ─────────────────"
tmux send-keys -t "$T"."${P[0]}" "claude" Enter

# ---- pane 1: Codex ----
prep "${P[1]}"
banner "${P[1]}" "── Codex ───────────────────────"
tmux send-keys -t "$T"."${P[1]}" "codex" Enter

# ---- pane 2: pi ----
prep "${P[2]}"
banner "${P[2]}" "── pi ──────────────────────────"
tmux send-keys -t "$T"."${P[2]}" "pi" Enter

# ---- pane 3: 基础设施（常驻桥 + soak）----
prep "${P[3]}"
banner "${P[3]}" "── 基础设施：常驻桥 + 稳定性 soak ──"
cat > "$RUN/infra.sh" <<'INNER'
set -uo pipefail
cd "$1"
export PYTHONPATH="$1/lib"
echo "── 常驻桥（真实生产栈）──"
python3 -m durable_bridge.bridge_process \
  --storage-path "$2/storage.sqlite" \
  --endpoint-path "$2/endpoint.json" \
  --backend pi_durable &
BRIDGE_PID=$!
sleep 2
echo
echo "── 稳定性 soak（80 轮）──"
python3 scripts/tmux_soak.py --rounds 80 --workdir "$2/soak" --degrade-ratio 2.5
echo
echo "── soak 结束，桥继续常驻 (pid=$BRIDGE_PID) ──"
echo "  attach: tmux attach -t $3"
wait $BRIDGE_PID
INNER
tmux send-keys -t "$T"."${P[3]}" "bash $RUN/infra.sh $REPO $RUN $SESSION" Enter

echo "tmux session '$SESSION' ready — 默认分屏 + agent 对话"
echo "  attach : tmux attach -t $SESSION"
echo "  切换   : Ctrl-b <方向键>  或  tmux select-pane -t $T.<n>"
echo "  窗格   : Claude(0)  Codex(1)  pi(2)  基础设施(3)"

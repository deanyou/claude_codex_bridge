#!/usr/bin/env bash
# tmux agent 对话布局选择器
#
# 用法:
#   bash scripts/tmux_agents_layout.sh              # 默认 2x2
#   bash scripts/tmux_agents_layout.sh 1x2          # 2 个 agent 并排 + 下方基础设施
#   bash scripts/tmux_agents_layout.sh 1x3          # 3 个 agent 并排 + 下方基础设施
#   bash scripts/tmux_agents_layout.sh 2x2          # 2x2 四格（3 agent + 1 基础设施）
#
# 环境变量:
#   SESSION=名字           默认 tmux-agents
#   AGENTS="claude codex pi"   agent 列表
#   INFRA=0|1              是否建基础设施窗格（常驻桥），默认 1
set -uo pipefail

LAYOUT="${1:-2x2}"
SESSION="${SESSION:-tmux-agents}"
AGENTS="${AGENTS:-claude codex pi}"
INFRA="${INFRA:-1}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN=/private/tmp/tmux-agents-layout
mkdir -p "$RUN"

case "$LAYOUT" in
  1x2) N_AGENT=2 ;;
  1x3) N_AGENT=3 ;;
  2x2) N_AGENT=3 ;;
  *) echo "用法: $0 [1x2|1x3|2x2]" >&2; exit 2 ;;
esac

read -r -a AGENT_ARR <<< "$AGENTS"
[ "${#AGENT_ARR[@]}" -lt "$N_AGENT" ] && { echo "AGENTS 至少要 $N_AGENT 个" >&2; exit 2; }

TOTAL=$(( N_AGENT + (INFRA == 1 ? 1 : 0) ))

tmux kill-session -t "$SESSION" 2>/dev/null || true
tmux new-session -d -s "$SESSION" -n "$LAYOUT" -x 240 -y 52 -c "$REPO"
W=$(tmux list-windows -t "$SESSION" -F '#{window_index}' | head -1)
T="$SESSION:$W"

# ---- 造出 TOTAL 个窗格 ----
# split -d 让新窗格不自动获得活动焦点
for i in $(seq 2 "$TOTAL"); do
  tmux split-window -d -t "$T" >/dev/null 2>&1
done

# ---- 摆位 ----
# 语义：
#   1x2 = 2 个 agent 横向并排，infra 在下方横跨一行
#   1x3 = 3 个 agent 横向并排，infra 在下方横跨一行
#   2x2 = 2x2 四格（3 agent + 1 infra 放右下）
# INFRA=0 时就是纯 agent 横向并排。
IDS=($(tmux list-panes -t "$T" -F '#{pane_index}' | sort -n))
if [ "$INFRA" != "1" ]; then
  tmux select-layout -t "$T" even-horizontal >/dev/null 2>&1
elif [ "$LAYOUT" = "2x2" ]; then
  tmux select-layout -t "$T" tiled >/dev/null 2>&1
else
  # 1x2 / 1x3：先把 infra 那格拉成整行（main-horizontal = 上下两行），
  # 再让上排均分。tmux 的 main-horizontal 确实是"上下"，与 main-vertical 相反。
  tmux select-layout -t "$T" main-horizontal >/dev/null 2>&1
fi

# ---- 分配内容：按 (top,left) 排序，前面 N 个给 agent，最后一个给 infra ----
# ---- 分配内容 ----
# 1x2 / 1x3 走 main-horizontal 后，横跨整宽的那格落在**上方**（实测），
# 其余等分格在下方。infra 我们要放上方无所谓 —— 关键是不能把 infra
# 和某个 agent 挤进同一格。
#
# 统一策略：按 (top,left) 排序取全部 pane，
#   前 N_AGENT 个 -> agent
#   最后一个     -> infra
# 这样无论 tiled / main-horizontal 怎么摆，都不会有冲突。
P=($(tmux list-panes -t "$T" -F '#{pane_top} #{pane_left} #{pane_index}' \
     | sort -k1,1n -k2,2n | awk '{print $3}'))
INFRA_PANE="${P[${#P[@]}-1]}"

for i in $(seq 0 $((N_AGENT-1))); do
  PIDX="${P[$i]}"; A="${AGENT_ARR[$i]}"
  tmux send-keys -t "$T.$PIDX" "cd $REPO && clear" Enter; sleep 0.3
  tmux send-keys -t "$T.$PIDX" "$A" Enter
done

LAST=$(( ${#P[@]} - 1 ))
if [ "$INFRA" = "1" ]; then
  PIDX="$INFRA_PANE"
  tmux send-keys -t "$T.$PIDX" "cd $REPO && export PYTHONPATH=$REPO/lib && clear" Enter
  sleep 0.3
  tmux send-keys -t "$T.$PIDX" "echo '── 基础设施：常驻桥 ──'" Enter
  sleep 0.3
  BRIDGE_CMD="python3 -m durable_bridge.bridge_process --storage-path $RUN/storage.sqlite --endpoint-path $RUN/endpoint.json --backend pi_durable"
  tmux send-keys -t "$T.$PIDX" "$BRIDGE_CMD" Enter
fi

# ---- attach 落在第一个 agent 上 ----
tmux select-pane -t "$T.${P[0]}" >/dev/null 2>&1
tmux select-window -t "$T" >/dev/null 2>&1

echo
echo "tmux '$SESSION' — 布局 $LAYOUT"
echo "  attach : tmux attach -t $SESSION"
echo "  pane   : $(for i in $(seq 0 $((N_AGENT-1))); do printf '%s=%s ' "${P[$i]}" "${AGENT_ARR[$i]}"; done)$([ "$INFRA" = 1 ] && printf 'infra=%s ' "${P[$LAST]}")"
echo
tmux list-panes -t "$T" -F '    #{pane_index}: x=#{pane_left},#{pane_top} w=#{pane_width} h=#{pane_height}'

#!/usr/bin/env bash
# tmux agent 对话布局选择器（dev/test 工具；非产品入口）
#
# 用法:
#   bash scripts/tmux_agents_layout.sh              # 默认 2x2
#   bash scripts/tmux_agents_layout.sh 1x2          # agent 横向并排 + 下方基础设施
#   bash scripts/tmux_agents_layout.sh 1x3          # agent 横向并排 + 下方基础设施
#   bash scripts/tmux_agents_layout.sh 2x2          # 2×2 四格（3 agent + 1 基础设施）
#
# 修复后几何（round 04 修复）：
#   1x2 / 1x3（默认 INFRA=0）：仅 agent 顶部一排
#                 ┌───────┬───────┐                 ┌─────┬─────┬─────┐
#                 │ a1    │ a2    │                 │ a1  │ a2  │ a3  │
#                 └───────┴───────┘                 └─────┴─────┴─────┘
#   1x2 / 1x3（INFRA=1）：agent 顶部一排 + infra 全宽下方
#                 ┌───────┬───────┐                 ┌─────┬─────┬─────┐
#                 │ a1    │ a2    │                 │ a1  │ a2  │ a3  │
#                 ├───────┴───────┤                 ├─────┴─────┴─────┤
#                 │ infra (full)  │                 │ infra (full)   │
#                 └───────────────┘                 └────────────────┘
#   2x2（默认 INFRA=0）：3 agent 2×2 网格
#   2x2（INFRA=1）        ：3 agent + 1 infra 在 2×2 网格
#
# 环境变量:
#   SESSION=名字           默认 tmux-agents
#   AGENTS="claude codex pi"   agent 列表（必须 ≥ 1x2 / 1x3 / 2x2 所需）
#   INFRA=0|1              是否建基础设施窗格（常驻桥），默认 0
#                            INFRA=1 时 1x2/1x3 顶部排 agent + 底部全宽 infra；
#                            2x2 时 3 agent + 1 infra 填右下格。占面积，默认不开。
set -uo pipefail

LAYOUT="${1:-2x2}"
SESSION="${SESSION:-tmux-agents}"
AGENTS="${AGENTS:-claude codex pi}"
INFRA="${INFRA:-0}"
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

tmux kill-session -t "$SESSION" 2>/dev/null || true

# ---- 造空窗口：top 占满全宽，作为 agent 行的根 ----
tmux new-session -d -s "$SESSION" -n "$LAYOUT" -x 240 -y 52 -c "$REPO"
W=$(tmux list-windows -t "$SESSION" -F '#{window_index}' | head -1)
T="$SESSION:$W"

# pane_root = 根 pane（顶部、全宽；1x2/1x3 时先变成 infra + 上排）
PANE_ROOT=$(tmux list-panes -t "$T" -F '#{pane_id}' | head -1)

# 显式 split 序列（不再依赖 main-horizontal + 坐标排序）：
# 步骤 A：先把根 pane 用 -v 切成上 + 下两行，下行就是 infra（占满全宽）
# 步骤 B：把上排根 pane 用 -h 切成 N-1 个 agent 列
PANES=("$PANE_ROOT")  # 已知 pane id 列表（按构建顺序）

if [ "$LAYOUT" = "2x2" ]; then
  # 2×2：直接 tiled。INFRA=1 时多一个 pane 放右下；INFRA=0 时 3 pane 填 2×2 (留一格空)
  PANES+=($(tmux split-window -d -t "$T" -P -F '#{pane_id}' 2>/dev/null))
  PANES+=($(tmux split-window -d -t "$T" -P -F '#{pane_id}' 2>/dev/null))
  if [ "$INFRA" = "1" ]; then
    PANES+=($(tmux split-window -d -t "$T" -P -F '#{pane_id}' 2>/dev/null))
  fi
  tmux select-layout -t "$T" tiled >/dev/null 2>&1
else
  # 1x2 / 1x3：INFRA=1 时先做步骤 A（infra 全宽下方）；INFRA=0 时直接做步骤 B
  if [ "$INFRA" = "1" ]; then
    PANES+=($(tmux split-window -v -t "$PANE_ROOT" -P -F '#{pane_id}' 2>/dev/null))
  fi
  # 步骤 B：上排多 agent 列。把 Pane_root 用 -h 切 N_AGENT-1 次。
  PREV="$PANE_ROOT"
  for _ in $(seq 2 "$N_AGENT"); do
    NEW=$(tmux split-window -h -t "$PREV" -P -F '#{pane_id}' 2>/dev/null)
    PANES+=("$NEW")
    PREV="$NEW"
  done
fi

# ---- 内容分配 ----
# PANES 顺序：
#   2x2：[root, split1, split2, split3] → 全 4 个 pane
#   1x2 / 1x3：[root, infra, agent2, agent3, ...]
# 我们按位置固定映射（不再按 sort 倒序依赖）：
#   2x2：P[0..N-1] = agent 0..N-1, P[N] = infra (在 2x2 网格的右下)
#   1x2 / 1x3：P[0] = agent 0 (top-left), P[1] = infra (bottom full-width),
#            P[2..] = agent 1..N-1 (top row columns)
# bash 3.2 兼容性：不用 declare -A，改用两个平行数组 + 固定顺序遍历。
PANE_NAMES=()
PANE_IDS=()
if [ "$LAYOUT" = "2x2" ]; then
  for i in $(seq 0 $((N_AGENT-1))); do
    PANE_NAMES+=("${AGENT_ARR[$i]}")
    PANE_IDS+=("${PANES[$i]}")
  done
  if [ "$INFRA" = "1" ]; then
    PANE_NAMES+=("infra")
    PANE_IDS+=("${PANES[$N_AGENT]}")
  fi
else
  # 1x2 / 1x3：root=agent0, [1]=infra, [2..]=agent1..
  PANE_NAMES+=("${AGENT_ARR[0]}")
  PANE_IDS+=("${PANES[0]}")
  idx=1
  if [ "$INFRA" = "1" ]; then
    PANE_NAMES+=("infra")
    PANE_IDS+=("${PANES[$idx]}")
    idx=$((idx + 1))
  fi
  for i in $(seq 1 $((N_AGENT-1))); do
    PANE_NAMES+=("${AGENT_ARR[$i]}")
    PANE_IDS+=("${PANES[$idx]}")
    idx=$((idx + 1))
  done
fi

# ---- 启动 agent ----
for i in $(seq 0 $((${#PANE_NAMES[@]}-1))); do
  AGENT_NAME="${PANE_NAMES[$i]}"
  PID="${PANE_IDS[$i]}"
  if [ "$AGENT_NAME" = "infra" ]; then
    tmux send-keys -t "$T.$PID" "cd $REPO && export PYTHONPATH=$REPO/lib && clear" Enter
    sleep 0.3
    tmux send-keys -t "$T.$PID" "echo '── 基础设施：常驻桥 ──'" Enter
    sleep 0.3
    BRIDGE_CMD="python3 -m durable_bridge.bridge_process --storage-path $RUN/storage.sqlite --endpoint-path $RUN/endpoint.json --backend pi_durable"
    tmux send-keys -t "$T.$PID" "$BRIDGE_CMD" Enter
  else
    tmux send-keys -t "$T.$PID" "cd $REPO && clear" Enter; sleep 0.3
    tmux send-keys -t "$T.$PID" "$AGENT_NAME" Enter
  fi
done

# ---- attach 落在第一个 agent pane ----
FIRST_AGENT_PANE="${PANE_IDS[0]}"
tmux select-pane -t "$T.$FIRST_AGENT_PANE" >/dev/null 2>&1
tmux select-window -t "$T" >/dev/null 2>&1

# ---- 报告 ----
echo
echo "tmux '$SESSION' — 布局 $LAYOUT"
echo "  attach : tmux attach -t $SESSION"
PANE_SUMMARY=""
for i in $(seq 0 $((${#PANE_NAMES[@]}-1))); do
  PANE_SUMMARY+="${PANE_NAMES[$i]}=${PANE_IDS[$i]} "
done
echo "  pane   : $PANE_SUMMARY"
echo
tmux list-panes -t "$T" -F '    #{pane_index}: x=#{pane_left},#{pane_top} w=#{pane_width} h=#{pane_height}'
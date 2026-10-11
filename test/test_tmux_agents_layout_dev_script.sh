#!/usr/bin/env bash
# test_tmux_agents_layout_dev_script.sh —— 几何回归测试
#
# 验证 scripts/tmux_agents_layout.sh 几何符合 spec：
#   默认 INFRA=0（不占面积）：
#     1x2 / 1x3：N 个 agent 顶部一排，全高（无底部 infra 行）
#     2x2    ：3 agent 2×2 网格（INFRA=0 时右下角空）
#   显式 INFRA=1（与上次 commit `fbd3e61e` 行为一致）：
#     1x2 / 1x3：N 个 agent 顶部一排 + 1 个 infra 全宽下方
#     2x2    ：3 agent + 1 infra 在 2×2 网格
#
# 这是 dev 脚本（scripts/），非产品路径。复测即回归。

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/tmux_agents_layout.sh"

PASS=0
FAIL=0

assert_eq() {
  local desc="$1"; local expected="$2"; local actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    PASS=$((PASS+1)); printf '  ✓ %s\n' "$desc"
  else
    FAIL=$((FAIL+1)); printf '  ✗ %s\n      expected: %q\n      actual:   %q\n' "$desc" "$expected" "$actual"
  fi
}

# 计算几何关键属性 + 断言
geometry_assert() {
  local layout="$1"
  local infra="$2"   # 0 或 1
  local session="geom-test-${layout}-infra${infra}-$$"
  local n_panes expected_panes expected_unique_tops expected_left_count expected_first_pane_height

  if [ "$infra" = "1" ]; then
    case "$layout" in
      1x2) expected_panes=3; expected_unique_tops=2; expected_left_count=2 ;;
      1x3) expected_panes=4; expected_unique_tops=2; expected_left_count=3 ;;
      2x2) expected_panes=4; expected_unique_tops=2; expected_left_count=2 ;;
    esac
    expected_first_pane_height=""   # INFRA=1 时 top-row 被下方均分，高度小于全高
  else
    case "$layout" in
      1x2) expected_panes=2; expected_unique_tops=1; expected_left_count=2 ;;
      1x3) expected_panes=3; expected_unique_tops=1; expected_left_count=3 ;;
      2x2) expected_panes=3; expected_unique_tops=2; expected_left_count=2 ;;  # tiled: 2 panes top, 1 pane bottom full-width
    esac
    expected_first_pane_height=52   # INFRA=0 时 1x2/1x3 全高
  fi

  SESSION="$session" AGENTS="claude codex pi" INFRA="$infra" bash "$SCRIPT" "$layout" >/dev/null 2>&1

  geo=$(tmux list-panes -t "$session" -F '#{pane_top} #{pane_left} #{pane_width} #{pane_height}')
  n_panes=$(echo "$geo" | wc -l | tr -d ' ')
  unique_tops=$(echo "$geo" | awk '{print $1}' | sort -u | wc -l | tr -d ' ')
  top_value=$(echo "$geo" | awk '{print $1}' | sort -u | head -1)
  top_lefts_unique=$(echo "$geo" | awk -v t="$top_value" '$1==t{print $2}' | sort -u | wc -l | tr -d ' ')

  echo "=== $layout INFRA=$infra (session=$session) ==="
  echo "$geo" | awk '{printf "    top=%s left=%s w=%s h=%s\n", $1, $2, $3, $4}'

  assert_eq "$layout INFRA=$infra pane count" "$expected_panes" "$n_panes"
  assert_eq "$layout INFRA=$infra unique_tops" "$expected_unique_tops" "$unique_tops"
  assert_eq "$layout INFRA=$infra top_row column count" "$expected_left_count" "$top_lefts_unique"

  # INFRA=0 时 1x2/1x3 应满高（无底部 infra 行）
  if [ "$infra" = "0" ] && [ "$layout" != "2x2" ]; then
    first_h=$(echo "$geo" | head -1 | awk '{print $4}')
    assert_eq "$layout INFRA=$infra first pane full-height" "$expected_first_pane_height" "$first_h"
  fi

  # INFRA=1 时 1x2/1x3 应有底部全宽 infra（bottom row width 接近 top_max_w 的两倍以上）
  if [ "$infra" = "1" ] && [ "$layout" != "2x2" ]; then
    top_max_w=$(echo "$geo" | awk -v t="$top_value" '$1==t{print $3}' | sort -n | tail -1)
    bottom_w=$(echo "$geo" | awk -v t="$top_value" '$1!=t{print $3}' | head -1)
    if [[ -n "$bottom_w" && "$bottom_w" -gt "$top_max_w" ]]; then
      PASS=$((PASS+1)); printf '  ✓ %s INFRA=1: infra pane full-width (w=%s > top_max_w=%s)\n' "$layout" "$bottom_w" "$top_max_w"
    else
      FAIL=$((FAIL+1)); printf '  ✗ %s INFRA=1: infra pane NOT full-width (w=%s vs top_max_w=%s)\n' "$layout" "$bottom_w" "$top_max_w"
    fi
  fi

  tmux kill-session -t "$session" 2>/dev/null
}

echo "=== scripts/tmux_agents_layout.sh 几何回归（默认 INFRA=0）==="
geometry_assert 1x2 0
geometry_assert 1x3 0
geometry_assert 2x2 0

echo
echo "=== 显式 INFRA=1 仍然支持 ==="
geometry_assert 1x2 1
geometry_assert 1x3 1
geometry_assert 2x2 1

echo
echo "============================================"
echo "  dev script geometry: PASS=$PASS FAIL=$FAIL"
echo "============================================"
[[ "$FAIL" -eq 0 ]]
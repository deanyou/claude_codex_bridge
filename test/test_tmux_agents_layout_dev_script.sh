#!/usr/bin/env bash
# test_tmux_agents_layout_dev_script.sh —— round 04 修复 B 后的几何回归测试
#
# 验证 scripts/tmux_agents_layout.sh 的几何符合 spec：
#   1x2 / 1x3：N 个 agent 顶部一排 + 1 个 infra 全宽下方
#   2x2     ：3 agent + 1 infra 2×2 网格（保持原行为）
#
# 这是 dev 脚本（scripts/），非产品路径。复测即回归。

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/tmux_agents_layout.sh"

PASS=0
FAIL=0

assert_ok() {
  if [[ "$1" == "0" ]]; then
    PASS=$((PASS+1)); printf '  ✓ %s\n' "$2"
  else
    FAIL=$((FAIL+1)); printf '  ✗ %s (rc=%s)\n' "$2" "$1"
  fi
}

# 计算几何关键属性：
#   - tops_sorted: 排序后的 top 坐标，用于判 unique_top 数
#   - lefts_sorted: 排序后的 left 坐标
#   - n_panes: pane 总数
geometry_assert() {
  local layout="$1"
  local session="geom-test-$layout-$$"
  local n_panes expected_panes expected_unique_tops expected_left_count

  case "$layout" in
    1x2) expected_panes=3; expected_unique_tops=2; expected_left_count=2 ;;  # 2 agent top row + 1 infra bottom full-width
    1x3) expected_panes=4; expected_unique_tops=2; expected_left_count=3 ;;  # 3 agent top row + 1 infra bottom full-width
    2x2) expected_panes=4; expected_unique_tops=2; expected_left_count=2 ;;  # 2x2 grid: 2 cols, 2 rows
  esac

  SESSION="$session" AGENTS="claude codex pi" INFRA=1 bash "$SCRIPT" "$layout" >/dev/null 2>&1

  # 拉 pane 几何
  geo=$(tmux list-panes -t "$session" -F '#{pane_top} #{pane_left} #{pane_width} #{pane_height}')
  n_panes=$(echo "$geo" | wc -l | tr -d ' ')

  # 排序后的 unique top 数（应是 1 表示所有 pane 同 row；2 表示 2x2）
  unique_tops=$(echo "$geo" | awk '{print $1}' | sort -u | wc -l | tr -d ' ')

  # top row 内的 unique left 数（用于 1x2/1x3 横向断言）
  top_value=$(echo "$geo" | awk '{print $1}' | sort -u | head -1)
  top_lefts_unique=$(echo "$geo" | awk -v t="$top_value" '$1==t{print $2}' | sort -u | wc -l | tr -d ' ')

  echo "=== $layout (session=$session) ==="
  echo "  panes:"
  echo "$geo" | awk '{printf "    top=%s left=%s w=%s h=%s\n", $1, $2, $3, $4}'
  echo "  → n_panes=$n_panes (expected $expected_panes)"
  echo "  → unique_tops=$unique_tops (expected $expected_unique_tops)"
  echo "  → top_row_unique_lefts=$top_lefts_unique (expected $expected_left_count)"

  # 断言
  if [[ "$n_panes" == "$expected_panes" ]]; then
    PASS=$((PASS+1)); printf '  ✓ %s: pane count\n' "$layout"
  else
    FAIL=$((FAIL+1)); printf '  ✗ %s: pane count (got %s, want %s)\n' "$layout" "$n_panes" "$expected_panes"
  fi

  if [[ "$unique_tops" == "$expected_unique_tops" ]]; then
    PASS=$((PASS+1)); printf '  ✓ %s: unique_tops\n' "$layout"
  else
    FAIL=$((FAIL+1)); printf '  ✗ %s: unique_tops (got %s, want %s)\n' "$layout" "$unique_tops" "$expected_unique_tops"
  fi

  if [[ "$top_lefts_unique" == "$expected_left_count" ]]; then
    PASS=$((PASS+1)); printf '  ✓ %s: top row column count\n' "$layout"
  else
    FAIL=$((FAIL+1)); printf '  ✗ %s: top row column count (got %s, want %s)\n' "$layout" "$top_lefts_unique" "$expected_left_count"
  fi

  # 1x2/1x3 还要断言：底部 row 是 full-width（width >= 上面最大宽度）
  if [[ "$layout" == "1x2" || "$layout" == "1x3" ]]; then
    bottom_w=$(echo "$geo" | awk -v t="$top_value" '$1!=t{print $3}' | head -1)
    top_max_w=$(echo "$geo" | awk -v t="$top_value" '$1==t{print $3}' | sort -n | tail -1)
    if [[ -n "$bottom_w" && "$bottom_w" -gt "$top_max_w" ]]; then
      PASS=$((PASS+1)); printf '  ✓ %s: infra pane full-width (w=%s > top_max_w=%s)\n' "$layout" "$bottom_w" "$top_max_w"
    else
      FAIL=$((FAIL+1)); printf '  ✗ %s: infra pane NOT full-width (w=%s vs top_max_w=%s)\n' "$layout" "$bottom_w" "$top_max_w"
    fi
  fi

  tmux kill-session -t "$session" 2>/dev/null
}

echo "=== scripts/tmux_agents_layout.sh 几何回归 ==="
geometry_assert 1x2
geometry_assert 1x3
geometry_assert 2x2

echo
echo "============================================"
echo "  dev script geometry: PASS=$PASS FAIL=$FAIL"
echo "============================================"
[[ "$FAIL" -eq 0 ]]
#!/usr/bin/env bash
# verify_install_tmux_layout.sh —— 真实 tmux 集成：安装器写完 layout 后，启动链路读出
# 的 spec 在真实 tmux session 里造出对应几何。
#
# 注意：
# - 真实启动路径是 `cc-bridge <project>`；本脚本不依赖 daemon，**直接调既有
#   ``prepare_tmux_start_layout``**（已读 ``config.layout_spec``），构造最小
#   ``ProjectConfig`` + ``LayoutNode``，用临时 tmux socket 隔离真实布局。
# - 这一路径是 spec 验收第 5 条（"真实启动后的 pane 几何符合"）。
# - 1x2 = 2 panes, 1x3 = 3 panes, 2x2 = 4 panes。

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN=""

# Find Python
for cmd in python3.13 python3.12 python3.11 python3.10 python3 python; do
  if command -v "$cmd" >/dev/null 2>&1; then
    PYTHON_BIN="$cmd"
    break
  fi
done
if [[ -z "$PYTHON_BIN" ]]; then
  echo "FATAL: no python3 found" >&2
  exit 99
fi

# Find tmux
if ! command -v tmux >/dev/null 2>&1; then
  echo "FATAL: tmux not installed" >&2
  exit 99
fi

# Unique tmux socket per run to avoid stepping on real session
SOCKET="verify-install-tmux-layout-$$"
TMPDIR="$(mktemp -d -t cc-bridge-verify.XXXXXX)"
trap 'tmux -L "$SOCKET" kill-server 2>/dev/null || true; rm -rf "$TMPDIR"' EXIT

PASS=0
FAIL=0
assert_ok() {
  local desc="$1"; local rc="$2"
  if [[ "$rc" -eq 0 ]]; then
    PASS=$((PASS+1)); printf '  ✓ %s\n' "$desc"
  else
    FAIL=$((FAIL+1)); printf '  ✗ %s (rc=%d)\n' "$desc" "$rc"
  fi
}

# Helper: 跑一段 Python 调既有 ``prepare_tmux_start_layout``，返回 pane 数。
verify_layout() {
  local shorthand="$1"
  shift
  local agents=("$@")
  PYTHONPATH="$REPO_ROOT/lib" "$PYTHON_BIN" - "$shorthand" "${agents[@]}" <<'PYEOF'
import sys
import subprocess
import time

shorthand = sys.argv[1]
agents = sys.argv[2:]

from cli.services.tmux_layout_shorthand import translate
spec = translate(shorthand, agents)

from agents.config_loader_runtime.io_runtime.documents import (
    load_project_config,
    parse_config_document_text,
)
from pathlib import Path

# Construct ``ConfigDocument`` directly (not via disk)
parsed = parse_config_document_text(spec + "\n", path=Path("(verify)"))

# Build ProjectConfig dataclass — use minimal subset for layout pipeline
from dataclasses import fields
from agents.models_runtime.config_runtime.project import (
    ProjectConfig as _RealProjectConfig,
)

# Build via the existing validator to keep the schema consistent
from agents.config_loader_runtime.parsing import validate_project_config
from agents.models_runtime.config import ProjectConfig

config = validate_project_config(parsed, source_path=Path("(verify)"))
project_root = Path("(verify)")

# Run the actual start layout pipeline in a real tmux session via a temp socket
socket_name = f"verify-install-tmux-layout-{shorthand.replace('x', 'x')}"

# Create session + root pane
subprocess.run(["tmux", "-L", socket_name, "new-session", "-d", "-s", "verify", "-x", "240", "-y", "52"], check=True)
try:
    from cli.services.tmux_start_layout import prepare_tmux_start_layout
    from cli.context import CliContext
    from cli.services.tmux_start_layout import TmuxStartLayout

    # Use the real backend pointing at our isolated socket
    from terminal_runtime import TmuxBackend

    class _CtxProxy:
        def __init__(self):
            self.project = type("P", (), {
                "project_id": "verify",
                "project_root": project_root,
            })()
        # context.project needs to be an attribute or context arg compatibility
        def __getattr__(self, name):
            return getattr(self.project, name)

    backend = TmuxBackend(socket_name=socket_name)
    root_pane_id = backend.get_current_pane_id() if False else None

    # No current pane (we're not inside tmux); use explicit root via list-panes
    import re
    out = subprocess.run(
        ["tmux", "-L", socket_name, "list-panes", "-t", "verify", "-F", "#{pane_id}"],
        capture_output=True, text=True, check=True,
    )
    root_pane_id = out.stdout.strip().splitlines()[0]
    assert root_pane_id.startswith("%"), f"bad pane id: {root_pane_id!r}"

    layout = prepare_tmux_start_layout(
        _CtxProxy(),
        config=config,
        targets=tuple(agents),
        tmux_backend=backend,
        root_pane_id=root_pane_id,
        window_name="verify",
    )

    # Now count panes in the verify session
    out = subprocess.run(
        ["tmux", "-L", socket_name, "list-panes", "-t", "verify", "-F", "#{pane_id}"],
        capture_output=True, text=True, check=True,
    )
    pane_ids = [p for p in out.stdout.strip().splitlines() if p.startswith("%")]
    print(f"VISIBLE_PANES={len(pane_ids)}")
    print(f"AGENT_PANES={len(layout.agent_panes)}")
    print(f"SPEC={spec}")
    print(f"AGENT_KEYS={','.join(sorted(layout.agent_panes.keys()))}")
    # Verify each agent got a real pane_id
    for agent in agents:
        if agent not in layout.agent_panes:
            print(f"MISSING_AGENT={agent}")
            sys.exit(2)

    # Geometry: list-panes with # pane_top / # pane_left for audit assertions
    geo_out = subprocess.run(
        ["tmux", "-L", socket_name, "list-panes", "-t", "verify", "-F", "#{pane_id} #{pane_top} #{pane_left} #{pane_width} #{pane_height}"],
        capture_output=True, text=True, check=True,
    )
    pane_geo = {}
    for line in geo_out.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) >= 5:
            pane_geo[parts[0]] = {
                "top": int(parts[1]),
                "left": int(parts[2]),
                "width": int(parts[3]),
                "height": int(parts[4]),
            }
    # 输出 pane geometry summary for the outer harness to assert on
    tops = ",".join(str(pane_geo[p]["top"]) for p in pane_ids if p in pane_geo)
    lefts = ",".join(str(pane_geo[p]["left"]) for p in pane_ids if p in pane_geo)
    print(f"PANE_TOPS={tops}")
    print(f"PANE_LEFTS={lefts}")

    # Provider mapping: each agent_panes[k] should point to a real pane
    for agent, pane_id in layout.agent_panes.items():
        if pane_id not in pane_geo:
            print(f"MISSING_PANE_FOR_AGENT={agent}:{pane_id}")
            sys.exit(2)
    print("PROVIDER_MAPPING_OK=1")
finally:
    subprocess.run(["tmux", "-L", socket_name, "kill-server"], capture_output=True)
PYEOF
}

echo "=== 真实 tmux 集成：安装期 layout → 启动链路几何 ==="

for layout in 1x2 1x3 2x2; do
  case "$layout" in
    1x2) agents=(claude codex); expected=2 ;;
    1x3) agents=(claude codex pi); expected=3 ;;
    2x2) agents=(claude codex pi demo); expected=4 ;;
  esac
  echo
  echo "--- $layout (${agents[*]}) ---"
  out="$(verify_layout "$layout" "${agents[@]}" 2>&1)"
  rc=$?
  assert_ok "$layout: pipeline runs" "$rc"
  visible="$(echo "$out" | grep -E '^VISIBLE_PANES=' | head -1 | cut -d= -f2)"
  if [[ -n "$visible" ]]; then
    assert_ok "$layout: visible_panes=$visible (expected $expected)" "$([[ "$visible" == "$expected" ]] && echo 0 || echo 1)"
  else
    FAIL=$((FAIL+1)); printf '  ✗ %s: no VISIBLE_PANES line\n' "$layout"
  fi
  agent_panes="$(echo "$out" | grep -E '^AGENT_PANES=' | head -1 | cut -d= -f2)"
  if [[ -n "$agent_panes" ]]; then
    assert_ok "$layout: agent_panes=$agent_panes (expected $expected)" "$([[ "$agent_panes" == "$expected" ]] && echo 0 || echo 1)"
  fi

  # Geometry assertions
  pane_tops="$(echo "$out" | grep -E '^PANE_TOPS=' | head -1 | cut -d= -f2)"
  pane_lefts="$(echo "$out" | grep -E '^PANE_LEFTS=' | head -1 | cut -d= -f2)"
  case "$layout" in
    1x2|1x3)
      # 所有 pane 同一行（top 值唯一）
      unique_tops="$(echo "$pane_tops" | tr ',' '\n' | sort -u | wc -l | tr -d ' ')"
      assert_ok "$layout: horizontal (1 row) — unique tops=$unique_tops" "$([[ "$unique_tops" == "1" ]] && echo 0 || echo 1)"
      # pane 顺序按 left 递増
      left_seq_ok=0
      prev_left=-1
      for l in $(echo "$pane_lefts" | tr ',' ' '); do
        if [[ "$l" -le "$prev_left" && "$prev_left" -ge 0 ]]; then
          left_seq_ok=1
          break
        fi
        prev_left="$l"
      done
      assert_ok "$layout: panes ordered by left (horizontal)" "$left_seq_ok"
      ;;
    2x2)
      # 上排 2 个 + 下排 2 个 = 2 个不同 top
      unique_tops="$(echo "$pane_tops" | tr ',' '\n' | sort -u | wc -l | tr -d ' ')"
      assert_ok "$layout: 2 rows (top) — unique_tops=$unique_tops" "$([[ "$unique_tops" == "2" ]] && echo 0 || echo 1)"
      ;;
  esac

  # Provider mapping
  provider_ok="$(echo "$out" | grep -E '^PROVIDER_MAPPING_OK=' | head -1 | cut -d= -f2)"
  assert_ok "$layout: provider → pane mapping OK" "$([[ "$provider_ok" == "1" ]] && echo 0 || echo 1)"

  missing="$(echo "$out" | grep -E '^MISSING_AGENT=' | head -1)"
  if [[ -z "$missing" ]]; then
    PASS=$((PASS+1)); printf '  ✓ %s: all agents have pane\n' "$layout"
  else
    FAIL=$((FAIL+1)); printf '  ✗ %s: missing agent %s\n' "$layout" "$missing"
  fi
done

echo
echo "============================================"
echo "  real tmux verify: PASS=$PASS FAIL=$FAIL"
echo "============================================"
[[ "$FAIL" -eq 0 ]]
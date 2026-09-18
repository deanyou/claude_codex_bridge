from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = REPO_ROOT / "mcp" / "cc_bridge-delegation" / "server.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("cc_bridge_delegation_server", SERVER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mcp_delegation_server_exposes_agent_first_tools() -> None:
    module = _load_module()
    tool_names = {tool["name"] for tool in module.TOOL_DEFS}

    assert {"cc_bridge_ask_agent", "cc_bridge_pend_agent", "cc_bridge_ping_agent"} <= tool_names
    assert "cc_bridge_ask_codex" not in tool_names
    assert "cask" not in tool_names

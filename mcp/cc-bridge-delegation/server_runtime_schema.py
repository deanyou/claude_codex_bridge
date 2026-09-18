from __future__ import annotations

from typing import Any


def ask_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "agent_name": {
                "type": "string",
                "description": "Target agent name from .cc-bridge/cc_bridge.config.",
            },
            "message": {
                "type": "string",
                "description": "Request text to send to the target agent.",
            },
            "work_dir": {
                "type": "string",
                "description": "Project work directory that contains .cc-bridge/cc_bridge.config.",
            },
            "task_id": {
                "type": "string",
                "description": "Optional logical task id for correlation.",
            },
            "reply_to": {
                "type": "string",
                "description": "Optional job id to use as reply_to correlation.",
            },
        },
        "required": ["agent_name", "message"],
    }


def pend_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "A job_id or agent name to inspect.",
            },
            "work_dir": {
                "type": "string",
                "description": "Project work directory that contains .cc-bridge/cc_bridge.config.",
            },
        },
        "required": ["target"],
    }


def ping_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Agent name, all, or cc_bridge_daemon.",
                "default": "cc_bridge_daemon",
            },
            "work_dir": {
                "type": "string",
                "description": "Project work directory that contains .cc-bridge/cc_bridge.config.",
            },
        },
        "required": [],
    }


TOOL_DEFS = [
    {
        "name": "cc_bridge_ask_agent",
        "description": "Submit a request to a named CC_BRIDGE agent.",
        "inputSchema": ask_schema(),
    },
    {
        "name": "cc_bridge_pend_agent",
        "description": "Inspect the latest state/reply for a named agent or job.",
        "inputSchema": pend_schema(),
    },
    {
        "name": "cc_bridge_ping_agent",
        "description": "Check cc_bridge_daemon or mounted-agent health inside the current project.",
        "inputSchema": ping_schema(),
    },
]


__all__ = ['TOOL_DEFS']

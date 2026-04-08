from __future__ import annotations

import json
import os
from typing import Any


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(CURRENT_DIR, "mcp_manifest.json")


def load_mcp_manifest() -> dict[str, Any]:
    if not os.path.exists(MANIFEST_PATH):
        return {"mcp_connections": []}
    with open(MANIFEST_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def get_active_mcp_summary() -> list[dict[str, Any]]:
    manifest = load_mcp_manifest()
    return [
        item
        for item in manifest.get("mcp_connections", [])
        if item.get("status") in {"active-by-code", "planned"}
    ]


def build_case_memory_mcp(
    *,
    case_id: str,
    payload: dict[str, Any],
    history: list[dict[str, Any]] | None = None,
    current_question: str | None = None,
) -> dict[str, Any]:
    history = history or []
    top_markers = payload.get("derived_features", {}).get("top_abnormal_markers", [])[:4]
    next_steps = payload.get("report_agent_output", {}).get("recommended_next_steps", [])[:4]
    monitoring = payload.get("report_agent_output", {}).get("monitoring_priorities", [])[:4]
    recent_turns = [
        {
            "user_message": item.get("user_message", ""),
            "assistant_message": item.get("assistant_message", ""),
            "created_at": item.get("created_at"),
        }
        for item in history[-4:]
    ]
    return {
        "name": "local_case_memory_mcp",
        "case_id": case_id,
        "patient_name": payload.get("case_metadata", {}).get("patient_name"),
        "current_question": current_question or "",
        "recent_turns": recent_turns,
        "remembered_monitoring_priorities": monitoring,
        "remembered_next_steps": next_steps,
        "remembered_measured_markers": [
            {
                "feature": item.get("feature"),
                "value": item.get("value"),
                "reference_range": item.get("reference_range"),
                "status": item.get("status"),
            }
            for item in top_markers
        ],
        "status": "active-by-code",
    }

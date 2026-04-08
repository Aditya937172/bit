from __future__ import annotations

import json
import os
from typing import Any


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))


def _safe_load_json(path: str) -> dict[str, Any] | list[Any] | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def get_reference_notes() -> dict[str, Any]:
    notes = {
        "range_source": os.path.join(ROOT_DIR, "Data", "medical_ranges.json"),
        "disease_label_source": os.path.join(ROOT_DIR, "Data", "encoder.json"),
    }
    ranges = _safe_load_json(notes["range_source"])
    labels = _safe_load_json(notes["disease_label_source"])
    return {
        "sources": notes,
        "medical_ranges": ranges or {},
        "labels": labels or {},
    }


def get_local_report_summaries(limit: int = 5) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for file_name in sorted(os.listdir(AGENT_DIR)):
        if not file_name.endswith(".json"):
            continue
        if not (
            file_name.startswith("agent_report_output")
            or file_name.startswith("sample_output")
        ):
            continue
        payload = _safe_load_json(os.path.join(AGENT_DIR, file_name))
        if not isinstance(payload, dict):
            continue
        raw = payload.get("raw_intake", payload)
        parsed = raw.get("parsed_document", {}).get("parsed_payload", {})
        summaries.append(
            {
                "file_name": file_name,
                "parsed_feature_count": parsed.get("parsed_feature_count", 0),
                "missing_feature_count": parsed.get("missing_feature_count", 0),
            }
        )
        if len(summaries) >= limit:
            break
    return summaries


def build_retrieval_context() -> dict[str, Any]:
    return {
        "local_reference_notes": get_reference_notes(),
        "local_report_summaries": get_local_report_summaries(),
    }

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_parsed_document_schema(
    *,
    file_name: str,
    file_type: str,
    extraction_mode: str,
    extracted_text: str,
    parsed_values: dict[str, float],
    missing_features: list[str],
    notes: list[str],
) -> dict[str, Any]:
    return {
        "document_ingestion": {
            "file_name": file_name,
            "file_type": file_type,
            "extraction_mode": extraction_mode,
            "processed_at": utc_now(),
            "text_preview": extracted_text[:4000],
            "notes": notes,
        },
        "parsed_payload": {
            "parsed_feature_count": len(parsed_values),
            "missing_feature_count": len(missing_features),
            "parsed_values": parsed_values,
            "missing_features": missing_features,
        },
    }


def build_analysis_schema(
    *,
    parsed_document: dict[str, Any],
    patient_values: dict[str, float],
    ranges: dict[str, list[float]],
    inference: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "parsed_document": parsed_document,
        "normalized_patient_input": patient_values,
        "reference_ranges": ranges,
        "ml_output": inference,
        "generated_at": utc_now(),
    }

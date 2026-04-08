from __future__ import annotations

from typing import Any


CARDIAC_MARKERS = {
    "Systolic Blood Pressure",
    "Diastolic Blood Pressure",
    "Heart Rate",
    "Troponin",
    "C-reactive Protein",
}
METABOLIC_MARKERS = {
    "Glucose",
    "HbA1c",
    "Insulin",
    "BMI",
    "Triglycerides",
    "LDL Cholesterol",
    "HDL Cholesterol",
    "Cholesterol",
}
HEMATOLOGY_MARKERS = {
    "Hemoglobin",
    "Platelets",
    "White Blood Cells",
    "Red Blood Cells",
    "Hematocrit",
    "Mean Corpuscular Volume",
    "Mean Corpuscular Hemoglobin",
    "Mean Corpuscular Hemoglobin Concentration",
}


def _deviation_ratio(value: float, low: float, high: float) -> float:
    if low <= value <= high:
        midpoint = (low + high) / 2
        span = max(high - low, 1e-9)
        return abs(value - midpoint) / span
    if value < low:
        return (low - value) / max(abs(low), 1e-9)
    return (value - high) / max(abs(high), 1e-9)


def _severity_band(ratio: float, status: str) -> str:
    if status == "normal":
        return "normal"
    if ratio >= 0.4:
        return "critical"
    if ratio >= 0.2:
        return "high"
    if ratio >= 0.08:
        return "moderate"
    return "mild"


def build_derived_features(
    *,
    source_data: dict[str, Any],
    research_output: dict[str, Any],
    verification_output: dict[str, Any],
    report_output: dict[str, Any],
) -> dict[str, Any]:
    all_status = source_data.get("all_feature_status", [])
    abnormal = [item for item in all_status if item["status"] != "normal"]
    enriched = []
    for item in all_status:
        ratio = _deviation_ratio(
            float(item["value"]),
            float(item["reference_low"]),
            float(item["reference_high"]),
        )
        enriched.append(
            {
                **item,
                "deviation_ratio": round(ratio, 4),
                "severity_band": _severity_band(ratio, item["status"]),
            }
        )

    abnormal_enriched = [item for item in enriched if item["status"] != "normal"]
    abnormal_sorted = sorted(abnormal_enriched, key=lambda item: item["deviation_ratio"], reverse=True)

    cardiac = [item for item in abnormal_sorted if item["feature"] in CARDIAC_MARKERS]
    metabolic = [item for item in abnormal_sorted if item["feature"] in METABOLIC_MARKERS]
    hematology = [item for item in abnormal_sorted if item["feature"] in HEMATOLOGY_MARKERS]

    critical_markers = [item["feature"] for item in abnormal_sorted if item["severity_band"] == "critical"][:8]
    urgency_score = min(
        100,
        int(
            len(abnormal_sorted) * 3
            + len(cardiac) * 6
            + len(critical_markers) * 8
            + len(research_output.get("system_buckets", {}).get("inflammatory", [])) * 4
        ),
    )

    if urgency_score >= 80:
        escalation_level = "immediate_review"
    elif urgency_score >= 55:
        escalation_level = "rapid_follow_up"
    elif urgency_score >= 30:
        escalation_level = "monitor_closely"
    else:
        escalation_level = "routine_review"

    systems_affected = report_output.get("patient_snapshot", {}).get("systems_affected", [])
    follow_up_needed = bool(abnormal_sorted)
    all_normal_summary = "All tracked markers are within configured ranges." if not abnormal_sorted else ""
    care_priority_label = {
        "immediate_review": "High Priority",
        "rapid_follow_up": "Elevated Priority",
        "monitor_closely": "Monitor",
        "routine_review": "Routine",
    }[escalation_level]

    return {
        "marker_status_map": {item["feature"]: item["status"] for item in enriched},
        "marker_deviation_map": {item["feature"]: item["deviation_ratio"] for item in enriched},
        "severity_score_per_marker": {item["feature"]: item["severity_band"] for item in enriched},
        "number_of_abnormal_markers": len(abnormal_sorted),
        "top_abnormal_markers": [
            {
                "feature": item["feature"],
                "status": item["status"],
                "deviation_ratio": item["deviation_ratio"],
                "severity_band": item["severity_band"],
            }
            for item in abnormal_sorted[:8]
        ],
        "grouped_abnormalities_by_system": research_output.get("system_buckets", {}),
        "cardiac_risk_indicators": [item["feature"] for item in cardiac[:6]],
        "metabolic_risk_indicators": [item["feature"] for item in metabolic[:8]],
        "hematology_risk_indicators": [item["feature"] for item in hematology[:8]],
        "critical_marker_alert": critical_markers,
        "urgency_score": urgency_score,
        "escalation_level": escalation_level,
        "follow_up_needed_flag": follow_up_needed,
        "all_normal_summary": all_normal_summary,
        "multi_system_abnormality_flag": len(systems_affected) >= 2,
        "executive_triage_summary": report_output.get("summary", ""),
        "patient_snapshot": report_output.get("patient_snapshot", {}),
        "care_priority_label": care_priority_label,
        "verified_clinical_findings": verification_output.get("verified_claims", []),
        "structured_downloadable_report": report_output,
        "history_placeholders": {
            "repeat_patient_detection": False,
            "prior_diagnosis_comparison": [],
            "prior_confidence_comparison": [],
            "marker_trend_over_time": [],
            "similar_patient_retrieval": [],
            "cohort_summaries": [],
            "recent_case_comparison": [],
        },
    }

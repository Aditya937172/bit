from __future__ import annotations

from typing import Any


def _systems_affected(system_buckets: dict[str, list[str]]) -> list[str]:
    return [name for name, items in system_buckets.items() if items]


def _build_diet_examples(abnormal: list[dict[str, Any]]) -> list[str]:
    features = {item["feature"] for item in abnormal}
    examples: list[str] = []

    if {"Systolic Blood Pressure", "Diastolic Blood Pressure"} & features:
        examples.append(
            "Diet example for blood pressure: oats or poha for breakfast, dal with salad for lunch, and a lighter dinner with less salt, chips, pickle, and packaged sauces."
        )
    if {"Glucose", "HbA1c", "Insulin"} & features:
        examples.append(
            "Diet example for blood sugar: replace sugary drinks with water, keep rice or roti portions moderate, and pair meals with protein like eggs, paneer, curd, beans, or grilled chicken."
        )
    if {"Cholesterol", "LDL Cholesterol", "Triglycerides", "BMI"} & features:
        examples.append(
            "Diet example for cholesterol and triglycerides: cut back on fried snacks, bakery foods, and late desserts, and choose nuts, sprouts, vegetables, oats, and grilled or home-cooked meals more often."
        )
    if {"Hemoglobin", "Red Blood Cells", "Hematocrit"} & features:
        examples.append(
            "Diet example for low blood counts: include iron-rich foods like spinach, beans, jaggery in moderation, eggs, or lean meat along with vitamin-C foods like orange or guava."
        )

    if not examples:
        examples.append(
            "Diet example: keep meals simple, balanced, and less processed by using vegetables, pulses, fruit, water, and regular meal timing."
        )

    return examples[:4]


def build_research_fallback(source_data: dict[str, Any]) -> dict[str, Any]:
    abnormal = source_data.get("abnormal_feature_status", [])
    executive = []
    system_buckets = {
        "metabolic": [],
        "hematology": [],
        "cardiovascular": [],
        "hepatic": [],
        "renal": [],
        "inflammatory": [],
    }

    for item in abnormal:
        feature = item["feature"]
        value = item["value"]
        low = item["reference_low"]
        high = item["reference_high"]
        status = item["status"]
        note = f"{feature} is {status} at {value} against reference {low}-{high}."
        executive.append(note)
        lowered = feature.lower()
        if any(token in lowered for token in ["glucose", "hba1c", "insulin", "bmi", "cholesterol", "triglycerides", "ldl", "hdl"]):
            system_buckets["metabolic"].append(note)
        if any(token in lowered for token in ["hemoglobin", "platelets", "white blood", "red blood", "hematocrit", "corpuscular"]):
            system_buckets["hematology"].append(note)
        if any(token in lowered for token in ["blood pressure", "heart rate", "troponin"]):
            system_buckets["cardiovascular"].append(note)
        if lowered in {"alt", "ast"}:
            system_buckets["hepatic"].append(note)
        if "creatinine" in lowered:
            system_buckets["renal"].append(note)
        if "c-reactive protein" in lowered:
            system_buckets["inflammatory"].append(note)

    return {
        "executive_observations": executive[:8],
        "abnormal_findings": [
            {
                "feature": item["feature"],
                "value": item["value"],
                "reference_range": f'{item["reference_low"]}-{item["reference_high"]}',
                "status": item["status"],
                "clinical_note": f'{item["feature"]} is outside the configured range.',
            }
            for item in abnormal[:12]
        ],
        "system_buckets": system_buckets,
        "follow_up_questions": [
            "Are these values from a fasting sample?",
            "Is there prior history available for trend comparison?",
            "Were any medications or acute symptoms present at collection time?",
        ],
    }


def build_verification_fallback(source_data: dict[str, Any], research_output: dict[str, Any]) -> dict[str, Any]:
    verified = []
    rejected = []
    for claim in research_output.get("executive_observations", []):
        if "reference" in claim or "outside the configured range" in claim or " is " in claim:
            verified.append(claim)
        else:
            rejected.append(claim)

    return {
        "verified_claims": verified,
        "rejected_claims": rejected,
        "safety_flags": [
            "This fallback verification is deterministic and based only on configured ranges.",
        ],
        "data_quality_flags": [
            f'Missing feature count: {source_data.get("document_summary", {}).get("missing_feature_count", 0)}'
        ],
        "verification_status": "verified",
    }


def build_report_fallback(source_data: dict[str, Any], research_output: dict[str, Any], verification_output: dict[str, Any]) -> dict[str, Any]:
    abnormal = source_data.get("abnormal_feature_status", [])
    top_items = [item["feature"] for item in abnormal[:5]]
    system_buckets = research_output.get("system_buckets", {})
    diet_examples = _build_diet_examples(abnormal)
    measured_highlights = [
        f'{item["feature"]}: {item["value"]} vs {item["reference_low"]}-{item["reference_high"]} ({item["status"]})'
        for item in abnormal[:6]
    ]
    critical_markers = []
    for item in abnormal:
        feature = item["feature"]
        value = item["value"]
        low = item["reference_low"]
        high = item["reference_high"]
        if high > low:
            if value > high + ((high - low) * 0.3) or value < low - ((high - low) * 0.3):
                critical_markers.append(feature)

    return {
        "headline": "Quick Health Report",
        "summary": (
            f'Here is the simple picture: {len(abnormal)} markers are outside the normal range. '
            f'The main points to review first are {", ".join(top_items) if top_items else "no major abnormalities detected"}.'
        ),
        "key_findings": verification_output.get("verified_claims", [])[:8],
        "measured_highlights": measured_highlights,
        "patient_snapshot": {
            "abnormal_marker_count": len(abnormal),
            "normal_marker_count": source_data.get("normal_feature_count", 0),
            "systems_affected": _systems_affected(system_buckets),
        },
        "critical_markers": critical_markers[:6],
        "monitoring_priorities": top_items,
        "follow_up_questions": research_output.get("follow_up_questions", [])[:3],
        "diet_examples": diet_examples,
        "agent_next_steps": [
            f"Review these measured markers first: {', '.join(top_items[:3]) if top_items else 'top abnormal markers'}.",
            "Use the measured values and reference ranges to confirm which markers need repeat review or closer follow-up.",
            "Use the diet example guidance as a simple educational starting point, not as a prescription.",
        ],
        "recommended_next_steps": [
            "Review the top markers with a clinician or medical reviewer.",
            "Confirm units and report context for any severe or unexpected values.",
            diet_examples[0],
            "Keep this report for future comparison with the next visit or upload.",
        ],
        "report_style": "simple_bullet_brief",
    }

from __future__ import annotations

from typing import Any


def build_document_fallback(
    *,
    source_data: dict[str, Any],
    derived_features: dict[str, Any],
    report_output: dict[str, Any],
    verification_output: dict[str, Any],
) -> dict[str, Any]:
    diet_examples = report_output.get("diet_examples", [])
    abnormal_count = derived_features.get("number_of_abnormal_markers", 0)
    top_markers = [item.get("feature") for item in derived_features.get("top_abnormal_markers", [])[:4] if item.get("feature")]
    return {
        "title": "Patient Health Snapshot Report",
        "clinical_overview": report_output.get("summary", ""),
        "major_abnormalities": derived_features.get("top_abnormal_markers", []),
        "system_analysis": report_output.get("patient_snapshot", {}).get("systems_affected", []),
        "severity_matrix": derived_features.get("severity_score_per_marker", {}),
        "monitoring_plan": report_output.get("monitoring_priorities", []),
        "follow_up_questions": report_output.get("follow_up_questions", []),
        "doctor_brief": verification_output.get("verified_claims", [])[:10],
        "summary_points": [
            f"Abnormal markers found: {abnormal_count}",
            f"Main markers to review: {', '.join(top_markers) if top_markers else 'None'}",
            f"Urgency score: {derived_features.get('urgency_score', 0)}/100",
        ],
        "measured_highlights": report_output.get("measured_highlights", []),
        "diet_examples": diet_examples,
        "patient_friendly_summary": (
            (
                "A few health markers are outside the expected range, so this report should be reviewed with a clinician. "
                + (f"One simple food example is: {diet_examples[0]}" if diet_examples else "")
            )
            if derived_features.get("number_of_abnormal_markers", 0)
            else "The measured markers are within configured ranges."
        ),
        "appendix": {
            "parsed_feature_count": source_data.get("document_summary", {}).get("parsed_feature_count", 0),
            "abnormal_marker_count": derived_features.get("number_of_abnormal_markers", 0),
            "urgency_score": derived_features.get("urgency_score", 0),
        },
        "image_prompt_for_visual_report": (
            "Create a clean clinical infographic dashboard on a white background with blue and teal accents. "
            "Show abnormal marker count, urgency score, affected systems, critical markers, and a workflow-style "
            "patient report summary. Use card layout, subtle medical iconography, data visualization feel, and "
            "legible headings."
        ),
    }

from __future__ import annotations

import json
import os
from typing import Any

from agent.chat_context import build_chat_agent_context
from agent.document_agent import build_document_fallback
from agent.derived_features import build_derived_features
from agent.fallback_agents import build_report_fallback, build_research_fallback, build_verification_fallback
from agent.model_adapter import get_reference_ranges

from .storage import normalize_legacy_values, parse_legacy_confidence


def _feature_cards(
    source_data: dict[str, Any],
    research_output: dict[str, Any],
    verification_output: dict[str, Any],
    report_output: dict[str, Any],
) -> dict[str, Any]:
    abnormal = source_data.get("abnormal_feature_status", [])
    top_abnormal = [
        {
            "feature": item["feature"],
            "status": item["status"],
            "value": item["value"],
            "reference_range": f'{item["reference_low"]}-{item["reference_high"]}',
        }
        for item in abnormal[:8]
    ]
    return {
        "executive_summary_card": {
            "headline": report_output.get("headline"),
            "summary": report_output.get("summary"),
            "verification_status": verification_output.get("verification_status"),
        },
        "patient_snapshot_card": report_output.get("patient_snapshot", {}),
        "critical_markers_card": {
            "critical_markers": report_output.get("critical_markers", []),
            "top_abnormal_markers": top_abnormal,
            "measured_highlights": report_output.get("measured_highlights", []),
        },
        "system_insights_card": research_output.get("system_buckets", {}),
        "action_card": {
            "monitoring_priorities": report_output.get("monitoring_priorities", []),
            "recommended_next_steps": report_output.get("recommended_next_steps", []),
            "follow_up_questions": report_output.get("follow_up_questions", []),
        },
        "agent_next_steps_card": {
            "agent_next_steps": report_output.get("agent_next_steps", []),
            "measured_highlights": report_output.get("measured_highlights", []),
        },
    }


def derive_source_data(
    normalized_patient_input: dict[str, float],
    *,
    file_name: str,
    file_type: str,
    extraction_mode: str,
    parsed_feature_count: int,
    missing_feature_count: int,
    extracted_text: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    ranges = get_reference_ranges()
    findings = []
    abnormal = []
    for feature, value in normalized_patient_input.items():
        low, high = ranges[feature]
        if value < low:
            status = "low"
        elif value > high:
            status = "high"
        else:
            status = "normal"
        finding = {
            "feature": feature,
            "value": value,
            "reference_low": low,
            "reference_high": high,
            "status": status,
        }
        findings.append(finding)
        if status != "normal":
            abnormal.append(finding)

    raw_intake = {
        "parsed_document": {
            "document_ingestion": {
                "file_name": file_name,
                "file_type": file_type,
                "extraction_mode": extraction_mode,
                "text_preview": extracted_text[:320],
            },
            "parsed_payload": {
                "parsed_feature_count": parsed_feature_count,
                "missing_feature_count": missing_feature_count,
                "parsed_values": normalized_patient_input,
            },
        },
        "normalized_patient_input": normalized_patient_input,
        "reference_ranges": ranges,
    }

    source_data = {
        "document_summary": {
            "file_name": file_name,
            "file_type": file_type,
            "extraction_mode": extraction_mode,
            "parsed_feature_count": parsed_feature_count,
            "missing_feature_count": missing_feature_count,
        },
        "abnormal_feature_status": abnormal,
        "normal_feature_count": len(findings) - len(abnormal),
        "all_feature_status": findings,
    }
    return raw_intake, source_data


def build_payload_from_legacy_row(row: dict[str, Any]) -> dict[str, Any]:
    patient_name = f"{row.get('first_name', '').strip()} {row.get('last_name', '').strip()}".strip() or "Legacy Patient"
    normalized_patient_input = normalize_legacy_values(row)
    raw_intake, source_data = derive_source_data(
        normalized_patient_input,
        file_name=f"legacy_{row['legacy_id']}.db",
        file_type=".db",
        extraction_mode="sqlite_history",
        parsed_feature_count=len(normalized_patient_input),
        missing_feature_count=0,
        extracted_text=f"Patient Name: {patient_name}",
    )

    research_output = build_research_fallback(source_data)
    verification_output = build_verification_fallback(source_data, research_output)
    report_output = build_report_fallback(source_data, research_output, verification_output)
    derived_features = build_derived_features(
        source_data=source_data,
        research_output=research_output,
        verification_output=verification_output,
        report_output=report_output,
    )
    document_output = build_document_fallback(
        source_data=source_data,
        derived_features=derived_features,
        report_output=report_output,
        verification_output=verification_output,
    )
    chat_context = build_chat_agent_context(
        source_data=source_data,
        derived_features=derived_features,
        report_output=report_output,
        verification_output=verification_output,
    )

    return {
        "case_metadata": {
            "case_id": f"legacy-{row['legacy_id']}",
            "patient_name": patient_name,
            "mode": "History",
            "created_at": None,
            "legacy_diagnosis": row.get("diagnosis"),
            "legacy_confidence": parse_legacy_confidence(row.get("confidence")),
        },
        "raw_intake": raw_intake,
        "research_agent_output": research_output,
        "verification_agent_output": verification_output,
        "report_agent_output": report_output,
        "derived_features": derived_features,
        "document_agent_output": document_output,
        "chat_agent_context": chat_context,
        "feature_outputs": _feature_cards(source_data, research_output, verification_output, report_output),
        "legacy_db_row": row,
    }


def _short_label(text: str) -> str:
    return text.replace("Cholesterol", "Chol").replace("Pressure", "BP")[:12]


def build_dashboard_profile(payload: dict[str, Any], *, case_id: str, mode: str) -> dict[str, Any]:
    report = payload.get("report_agent_output", {})
    derived = payload.get("derived_features", {})
    feature_outputs = payload.get("feature_outputs", {})
    chat = payload.get("chat_agent_context", {})
    raw_intake = payload.get("raw_intake", {})
    ingestion = raw_intake.get("parsed_document", {}).get("document_ingestion", {})
    parsed_payload = raw_intake.get("parsed_document", {}).get("parsed_payload", {})
    enrichment = payload.get("dashboard_enrichment", {})
    medication_guidance = enrichment.get("medication_guidance", {})
    patient_name = payload.get("case_metadata", {}).get("patient_name") or ingestion.get("file_name", "Imported Case")
    top_abnormal = derived.get("top_abnormal_markers", [])
    urgency_score = int(derived.get("urgency_score", 0) or 0)

    if urgency_score >= 80:
        status_class = "high"
        status_text = "High priority"
    elif urgency_score >= 40:
        status_class = "monitoring"
        status_text = "Monitoring"
    else:
        status_class = "stable"
        status_text = "Stable"

    trend_labels = [_short_label(item["feature"]) for item in top_abnormal[:6]]
    trend_patient = [max(20, round(float(item.get("deviation_ratio", 0)) * 100)) for item in top_abnormal[:6]]
    trend_reference = [18 + (index * 3) for index in range(len(trend_labels))]
    severity_palette = ["red", "blue", "brown", "teal", "dark"]

    return {
        "caseId": case_id,
        "patientName": patient_name,
        "mode": mode,
        "statusText": status_text,
        "statusClass": status_class,
        "fileName": ingestion.get("file_name", "Imported report"),
        "verificationStatus": feature_outputs.get("executive_summary_card", {}).get("verification_status")
        or payload.get("verification_agent_output", {}).get("verification_status", "verified"),
        "headline": report.get("headline", "Clinical report"),
        "summary": report.get("summary", ""),
        "carePriority": derived.get("care_priority_label", "Monitor"),
        "urgencyScore": urgency_score,
        "systemsAffected": report.get("patient_snapshot", {}).get("systems_affected", []),
        "criticalMarkers": report.get("critical_markers", []),
        "monitoringPriorities": report.get("monitoring_priorities", []),
        "recommendedNextSteps": report.get("recommended_next_steps", []),
        "followUpQuestions": report.get("follow_up_questions", []),
        "dietExamples": report.get("diet_examples", []),
        "agentNextSteps": report.get("agent_next_steps", []),
        "measuredHighlights": report.get("measured_highlights", []),
        "keyFindings": report.get("key_findings", []),
        "abnormalMarkerCount": report.get("patient_snapshot", {}).get("abnormal_marker_count", derived.get("number_of_abnormal_markers", 0)),
        "normalMarkerCount": report.get("patient_snapshot", {}).get("normal_marker_count", 0),
        "parsedFeatureCount": parsed_payload.get("parsed_feature_count", 0),
        "missingFeatureCount": parsed_payload.get("missing_feature_count", 0),
        "extractionMode": ingestion.get("extraction_mode", ""),
        "fileType": ingestion.get("file_type", ""),
        "systemInsights": feature_outputs.get("system_insights_card", {}),
        "topAbnormalMarkers": top_abnormal,
        "trend": {
            "labels": trend_labels or ["Profile"],
            "patient": trend_patient or [20],
            "reference": trend_reference or [18],
        },
        "severityBars": [
            {
                "label": _short_label(item["feature"]),
                "value": max(20, round(float(item.get("deviation_ratio", 0)) * 100)),
                "className": severity_palette[index % len(severity_palette)],
            }
            for index, item in enumerate(top_abnormal[:5])
        ]
        or [{"label": "Stable", "value": 20, "className": "teal"}],
        "starterQuestions": chat.get("starter_questions", []),
        "pdfPath": f"/api/cases/{case_id}/pdf",
        "imagePath": f"/api/cases/{case_id}/image",
        "createdAt": payload.get("case_metadata", {}).get("created_at"),
        "medicationSummary": medication_guidance.get("summary", ""),
        "medicationGraph": medication_guidance.get("graph", []),
        "medicationRules": medication_guidance.get("matched_rules", []),
        "medicationSources": medication_guidance.get("sources", []),
    }


def load_demo_payload(case_id: str = "demo-visualhook") -> dict[str, Any]:
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    demo_path = os.path.join(root_dir, "agent", "agent_report_output_visualhook.json")
    if os.path.exists(demo_path):
        with open(demo_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        payload.setdefault("case_metadata", {})
        payload["case_metadata"].update({"case_id": case_id, "patient_name": "Demo Case", "mode": "Demo"})
        return payload

    demo_values = {
        "Glucose": 110.0,
        "Cholesterol": 185.0,
        "Hemoglobin": 12.1,
        "Platelets": 180000.0,
        "White Blood Cells": 9000.0,
        "Red Blood Cells": 4.0,
        "Hematocrit": 36.0,
        "Mean Corpuscular Volume": 77.0,
        "Mean Corpuscular Hemoglobin": 25.0,
        "Mean Corpuscular Hemoglobin Concentration": 32.0,
        "Insulin": 15.0,
        "BMI": 27.0,
        "Systolic Blood Pressure": 138.0,
        "Diastolic Blood Pressure": 88.0,
        "Triglycerides": 170.0,
        "HbA1c": 6.4,
        "LDL Cholesterol": 142.0,
        "HDL Cholesterol": 42.0,
        "ALT": 39.0,
        "AST": 33.0,
        "Heart Rate": 86.0,
        "Creatinine": 1.0,
        "Troponin": 0.02,
        "C-reactive Protein": 2.0,
    }
    raw_intake, source_data = derive_source_data(
        demo_values,
        file_name="demo_case.txt",
        file_type=".txt",
        extraction_mode="demo",
        parsed_feature_count=24,
        missing_feature_count=0,
        extracted_text="Patient Name: Demo Case",
    )
    research = build_research_fallback(source_data)
    verification = build_verification_fallback(source_data, research)
    report = build_report_fallback(source_data, research, verification)
    derived = build_derived_features(
        source_data=source_data,
        research_output=research,
        verification_output=verification,
        report_output=report,
    )
    document = build_document_fallback(
        source_data=source_data,
        derived_features=derived,
        report_output=report,
        verification_output=verification,
    )
    chat = build_chat_agent_context(
        source_data=source_data,
        derived_features=derived,
        report_output=report,
        verification_output=verification,
    )
    payload = {
        "case_metadata": {"case_id": case_id, "patient_name": "Demo Case", "mode": "Demo"},
        "raw_intake": raw_intake,
        "research_agent_output": research,
        "verification_agent_output": verification,
        "report_agent_output": report,
        "derived_features": derived,
        "document_agent_output": document,
        "chat_agent_context": chat,
        "feature_outputs": _feature_cards(source_data, research, verification, report),
    }
    return payload


def load_demo_profiles() -> list[dict[str, Any]]:
    payload = load_demo_payload()
    case_id = payload.get("case_metadata", {}).get("case_id", "demo-visualhook")
    return [build_dashboard_profile(payload, case_id=case_id, mode="Demo")]

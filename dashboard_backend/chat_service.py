from __future__ import annotations

import re
from typing import Any

from agent.llm_client import LLMClient
from agent.skills_manager import build_skill_block
from .clinical_facts import FACT_SOURCES


FEATURE_KEYWORDS = {
    "glucose": "Glucose",
    "cholesterol": "Cholesterol",
    "hemoglobin": "Hemoglobin",
    "platelets": "Platelets",
    "white blood": "White Blood Cells",
    "wbc": "White Blood Cells",
    "red blood": "Red Blood Cells",
    "rbc": "Red Blood Cells",
    "hematocrit": "Hematocrit",
    "mcv": "Mean Corpuscular Volume",
    "mch": "Mean Corpuscular Hemoglobin",
    "mchc": "Mean Corpuscular Hemoglobin Concentration",
    "insulin": "Insulin",
    "bmi": "BMI",
    "systolic": "Systolic Blood Pressure",
    "diastolic": "Diastolic Blood Pressure",
    "blood pressure": "Systolic Blood Pressure",
    "bp": "Systolic Blood Pressure",
    "triglycerides": "Triglycerides",
    "a1c": "HbA1c",
    "hba1c": "HbA1c",
    "ldl": "LDL Cholesterol",
    "hdl": "HDL Cholesterol",
    "alt": "ALT",
    "ast": "AST",
    "heart rate": "Heart Rate",
    "pulse": "Heart Rate",
    "creatinine": "Creatinine",
    "troponin": "Troponin",
    "crp": "C-reactive Protein",
    "c-reactive protein": "C-reactive Protein",
    "drug": "medication",
    "medicine": "medication",
}

DIET_RULES = [
    (
        {"Systolic Blood Pressure", "Diastolic Blood Pressure"},
        "Because blood pressure markers are elevated, prioritize lower-sodium meals, cut back on packaged salty foods, and watch sauces, pickles, instant foods, and restaurant-heavy meals.",
    ),
    (
        {"Glucose", "HbA1c", "Insulin"},
        "Because glucose-related markers are elevated, reduce sugary drinks, sweets, and refined carbs, and favor slower-digesting meals with fiber, protein, and steadier portions.",
    ),
    (
        {"Triglycerides", "BMI"},
        "Triglycerides and BMI suggest leaning away from ultra-processed snacks, excess alcohol, and late heavy meals while increasing vegetables, legumes, and consistent meal timing.",
    ),
    (
        {"LDL Cholesterol", "Cholesterol", "HDL Cholesterol"},
        "Lipid markers suggest limiting fried foods and high saturated-fat meals, while shifting toward nuts, seeds, pulses, fish, and unsaturated fats where possible.",
    ),
    (
        {"Hemoglobin", "Red Blood Cells", "Hematocrit"},
        "Low blood-count markers can justify reviewing iron-rich and protein-rich foods, but that should be interpreted alongside clinician advice and possible deficiency workup.",
    ),
]

FEATURE_EXPLANATIONS = {
    "Systolic Blood Pressure": "This reflects the pressure when the heart pumps; high values raise cardiovascular load.",
    "Diastolic Blood Pressure": "This reflects resting arterial pressure between beats; persistent elevation supports hypertension risk.",
    "Glucose": "High glucose can signal poor short-term blood sugar control.",
    "HbA1c": "HbA1c reflects longer-term blood sugar exposure over recent weeks to months.",
    "Triglycerides": "High triglycerides often track with metabolic stress, diet quality, or insulin resistance.",
    "LDL Cholesterol": "Higher LDL is commonly treated as a more atherogenic lipid pattern.",
    "Hemoglobin": "Low hemoglobin can fit an anemia pattern and often deserves follow-up with blood count context.",
    "Creatinine": "Creatinine helps screen kidney function and should be read with context and trend.",
    "C-reactive Protein": "CRP is a non-specific inflammatory marker and can rise with systemic inflammation.",
    "Troponin": "Troponin is a cardiac injury marker and should always be interpreted carefully with symptoms and timing.",
}

SYSTEM_KEYWORDS = {
    "metabolic": ["metabolic", "glucose", "sugar", "diabetes", "cholesterol", "lipid", "triglycerides", "a1c", "hba1c", "insulin", "bmi"],
    "hematology": ["hematology", "blood count", "anemia", "hemoglobin", "platelet", "platelets", "rbc", "wbc", "hematocrit", "mcv", "mch", "mchc"],
    "cardiovascular": ["cardiovascular", "heart", "blood pressure", "bp", "pulse", "heart rate", "systolic", "diastolic"],
    "hepatic": ["liver", "hepatic", "alt", "ast"],
    "renal": ["kidney", "kidneys", "renal", "creatinine"],
    "inflammatory": ["inflammation", "inflammatory", "crp", "c-reactive protein"],
}


SPECIALIST_AGENTS = {
    "dr_emily_carter": {
        "name": "Emily",
        "title": "Metabolic & Endocrine Specialist",
        "focus_features": {"Glucose", "HbA1c", "Insulin", "BMI", "Triglycerides"},
        "source_ids": ["ada_type2_meds", "aha_tg_meds"],
        "icon": "metabolic",
        "skill": "dr_emily_carter_skill.md",
    },
    "dr_james_brooks": {
        "name": "James",
        "title": "Cardiovascular Specialist",
        "focus_features": {
            "Systolic Blood Pressure",
            "Diastolic Blood Pressure",
            "Heart Rate",
            "Cholesterol",
            "LDL Cholesterol",
            "HDL Cholesterol",
            "Troponin",
        },
        "source_ids": ["aha_bp_meds", "aha_chol_meds", "aha_heart_meds"],
        "icon": "cardio",
        "skill": "dr_james_brooks_skill.md",
    },
    "dr_hannah_reed": {
        "name": "Hannah",
        "title": "Hematology Specialist",
        "focus_features": {
            "Hemoglobin",
            "Red Blood Cells",
            "Hematocrit",
            "Mean Corpuscular Volume",
            "Mean Corpuscular Hemoglobin",
            "Mean Corpuscular Hemoglobin Concentration",
            "White Blood Cells",
            "Platelets",
        },
        "source_ids": ["nhlbi_anemia_tx", "nhlbi_platelet_tx"],
        "icon": "heme",
        "skill": "dr_hannah_reed_skill.md",
    },
    "dr_olivia_bennett": {
        "name": "Olivia",
        "title": "Internal Medicine Specialist",
        "focus_features": {"C-reactive Protein", "Creatinine", "ALT", "AST", "Troponin"},
        "source_ids": ["aha_heart_meds", "nhlbi_anemia_tx"],
        "icon": "internal",
        "skill": "dr_olivia_bennett_skill.md",
    },
}


def _feature_snapshot(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    normalized = payload.get("raw_intake", {}).get("normalized_patient_input", {})
    ranges = payload.get("raw_intake", {}).get("reference_ranges", {})
    statuses = payload.get("derived_features", {}).get("marker_status_map", {})
    deviations = payload.get("derived_features", {}).get("marker_deviation_map", {})
    severity = payload.get("derived_features", {}).get("severity_score_per_marker", {})

    snapshot = {}
    for feature, value in normalized.items():
        ref = ranges.get(feature, ["", ""])
        snapshot[feature] = {
            "feature": feature,
            "value": value,
            "reference_low": ref[0],
            "reference_high": ref[1],
            "status": statuses.get(feature, "unknown"),
            "severity": severity.get(feature, "unknown"),
            "deviation_ratio": deviations.get(feature, 0.0),
        }
    return snapshot


def _specialist_focus_items(payload: dict[str, Any], agent_key: str) -> list[dict[str, Any]]:
    agent = SPECIALIST_AGENTS.get(agent_key)
    if not agent:
        return []

    snapshot = _feature_snapshot(payload)
    top_abnormal = payload.get("derived_features", {}).get("top_abnormal_markers", [])
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in top_abnormal:
        feature = item.get("feature")
        if feature in agent["focus_features"] and feature in snapshot and feature not in seen:
            merged = {**snapshot[feature], **item}
            ordered.append(merged)
            seen.add(feature)

    for feature in agent["focus_features"]:
        if feature in snapshot and feature not in seen:
            ordered.append(snapshot[feature])
            seen.add(feature)

    return ordered


def _specialist_citations(agent_key: str) -> list[dict[str, Any]]:
    agent = SPECIALIST_AGENTS.get(agent_key)
    if not agent:
        return []
    seen = set()
    citations = []
    for source_id in agent["source_ids"]:
        if source_id in FACT_SOURCES and source_id not in seen:
            citations.append(FACT_SOURCES[source_id])
            seen.add(source_id)
    return citations


def build_specialist_agents(payload: dict[str, Any]) -> list[dict[str, Any]]:
    agents = []
    for key, agent in SPECIALIST_AGENTS.items():
        focus_items = _specialist_focus_items(payload, key)
        main_markers = [item.get("feature") for item in focus_items[:3] if item.get("feature")]
        agents.append(
            {
                "key": key,
                "name": agent["name"],
                "title": agent["title"],
                "icon": agent["icon"],
                "skill": agent["skill"],
                "main_markers": main_markers,
                "available": True,
                "focus_count": len([item for item in focus_items if item.get("status") != "normal"]),
            }
        )
    return agents


def _recent_specialist_context(history: list[dict[str, Any]], agent_key: str) -> list[dict[str, str]]:
    recent: list[dict[str, str]] = []
    for entry in reversed(history):
        assistant_text = str(entry.get("assistant_message", "")).strip()
        if not assistant_text:
            continue
        for other_key, other_agent in SPECIALIST_AGENTS.items():
            if other_key == agent_key:
                continue
            prefix = f"{other_agent['name']} here."
            if not assistant_text.startswith(prefix):
                continue
            summary = assistant_text.split("Measured data:")[0].split("Next steps:")[0]
            summary = summary.replace(prefix, "", 1).strip()
            summary = _shorten_answer_text(summary).rstrip(".")
            if not summary:
                continue
            recent.append(
                {
                    "key": other_key,
                    "name": other_agent["name"],
                    "title": other_agent["title"],
                    "summary": summary,
                }
            )
            break
        if len(recent) >= 2:
            break
    recent.reverse()
    return recent


def _shared_context_line(agent_key: str, focus_items: list[dict[str, Any]], history: list[dict[str, Any]]) -> str:
    shared_context = _recent_specialist_context(history, agent_key)
    if not shared_context:
        return ""
    latest = shared_context[-1]
    focus_names = [item.get("feature") for item in focus_items[:2] if item.get("feature")]
    focus_text = ", ".join(focus_names) if focus_names else "my part of the report"
    return f"Shared context: keeping {latest['name']}'s earlier note in mind while I focus on {focus_text}."


def _format_measure_line(item: dict[str, Any]) -> str:
    feature = item.get("feature", "Marker")
    value = item.get("value", "unknown")
    reference_low = item.get("reference_low", "")
    reference_high = item.get("reference_high", "")
    reference_range = item.get("reference_range")
    status = item.get("status", "unknown")
    severity = item.get("severity") or item.get("severity_band")
    range_text = reference_range or f"{reference_low}-{reference_high}"
    if severity:
        return f"{feature}: {value} vs {range_text} ({status}, {severity})"
    return f"{feature}: {value} vs {range_text} ({status})"


def _find_feature(question: str) -> str | None:
    lowered = question.lower()
    for keyword, feature in FEATURE_KEYWORDS.items():
        if keyword in lowered:
            return feature
    return None


def _find_systems(question: str) -> list[str]:
    lowered = question.lower()
    matched = []
    for system, keywords in SYSTEM_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            matched.append(system)
    return matched


def _infer_feature_from_history(history: list[dict[str, Any]]) -> str | None:
    for item in reversed(history):
        for key in ("user_message", "assistant_message"):
            text = str(item.get(key, ""))
            feature = _find_feature(text)
            if feature and feature != "medication":
                return feature
    return None


def _mentions_followup_reference(question: str) -> bool:
    lowered = f" {question.lower()} "
    return any(token in lowered for token in [" that ", " those ", " it ", " this one ", " these "])


def _top_marker_lines(payload: dict[str, Any], limit: int = 5) -> list[str]:
    snapshot = _feature_snapshot(payload)
    top = payload.get("derived_features", {}).get("top_abnormal_markers", [])[:limit]
    lines = []
    for item in top:
        feature = item.get("feature")
        raw = snapshot.get(feature, {})
        lines.append(
            f"{feature}: {raw.get('value')} vs {raw.get('reference_low')}-{raw.get('reference_high')} "
            f"({raw.get('status')}, {item.get('severity_band', raw.get('severity', 'unknown'))})"
        )
    return lines


def _extract_supporting_measure_lines(
    payload: dict[str, Any],
    question: str,
    supporting_facts: list[Any] | None,
) -> list[str]:
    supporting_facts = supporting_facts or []
    lines: list[str] = []
    snapshot = _feature_snapshot(payload)

    for fact in supporting_facts:
        if isinstance(fact, dict) and fact.get("feature"):
            feature_name = fact.get("feature")
            merged = {**snapshot.get(feature_name, {}), **fact}
            lines.append(_format_measure_line(merged))
        elif isinstance(fact, dict) and fact.get("observations"):
            for observation in fact.get("observations", [])[:3]:
                lines.append(str(observation))
        elif isinstance(fact, str) and ":" in fact and " vs " in fact:
            lines.append(fact)

    if lines:
        return lines[:4]

    feature = _find_feature(question)
    if feature and feature in snapshot:
        return [_format_measure_line(snapshot[feature])]

    systems = _find_systems(question)
    if systems:
        insights = payload.get("feature_outputs", {}).get("system_insights_card", {})
        for system in systems:
            lines.extend(insights.get(system, [])[:2])
        if lines:
            return lines[:4]

    return _top_marker_lines(payload, limit=3)


def _extract_next_steps(payload: dict[str, Any], question: str) -> list[str]:
    report = payload.get("report_agent_output", {})
    agent_steps = report.get("agent_next_steps", [])
    recommended = report.get("recommended_next_steps", [])
    follow_up = report.get("follow_up_questions", [])

    if any(term in question.lower() for term in ["diet", "food", "eat", "nutrition"]):
        diet_examples = report.get("diet_examples", [])
        combined = diet_examples[:2] + recommended[:2]
        return combined[:3]

    combined = agent_steps[:2] + recommended[:2] + [f"Follow-up question: {item}" for item in follow_up[:1]]
    deduped = []
    for item in combined:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:3]


def _format_answer_with_measures(
    answer: str,
    *,
    measure_lines: list[str],
    next_steps: list[str],
) -> str:
    sections = [_shorten_answer_text(answer)]
    if measure_lines:
        sections.append("Measured data:\n- " + "\n- ".join(measure_lines[:2]))
    if next_steps:
        sections.append("Next steps:\n- " + "\n- ".join(next_steps[:2]))
    return "\n\n".join(section for section in sections if section)


def _shorten_answer_text(answer: str) -> str:
    cleaned = " ".join(str(answer).strip().split())
    if not cleaned:
        return "I do not have enough data to answer that clearly."

    sentence_parts = [
        piece.strip()
        for piece in re.split(r"(?<=[A-Za-z\)])\.\s+|(?<=[!?])\s+", cleaned.replace(";", ". "))
        if piece.strip()
    ]
    short_answer = ". ".join(sentence_parts[:2]).strip()
    if short_answer and not short_answer.endswith("."):
        short_answer += "."
    return short_answer


def _general_summary(payload: dict[str, Any], *, audience: str = "general") -> str:
    patient_name = payload.get("case_metadata", {}).get("patient_name", "this patient")
    derived = payload.get("derived_features", {})
    report = payload.get("report_agent_output", {})
    systems = report.get("patient_snapshot", {}).get("systems_affected", [])
    top_lines = _top_marker_lines(payload, limit=4)

    if audience == "patient":
        return (
            f"For {patient_name}, several lab markers are outside the expected range. "
            f"The main issues showing up are {', '.join(top_lines) if top_lines else 'no major abnormalities'}; "
            f"the current priority label is {derived.get('care_priority_label', 'Monitor')} with urgency "
            f"{derived.get('urgency_score', 0)}/100. The main body systems involved are "
            f"{', '.join(systems) if systems else 'not strongly clustered into one system'}."
        )

    if audience == "clinician":
        return (
            f"{patient_name} has {derived.get('number_of_abnormal_markers', 0)} abnormal markers with "
            f"urgency {derived.get('urgency_score', 0)}/100 and care priority "
            f"{derived.get('care_priority_label', 'Monitor')}. Dominant findings: "
            f"{'; '.join(top_lines) if top_lines else 'no major abnormalities recorded'}. "
            f"Systems affected: {', '.join(systems) if systems else 'none clearly clustered'}."
        )

    return (
        f"{patient_name} currently shows {derived.get('number_of_abnormal_markers', 0)} abnormal markers. "
        f"The top ones are {', '.join(top_lines[:3]) if top_lines else 'none flagged'}. "
        f"Overall priority is {derived.get('care_priority_label', 'Monitor')} with urgency "
        f"{derived.get('urgency_score', 0)}/100."
    )


def _diet_guidance(payload: dict[str, Any]) -> tuple[str, list[str]]:
    top_features = {
        item.get("feature")
        for item in payload.get("derived_features", {}).get("top_abnormal_markers", [])
    }
    matched = []
    notes = []
    for features, note in DIET_RULES:
        if top_features.intersection(features):
            matched.extend(sorted(top_features.intersection(features)))
            notes.append(note)

    if not notes:
        notes.append(
            "There is not a strong diet-specific signal from the current top markers alone, so the safest approach is to keep meals balanced, limit ultra-processed foods, and review the formal plan with a clinician."
        )

    answer = (
        "Based on the current marker pattern, the most relevant food changes are: "
        + " ".join(notes[:3])
        + " This is general guidance from the parsed data, not a personalized prescription."
    )
    return answer, matched[:8]


def _exercise_guidance(payload: dict[str, Any]) -> str:
    urgency = payload.get("derived_features", {}).get("urgency_score", 0)
    top = [item.get("feature") for item in payload.get("derived_features", {}).get("top_abnormal_markers", [])[:4]]
    if urgency >= 80:
        return (
            f"Because urgency is {urgency}/100 and the main concerns include {', '.join(top)}, "
            "it would be better to clear activity intensity with a clinician first and focus on safe follow-up before pushing exercise volume."
        )
    return (
        f"Exercise-wise, the current data suggests starting with steady, sustainable movement rather than aggressive intensity. "
        f"That is especially relevant because the leading markers are {', '.join(top) if top else 'fairly mild'}."
    )


def _clinician_review(payload: dict[str, Any]) -> str:
    report = payload.get("report_agent_output", {})
    derived = payload.get("derived_features", {})
    findings = _top_marker_lines(payload, limit=5)
    systems = report.get("patient_snapshot", {}).get("systems_affected", [])
    return (
        f"First review the highest-severity markers: {'; '.join(findings) if findings else 'no major markers flagged'}. "
        f"Then review the affected systems ({', '.join(systems) if systems else 'none clearly clustered'}) and the current next steps: "
        f"{' '.join(report.get('recommended_next_steps', [])[:3])}. "
        f"Overall urgency is {derived.get('urgency_score', 0)}/100."
    )


def _similar_case_summary(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    similar = payload.get("dashboard_enrichment", {}).get("similar_cases", [])[:3]
    if not similar:
        return "I do not have strong similar-case matches stored yet for this patient.", []
    lines = []
    for case in similar:
        overlap = ", ".join(case.get("overlap_markers", [])) or "general marker profile"
        lines.append(
            f"{case.get('patient_name')} ({case.get('mode')}) with similarity {case.get('similarity_score')}%, overlapping on {overlap}"
        )
    return "Closest stored cases: " + "; ".join(lines) + ".", similar


def _feature_response(payload: dict[str, Any], feature: str) -> tuple[str, list[dict[str, Any]]]:
    snapshot = _feature_snapshot(payload)
    item = snapshot.get(feature)
    if not item:
        return f"I do not have a parsed value for {feature} in this case.", []
    explanation = FEATURE_EXPLANATIONS.get(feature, "This marker should be interpreted in the context of the rest of the panel.")
    answer = (
        f"{feature} is {item['value']} against reference {item['reference_low']}-{item['reference_high']}, "
        f"so it is currently {item['status']} with {item['severity']} severity. "
        f"{explanation}"
    )
    return answer, [item]


def _blood_pressure_response(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    snapshot = _feature_snapshot(payload)
    systolic = snapshot.get("Systolic Blood Pressure")
    diastolic = snapshot.get("Diastolic Blood Pressure")
    facts = [item for item in [systolic, diastolic] if item]
    if not facts:
        return "I do not have parsed blood pressure values for this case.", []

    parts = []
    if systolic:
        parts.append(
            f"systolic is {systolic['value']} against {systolic['reference_low']}-{systolic['reference_high']} ({systolic['status']}, {systolic['severity']})"
        )
    if diastolic:
        parts.append(
            f"diastolic is {diastolic['value']} against {diastolic['reference_low']}-{diastolic['reference_high']} ({diastolic['status']}, {diastolic['severity']})"
        )

    answer = (
        "The blood pressure pattern is: "
        + "; ".join(parts)
        + ". Elevated systolic or diastolic pressure increases cardiovascular workload, so this belongs in the main review priorities for this report."
    )
    return answer, facts


def _system_response(payload: dict[str, Any], systems: list[str]) -> tuple[str, list[dict[str, Any]]]:
    insights = payload.get("feature_outputs", {}).get("system_insights_card", {})
    snapshot = payload.get("report_agent_output", {}).get("patient_snapshot", {})
    affected = set(snapshot.get("systems_affected", []))
    system_lines = []
    facts: list[dict[str, Any]] = []

    for system in systems:
        lines = insights.get(system, [])
        if not lines:
            qualifier = "is flagged" if system in affected else "is not strongly flagged"
            system_lines.append(f"{system.title()} {qualifier} in the current derived report.")
            continue
        preview = "; ".join(lines[:3])
        system_lines.append(f"{system.title()}: {preview}")
        facts.append({"system": system, "observations": lines[:5], "affected": system in affected})

    if not system_lines:
        return "I do not see a clearly matched body-system question in the current case data.", []

    answer = "From the parsed report, " + " ".join(system_lines)
    return answer, facts


def _priority_patient_response(payload: dict[str, Any]) -> str:
    patient_name = payload.get("case_metadata", {}).get("patient_name", "this patient")
    derived = payload.get("derived_features", {})
    report = payload.get("report_agent_output", {})
    top_markers = [item.get("feature") for item in payload.get("derived_features", {}).get("top_abnormal_markers", [])[:4] if item.get("feature")]
    systems = report.get("patient_snapshot", {}).get("systems_affected", [])
    return (
        f"If I explained it simply to {patient_name}, I would say the most important things right now are "
        f"{', '.join(top_markers) if top_markers else 'the main flagged markers'}, because they are driving the highest concern in the report. "
        f"The current priority is {derived.get('care_priority_label', 'Monitor')} with urgency {derived.get('urgency_score', 0)}/100, "
        f"and the main affected areas are {', '.join(systems) if systems else 'not concentrated into one system'}."
    )


def _measured_highlights_response(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    measured = payload.get("report_agent_output", {}).get("measured_highlights", [])
    if not measured:
        measured = _top_marker_lines(payload, limit=4)
    answer = (
        "The key measured highlights from this case are: "
        + "; ".join(measured[:4])
        + ". These are the main values the agent is using for review and next-step planning."
    )
    return answer, measured[:4]


def _available_data_response(payload: dict[str, Any]) -> dict[str, Any]:
    patient_name = payload.get("case_metadata", {}).get("patient_name", "the active patient")
    inventory = payload.get("dashboard_enrichment", {}).get("available_details", {})
    source = payload.get("dashboard_enrichment", {}).get("source_overview", {})
    answer = (
        f"For {patient_name}, I have the uploaded document source, parsed lab markers, reference ranges, derived risk features, "
        f"verified report outputs, medication-education guidance, similar-case matches, and report artifacts. "
        f"The parser captured {source.get('parsed_feature_count', 0)} features with {source.get('missing_feature_count', 0)} missing. "
        f"Available section counts are raw inputs: {inventory.get('counts', {}).get('raw_input_field_count', 0)}, "
        f"report fields: {inventory.get('counts', {}).get('report_field_count', 0)}, derived fields: {inventory.get('counts', {}).get('derived_field_count', 0)}."
    )
    return {"answer": answer, "supporting_facts": inventory, "citations": []}


def _medication_response(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    medication = payload.get("dashboard_enrichment", {}).get("medication_guidance", {})
    matched = medication.get("matched_rules", [])
    sources = medication.get("sources", [])
    if not matched:
        return (
            "I do not see a strong medication-pattern match from the current case data. That does not rule out treatment; it just means the case needs clinician judgement rather than a simple rule-based medication summary.",
            [],
            sources,
        )

    summary_lines = []
    for rule in matched[:3]:
        classes = ", ".join(item["label"] for item in rule.get("medication_classes", [])[:4])
        triggers = ", ".join(rule.get("trigger_features", []))
        summary_lines.append(f"{rule['category']} because of {triggers}: common classes discussed include {classes}.")

    answer = (
        medication.get("summary", "")
        + " "
        + " ".join(summary_lines)
        + " Use this as educational context only and confirm actual treatment choice with a clinician."
    ).strip()
    return answer, matched, sources


def _build_llm_context(payload: dict[str, Any], question: str, deterministic_answer: str, history: list[dict[str, Any]]) -> tuple[str, str]:
    patient_name = payload.get("case_metadata", {}).get("patient_name", "the active patient")
    report = payload.get("report_agent_output", {})
    derived = payload.get("derived_features", {})
    medication = payload.get("dashboard_enrichment", {}).get("medication_guidance", {})
    similar = payload.get("dashboard_enrichment", {}).get("similar_cases", [])[:3]
    sources = medication.get("sources", [])
    mcp_context = payload.get("dashboard_enrichment", {}).get("mcp_context", [])
    case_memory = payload.get("dashboard_enrichment", {}).get("case_memory", {})
    recent_history = history[-4:] if history else []
    chat_skill = build_skill_block(["chat_agent_skill.md"])

    system_prompt = (
        "You are the BodyWise clinical chat agent. "
        "Answer conversationally, but use only the provided case context, source-backed medication facts, and retrieved history. "
        "Do not invent diagnoses, drug instructions, dosages, or unsupported medical claims. "
        "If the user asks beyond the available facts, say the case data is insufficient. "
        "When medications are mentioned, present them as educational classes that may be discussed with a clinician, not as a prescription. "
        "Keep the answer short, easy to understand, and data-backed. "
        "Prefer 2 short paragraphs max. "
        "Use simple language. "
        "When useful, preserve exact measured values, reference ranges, and short next steps."
    )
    if chat_skill:
        system_prompt += "\n\n" + chat_skill

    user_prompt = (
        f"Patient: {patient_name}\n"
        f"Priority: {derived.get('care_priority_label')} | Urgency: {derived.get('urgency_score')}/100\n"
        f"Systems affected: {', '.join(report.get('patient_snapshot', {}).get('systems_affected', []))}\n"
        f"Top abnormalities: {'; '.join(_top_marker_lines(payload, limit=5))}\n"
        f"Recommended next steps: {' '.join(report.get('recommended_next_steps', [])[:3])}\n"
        f"Agent next steps: {' '.join(report.get('agent_next_steps', [])[:3])}\n"
        f"Medication guidance summary: {medication.get('summary', 'None')}\n"
        f"Medication categories: "
        + " | ".join(
            f"{rule.get('category')}: {', '.join(item['label'] for item in rule.get('medication_classes', [])[:4])}"
            for rule in medication.get("matched_rules", [])[:4]
        )
        + "\n"
        + f"Similar cases: "
        + " | ".join(
            f"{case.get('patient_name')} {case.get('similarity_score')}% ({', '.join(case.get('overlap_markers', []))})"
            for case in similar
        )
        + "\n"
        + f"MCP context: {mcp_context}\n"
        + f"Memory MCP: {case_memory}\n"
        + f"Source-backed references: {sources}\n"
        + f"Recent chat history: {recent_history}\n"
        + f"Deterministic draft answer: {deterministic_answer}\n"
        + f"User question: {question}\n"
        + "Rewrite or improve the draft answer using only the provided facts. Do not add outside medical claims. "
        + "Keep it concise and easy. Prefer a three-part shape when relevant: main answer, measured data, next steps."
    )
    return system_prompt, user_prompt


def _try_llm_refine(payload: dict[str, Any], question: str, deterministic_answer: str, history: list[dict[str, Any]]) -> str | None:
    try:
        client = LLMClient()
        system_prompt, user_prompt = _build_llm_context(payload, question, deterministic_answer, history)
        answer = client.chat_text(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=260)
        return answer.strip() if answer else None
    except Exception:
        return None


def _deterministic_answer(payload: dict[str, Any], question: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    patient_name = payload.get("case_metadata", {}).get("patient_name", "the active patient")
    report = payload.get("report_agent_output", {})
    derived = payload.get("derived_features", {})
    lowered = question.lower().strip()

    feature = _find_feature(question)
    if not feature and _mentions_followup_reference(question):
        feature = _infer_feature_from_history(history)

    if lowered in {"hi", "hello", "hey", "start"}:
        return {
            "answer": (
                f"Hi - I have {patient_name}'s parsed report loaded. I can summarize it, explain any marker, compare it to normal ranges, "
                "point out the main risks, show similar cases, and discuss medication classes in an educational way."
            ),
            "supporting_facts": [],
            "citations": [],
        }

    if "what data" in lowered or "available data" in lowered or "detail" in lowered or "what do you have" in lowered:
        return _available_data_response(payload)

    if "matters most" in lowered or "most important" in lowered or "right now" in lowered:
        return {
            "answer": _priority_patient_response(payload),
            "supporting_facts": report.get("monitoring_priorities", [])[:5],
            "citations": [],
        }

    if "measured" in lowered or "measure" in lowered or "exact value" in lowered or "highlight" in lowered:
        answer, facts = _measured_highlights_response(payload)
        return {"answer": answer, "supporting_facts": facts, "citations": []}

    if any(term in lowered for term in ["drug", "drugs", "medication", "medicine", "meds"]):
        answer, facts, citations = _medication_response(payload)
        return {"answer": answer, "supporting_facts": facts, "citations": citations}

    if any(term in lowered for term in ["diet", "food", "eat", "nutrition", "meal", "avoid"]):
        answer, facts = _diet_guidance(payload)
        return {"answer": answer, "supporting_facts": facts, "citations": payload.get("dashboard_enrichment", {}).get("medication_guidance", {}).get("sources", [])}

    if any(term in lowered for term in ["exercise", "workout", "activity", "walk", "gym"]):
        return {"answer": _exercise_guidance(payload), "supporting_facts": report.get("monitoring_priorities", [])[:4], "citations": []}

    if "blood pressure" in lowered or ("systolic" in lowered and "diastolic" in lowered):
        answer, facts = _blood_pressure_response(payload)
        return {"answer": answer, "supporting_facts": facts, "citations": []}

    systems = _find_systems(question)
    if systems:
        answer, facts = _system_response(payload, systems)
        return {"answer": answer, "supporting_facts": facts, "citations": []}

    if feature and feature != "medication":
        answer, facts = _feature_response(payload, feature)
        return {"answer": answer, "supporting_facts": facts, "citations": []}

    if "clinician" in lowered or "doctor" in lowered or "review first" in lowered:
        return {"answer": _clinician_review(payload), "supporting_facts": report.get("key_findings", [])[:5], "citations": []}

    if "similar" in lowered or "history" in lowered or "previous case" in lowered:
        answer, facts = _similar_case_summary(payload)
        return {"answer": answer, "supporting_facts": facts, "citations": []}

    if "summary" in lowered or "summarize" in lowered:
        audience = "general"
        if "patient" in lowered or "simple" in lowered:
            audience = "patient"
        elif "clinician" in lowered or "doctor" in lowered:
            audience = "clinician"
        return {
            "answer": _general_summary(payload, audience=audience),
            "supporting_facts": _top_marker_lines(payload, limit=4),
            "citations": [],
        }

    if "system" in lowered:
        systems = report.get("patient_snapshot", {}).get("systems_affected", [])
        insights = payload.get("feature_outputs", {}).get("system_insights_card", {})
        answer = (
            f"The main systems showing abnormalities are {', '.join(systems) if systems else 'none clearly clustered'}. "
            f"Key observations include: "
            + " ".join(
                f"{system}: {', '.join(insights.get(system, [])[:2])}"
                for system in systems[:3]
            )
        )
        return {"answer": answer, "supporting_facts": systems, "citations": []}

    if "urgent" in lowered or "critical" in lowered or "risk" in lowered or "worry" in lowered:
        critical = report.get("critical_markers", [])
        answer = (
            f"{patient_name} is currently tagged {derived.get('care_priority_label', 'Monitor')} with urgency "
            f"{derived.get('urgency_score', 0)}/100. Critical or standout markers are "
            f"{', '.join(critical) if critical else 'not strongly flagged as critical'}, and the main priorities are "
            f"{', '.join(report.get('monitoring_priorities', [])[:5]) or 'not yet assigned'}."
        )
        return {"answer": answer, "supporting_facts": critical, "citations": []}

    if "follow" in lowered or "next" in lowered or "plan" in lowered:
        steps = report.get("recommended_next_steps", [])
        questions = report.get("follow_up_questions", [])
        answer = (
            "The current next-step plan is: "
            + (" ".join(steps) if steps else "No next-step plan is stored.")
            + (" Follow-up questions to clarify: " + "; ".join(questions[:3]) if questions else "")
        )
        return {"answer": answer, "supporting_facts": steps + questions[:3], "citations": []}

    if any(
        phrase in lowered
        for phrase in [
            "patient name",
            "client name",
            "who is the patient",
            "who is this patient",
            "who is the client",
            "active patient",
            "active client",
        ]
    ):
        ingestion = payload.get("raw_intake", {}).get("parsed_document", {}).get("document_ingestion", {})
        return {
            "answer": (
                f"The active patient is {patient_name}. Source file is {ingestion.get('file_name', 'legacy record')}, "
                f"and the current report priority is {derived.get('care_priority_label', 'Monitor')}."
            ),
            "supporting_facts": [patient_name, ingestion.get("file_name", "legacy record")],
            "citations": [],
        }

    return {
        "answer": (
            f"I have {patient_name}'s full parsed context loaded. The quick summary is: "
            f"{_general_summary(payload)} You can ask me for a patient-friendly summary, clinician review order, "
            "diet guidance, medication classes, feature explanations, similar cases, or what data is available."
        ),
        "supporting_facts": _top_marker_lines(payload, limit=4),
        "citations": [],
    }


def _specialist_next_steps(
    agent_key: str,
    payload: dict[str, Any],
    focus_items: list[dict[str, Any]],
    history: list[dict[str, Any]],
) -> list[str]:
    general_steps = payload.get("report_agent_output", {}).get("recommended_next_steps", [])
    focus_names = [item.get("feature") for item in focus_items[:3] if item.get("feature")]
    focus_text = ", ".join(focus_names) if focus_names else "the main markers in this specialty"

    domain_steps = {
        "dr_emily_carter": [
            f"Review sugar-control markers first: {focus_text}.",
            "Keep meals simpler, watch sugar-heavy foods, and review long-term glucose control with a clinician.",
        ],
        "dr_james_brooks": [
            f"Review heart-risk markers first: {focus_text}.",
            "Check blood pressure trend, salt intake, and lipid follow-up with a clinician.",
        ],
        "dr_hannah_reed": [
            f"Review blood-count markers first: {focus_text}.",
            "Discuss anemia or infection context and whether a repeat CBC is needed.",
        ],
        "dr_olivia_bennett": [
            f"Review whole-body markers first: {focus_text}.",
            "Check inflammation, liver, and kidney context with the next clinical review.",
        ],
    }

    shared_context = _recent_specialist_context(history, agent_key)
    shared_step = []
    if shared_context:
        shared_step.append(f"Also keep {shared_context[-1]['name']}'s earlier note in mind during follow-up.")

    combined = domain_steps.get(agent_key, []) + shared_step + general_steps[:2]
    deduped = []
    for item in combined:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:3]


def _specialist_main_answer(
    agent_key: str,
    payload: dict[str, Any],
    question: str,
    focus_items: list[dict[str, Any]],
    history: list[dict[str, Any]],
) -> str:
    agent = SPECIALIST_AGENTS[agent_key]
    lowered = question.lower()
    if not focus_items:
        return f"{agent['name']} here. In my area, this report does not show a strong flagged pattern right now."

    lead = focus_items[:3]
    marker_bits = ", ".join(f"{item['feature']} {item['value']}" for item in lead)
    shared_line = _shared_context_line(agent_key, lead, history)

    if any(term in lowered for term in ["diet", "food", "eat", "meal", "nutrition"]):
        diet_examples = payload.get("report_agent_output", {}).get("diet_examples", [])
        chosen = diet_examples[0] if diet_examples else "Keep meals simple, balanced, and lower in processed foods."
        base = f"{agent['name']} here. From the {agent['title'].lower()} view, the main food focus is: {chosen}"
        return f"{base} {shared_line}".strip()

    if any(term in lowered for term in ["drug", "medicine", "medication", "meds"]):
        medication = payload.get("dashboard_enrichment", {}).get("medication_guidance", {})
        matched_labels = []
        for rule in medication.get("matched_rules", []):
            if set(rule.get("trigger_features", [])).intersection(agent["focus_features"]):
                matched_labels.extend(item.get("label") for item in rule.get("medication_classes", [])[:3] if item.get("label"))
        if matched_labels:
            unique = []
            for label in matched_labels:
                if label not in unique:
                    unique.append(label)
            base = f"{agent['name']} here. In my area, common medication classes discussed for this pattern include {', '.join(unique[:4])}. This is educational only, not a prescription."
            return f"{base} {shared_line}".strip()
        base = f"{agent['name']} here. In my area, I would keep medication talk general and clinician-led because the lab pattern still needs full clinical review."
        return f"{base} {shared_line}".strip()

    if any(term in lowered for term in ["why", "explain", "reason"]) and lead:
        first = lead[0]
        base = f"{agent['name']} here. I am focusing on {first['feature']} because it is {first['status']} at {first['value']} against {first['reference_low']}-{first['reference_high']}."
        return f"{base} {shared_line}".strip()

    base = f"{agent['name']} here. From the {agent['title'].lower()} view, the main things I see are {marker_bits}."
    return f"{base} {shared_line}".strip()


def _answer_as_specialist(payload: dict[str, Any], question: str, agent_key: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    agent = SPECIALIST_AGENTS[agent_key]
    focus_items = _specialist_focus_items(payload, agent_key)
    abnormal_focus = [item for item in focus_items if item.get("status") != "normal"] or focus_items[:3]
    measure_lines = [_format_measure_line(item) for item in abnormal_focus[:3]]
    next_steps = _specialist_next_steps(agent_key, payload, abnormal_focus, history)
    citations = _specialist_citations(agent_key)
    main_answer = _specialist_main_answer(agent_key, payload, question, abnormal_focus, history)
    parts = [main_answer]
    if measure_lines:
        parts.append("Measured data:\n- " + "\n- ".join(measure_lines[:2]))
    if next_steps:
        parts.append("Next steps:\n- " + "\n- ".join(next_steps[:2]))
    formatted = "\n\n".join(parts)
    return {
        "answer": formatted,
        "supporting_facts": abnormal_focus,
        "measure_lines": measure_lines,
        "next_steps": next_steps,
        "citations": citations,
        "agent": {
            "key": agent_key,
            "name": agent["name"],
            "title": agent["title"],
            "icon": agent["icon"],
        },
    }


def answer_case_question(
    payload: dict[str, Any],
    question: str,
    history: list[dict[str, Any]] | None = None,
    agent_key: str | None = None,
) -> dict[str, Any]:
    history = history or []
    if agent_key in SPECIALIST_AGENTS:
        return _answer_as_specialist(payload, question, agent_key, history)
    deterministic = _deterministic_answer(payload, question, history)
    lowered = question.lower()
    use_llm = not (
        _find_feature(question)
        or _find_systems(question)
        or "blood pressure" in lowered
        or "what data" in lowered
        or "available data" in lowered
        or "similar case" in lowered
        or "explain " in lowered
        or "matters most" in lowered
        or "most important" in lowered
        or "summary" in lowered
        or "summarize" in lowered
        or "clinician" in lowered
        or "doctor" in lowered
        or "review first" in lowered
        or "diet" in lowered
        or "food" in lowered
        or "eat" in lowered
        or "nutrition" in lowered
        or "drug" in lowered
        or "medication" in lowered
        or "medicine" in lowered
        or "urgent" in lowered
        or "risk" in lowered
        or "critical" in lowered
        or "follow" in lowered
        or "next" in lowered
        or "plan" in lowered
        or "exercise" in lowered
        or "workout" in lowered
        or "activity" in lowered
        or "measured" in lowered
        or "highlight" in lowered
    )
    llm_answer = _try_llm_refine(payload, question, deterministic["answer"], history) if use_llm else None
    if llm_answer:
        deterministic["answer"] = _shorten_answer_text(llm_answer)
    measure_lines = _extract_supporting_measure_lines(payload, question, deterministic.get("supporting_facts", []))
    next_steps = _extract_next_steps(payload, question)
    deterministic["measure_lines"] = measure_lines
    deterministic["next_steps"] = next_steps
    if "Measured data:" not in deterministic["answer"] and "Next steps:" not in deterministic["answer"]:
        deterministic["answer"] = _format_answer_with_measures(
            deterministic["answer"],
            measure_lines=measure_lines,
            next_steps=next_steps,
        )
    deterministic["agent"] = {
        "key": "general",
        "name": "General Review",
        "title": "Case-wide Assistant",
        "icon": "general",
    }
    return deterministic

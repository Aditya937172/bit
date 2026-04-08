from __future__ import annotations

from collections import defaultdict
from typing import Any


FACT_SOURCES = {
    "aha_bp_meds": {
        "title": "Types of Blood Pressure Medications",
        "url": "https://www.heart.org/en/health-topics/high-blood-pressure/changes-you-can-make-to-manage-high-blood-pressure/types-of-blood-pressure-medications",
        "publisher": "American Heart Association",
    },
    "ada_type2_meds": {
        "title": "What Are My Options for Type 2 Diabetes Medications?",
        "url": "https://diabetes.org/health-wellness/medication/type-2-medications",
        "publisher": "American Diabetes Association",
    },
    "aha_chol_meds": {
        "title": "Cholesterol Medications",
        "url": "https://www.heart.org/en/health-topics/cholesterol/prevention-and-treatment-of-high-cholesterol-hyperlipidemia/cholesterol-medications",
        "publisher": "American Heart Association",
    },
    "aha_tg_meds": {
        "title": "Prescription omega-3 medications work for high triglycerides, advisory says",
        "url": "https://www.heart.org/en/news/2019/08/19/prescription-omega3-medications-work-for-high-triglycerides-advisory-says",
        "publisher": "American Heart Association",
    },
    "nhlbi_anemia_tx": {
        "title": "Anemia - Treatment and Management",
        "url": "https://www.nhlbi.nih.gov/health/anemia/treatment",
        "publisher": "NHLBI, NIH",
    },
    "nhlbi_platelet_tx": {
        "title": "Platelet Disorders - Treatment",
        "url": "https://www.nhlbi.nih.gov/health/platelet-disorders/treatment",
        "publisher": "NHLBI, NIH",
    },
    "aha_heart_meds": {
        "title": "Types of Heart Medications",
        "url": "https://www.heart.org/en/health-topics/heart-attack/treatment-of-a-heart-attack/cardiac-medications",
        "publisher": "American Heart Association",
    },
}


MEDICATION_RULES = [
    {
        "name": "Blood Pressure Control",
        "match_features": {"Systolic Blood Pressure", "Diastolic Blood Pressure"},
        "priority_weight": 26,
        "message": "Blood-pressure markers are elevated, so antihypertensive medication classes are commonly discussed with clinicians if lifestyle measures alone are not enough.",
        "classes": [
            {"label": "Diuretics", "score": 92, "description": "Common first-line blood pressure class."},
            {"label": "ACE Inhibitors", "score": 88, "description": "Commonly used blood pressure class."},
            {"label": "ARBs", "score": 86, "description": "Often used when ACE inhibitors are not tolerated or as an alternative."},
            {"label": "Calcium Channel Blockers", "score": 84, "description": "Common blood pressure lowering class."},
            {"label": "Beta Blockers", "score": 70, "description": "Used in some blood pressure and heart-related situations."},
        ],
        "source_ids": ["aha_bp_meds"],
    },
    {
        "name": "Glucose Management",
        "match_features": {"Glucose", "HbA1c", "Insulin"},
        "priority_weight": 28,
        "message": "Glucose-related markers are elevated, so diabetes medication classes may become relevant depending on diagnosis, severity, and clinician assessment.",
        "classes": [
            {"label": "Metformin", "score": 94, "description": "Common early oral medication for type 2 diabetes discussions."},
            {"label": "GLP-1 Receptor Agonists", "score": 88, "description": "Often discussed when weight and glucose both matter."},
            {"label": "SGLT2 Inhibitors", "score": 84, "description": "Common class for type 2 diabetes management discussions."},
            {"label": "Insulin", "score": 78, "description": "Can be used when glucose control needs stronger treatment."},
            {"label": "Sulfonylureas", "score": 62, "description": "Older oral class that may still be used in some cases."},
        ],
        "source_ids": ["ada_type2_meds"],
    },
    {
        "name": "Cholesterol Lowering",
        "match_features": {"LDL Cholesterol", "Cholesterol", "HDL Cholesterol"},
        "priority_weight": 22,
        "message": "Lipid markers are abnormal, so cholesterol-lowering medication classes may be discussed based on overall cardiovascular risk.",
        "classes": [
            {"label": "Statins", "score": 96, "description": "Most common lipid-lowering class discussed for LDL reduction."},
            {"label": "Ezetimibe", "score": 74, "description": "Sometimes added when LDL goals are not reached."},
            {"label": "PCSK9 Inhibitors", "score": 58, "description": "More specialized LDL-lowering option in selected patients."},
            {"label": "Bempedoic Acid", "score": 46, "description": "Another LDL-lowering option in selected cases."},
        ],
        "source_ids": ["aha_chol_meds"],
    },
    {
        "name": "Triglyceride Lowering",
        "match_features": {"Triglycerides"},
        "priority_weight": 20,
        "message": "High triglycerides can push discussions toward triglyceride-focused therapy in addition to lifestyle measures.",
        "classes": [
            {"label": "Prescription Omega-3", "score": 82, "description": "Prescription omega-3 therapies may be used for high triglycerides."},
            {"label": "Fibrates", "score": 76, "description": "Often discussed for triglyceride lowering."},
            {"label": "Statins", "score": 60, "description": "Also part of lipid management when overall risk is elevated."},
        ],
        "source_ids": ["aha_tg_meds", "aha_chol_meds"],
    },
    {
        "name": "Anemia Support",
        "match_features": {"Hemoglobin", "Red Blood Cells", "Hematocrit", "Mean Corpuscular Volume", "Mean Corpuscular Hemoglobin"},
        "priority_weight": 16,
        "message": "Low blood-count markers can fit anemia patterns, but treatment depends on the cause, so medication guidance should stay cause-specific.",
        "classes": [
            {"label": "Iron Supplements", "score": 72, "description": "Used when iron-deficiency anemia is confirmed."},
            {"label": "Vitamin B12", "score": 54, "description": "Used if B12 deficiency is the cause."},
            {"label": "Folate", "score": 48, "description": "Used if folate deficiency is identified."},
        ],
        "source_ids": ["nhlbi_anemia_tx"],
    },
    {
        "name": "Platelet Disorder Review",
        "match_features": {"Platelets"},
        "priority_weight": 10,
        "message": "Low platelet markers should be treated very cautiously because treatment depends heavily on the cause and severity.",
        "classes": [
            {"label": "Anti-D Immunoglobulin", "score": 34, "description": "Used in some immune thrombocytopenia situations."},
            {"label": "Rituximab", "score": 28, "description": "May be used in some immune platelet disorders."},
        ],
        "source_ids": ["nhlbi_platelet_tx"],
    },
    {
        "name": "Cardiac Urgency Context",
        "match_features": {"Troponin", "Heart Rate", "C-reactive Protein"},
        "priority_weight": 14,
        "message": "Cardiac stress markers increase urgency, but treatment choices are condition-specific and should not be guessed from labs alone.",
        "classes": [
            {"label": "Antiplatelet Therapy", "score": 38, "description": "Discussed in some heart-related care pathways."},
            {"label": "Anticoagulants", "score": 30, "description": "Used in selected cardiovascular/clotting contexts only."},
            {"label": "Beta Blockers", "score": 32, "description": "May appear in some heart-related medication plans."},
        ],
        "source_ids": ["aha_heart_meds"],
    },
]


def build_available_details(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("raw_intake", {})
    report = payload.get("report_agent_output", {})
    derived = payload.get("derived_features", {})
    enrichment = payload.get("dashboard_enrichment", {})
    return {
        "case_metadata": sorted(list(payload.get("case_metadata", {}).keys())),
        "raw_input_fields": sorted(list(raw.get("normalized_patient_input", {}).keys())),
        "report_fields": sorted(list(report.keys())),
        "derived_fields": sorted(list(derived.keys())),
        "enrichment_fields": sorted(list(enrichment.keys())),
        "counts": {
            "raw_input_field_count": len(raw.get("normalized_patient_input", {})),
            "report_field_count": len(report),
            "derived_field_count": len(derived),
        },
    }


def build_medication_guidance(payload: dict[str, Any]) -> dict[str, Any]:
    top_features = {
        item.get("feature")
        for item in payload.get("derived_features", {}).get("top_abnormal_markers", [])
        if item.get("feature")
    }
    matched_rules = []
    graph_by_class: dict[str, dict[str, Any]] = defaultdict(lambda: {"label": "", "value": 0, "category": "", "source_ids": []})

    for rule in MEDICATION_RULES:
        overlap = sorted(top_features.intersection(rule["match_features"]))
        if not overlap:
            continue
        matched_classes = []
        for drug_class in rule["classes"]:
            graph_entry = graph_by_class[drug_class["label"]]
            graph_entry["label"] = drug_class["label"]
            graph_entry["value"] = max(graph_entry["value"], drug_class["score"])
            graph_entry["category"] = rule["name"]
            graph_entry["source_ids"] = sorted(set(graph_entry["source_ids"] + rule["source_ids"]))
            matched_classes.append(drug_class)

        matched_rules.append(
            {
                "category": rule["name"],
                "message": rule["message"],
                "trigger_features": overlap,
                "medication_classes": matched_classes,
                "source_ids": rule["source_ids"],
            }
        )

    graph = sorted(graph_by_class.values(), key=lambda item: item["value"], reverse=True)[:8]
    source_ids = sorted({source_id for rule in matched_rules for source_id in rule["source_ids"]})
    sources = [FACT_SOURCES[source_id] for source_id in source_ids if source_id in FACT_SOURCES]

    if matched_rules:
        summary = (
            "This medication section is educational only. It highlights drug classes commonly discussed for the abnormal marker patterns in this case; "
            "it is not a prescription recommendation."
        )
    else:
        summary = (
            "No strong medication-pattern mapping was triggered from the current abnormalities. "
            "Lifestyle, repeat testing, and clinician review may still be important."
        )

    return {
        "summary": summary,
        "educational_only": True,
        "matched_rules": matched_rules,
        "graph": graph,
        "sources": sources,
    }

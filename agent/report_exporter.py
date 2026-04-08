from __future__ import annotations

import os
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _list_to_paragraph(items: list[str], style: ParagraphStyle) -> list:
    flow = []
    for item in items:
        flow.append(Paragraph(f"- {item}", style))
        flow.append(Spacer(1, 6))
    return flow


def _summary_points(text: str) -> list[str]:
    parts = [item.strip(" .") for item in text.split(".") if item.strip()]
    return parts[:4]


def export_pdf_report(payload: dict[str, Any], output_path: str) -> str:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    title = styles["Title"]
    heading = styles["Heading2"]
    body = styles["BodyText"]
    body.leading = 15

    story = []
    report = payload.get("report_agent_output", {})
    document = payload.get("document_agent_output", {})
    derived = payload.get("derived_features", {})
    feature_outputs = payload.get("feature_outputs", {})
    visual = payload.get("visual_report_output", {})

    story.append(Paragraph(document.get("title", "Clinical Report"), title))
    story.append(Spacer(1, 12))

    image_files = visual.get("saved_files", [])
    if image_files:
        image_path = image_files[0]
        if os.path.exists(image_path):
            story.append(Image(image_path, width=6.9 * inch, height=4.4 * inch))
            story.append(Spacer(1, 14))

    story.append(Paragraph(report.get("headline", "Summary"), heading))
    summary_points = document.get("summary_points", []) or _summary_points(report.get("summary", ""))
    story.extend(_list_to_paragraph(summary_points, body))
    story.append(Spacer(1, 12))

    snapshot = report.get("patient_snapshot", {})
    snapshot_table = Table(
        [
            ["Abnormal markers", str(snapshot.get("abnormal_marker_count", ""))],
            ["Normal markers", str(snapshot.get("normal_marker_count", ""))],
            ["Systems affected", ", ".join(snapshot.get("systems_affected", []))],
            ["Urgency score", str(derived.get("urgency_score", ""))],
            ["Care priority", str(derived.get("care_priority_label", ""))],
        ],
        colWidths=[2.0 * inch, 4.8 * inch],
    )
    snapshot_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(Paragraph("Patient Snapshot", heading))
    story.append(snapshot_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Key Findings", heading))
    story.extend(_list_to_paragraph(report.get("key_findings", []), body))

    measured_highlights = report.get("measured_highlights", []) or document.get("measured_highlights", [])
    if measured_highlights:
        story.append(Paragraph("Measured Highlights", heading))
        story.extend(_list_to_paragraph(measured_highlights, body))

    story.append(Paragraph("Critical Markers", heading))
    story.extend(_list_to_paragraph(report.get("critical_markers", []), body))

    story.append(Paragraph("Monitoring Priorities", heading))
    story.extend(_list_to_paragraph(report.get("monitoring_priorities", []), body))

    story.append(Paragraph("Follow-up Questions", heading))
    story.extend(_list_to_paragraph(report.get("follow_up_questions", []), body))

    story.append(Paragraph("Recommended Next Steps", heading))
    story.extend(_list_to_paragraph(report.get("recommended_next_steps", []), body))

    agent_next_steps = report.get("agent_next_steps", [])
    if agent_next_steps:
        story.append(Paragraph("Agent Next Steps", heading))
        story.extend(_list_to_paragraph(agent_next_steps, body))

    diet_examples = report.get("diet_examples", []) or document.get("diet_examples", [])
    if diet_examples:
        story.append(Paragraph("Diet Examples", heading))
        story.extend(_list_to_paragraph(diet_examples, body))

    story.append(Paragraph("Systems Analysis", heading))
    for system_name, system_items in feature_outputs.get("system_insights_card", {}).items():
        if not system_items:
            continue
        story.append(Paragraph(system_name.title(), styles["Heading3"]))
        story.extend(_list_to_paragraph(system_items, body))

    story.append(Paragraph("Patient-Friendly Summary", heading))
    story.append(Paragraph(document.get("patient_friendly_summary", ""), body))
    story.append(Spacer(1, 12))

    if visual.get("fallback_reason"):
        story.append(Paragraph("Visual Notes", heading))
        story.append(Paragraph("A local infographic was generated because the external image model was unavailable.", body))
        story.append(Spacer(1, 12))

    doc.build(story)
    return output_path

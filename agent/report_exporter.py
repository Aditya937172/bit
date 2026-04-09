from __future__ import annotations

import os
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


PRIMARY = colors.HexColor("#6B8E23")
PRIMARY_DARK = colors.HexColor("#556B2F")
PRIMARY_LIGHT = colors.HexColor("#F1F7E7")
TEXT_MAIN = colors.HexColor("#1D1D1F")
TEXT_MUTED = colors.HexColor("#667085")
BORDER = colors.HexColor("#D9E3CB")
CARD = colors.HexColor("#FBFDF8")
ALERT = colors.HexColor("#C96D34")


def _safe_list(items: list[str] | None) -> list[str]:
    return [str(item).strip() for item in (items or []) if str(item).strip()]


def _summary_points(text: str) -> list[str]:
    parts = [item.strip(" .") for item in text.split(".") if item.strip()]
    return parts[:4]


def _build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    styles: dict[str, ParagraphStyle] = {
        "title": ParagraphStyle(
            "VisualTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=colors.white,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "VisualSubtitle",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=14,
            textColor=colors.white,
            alignment=TA_LEFT,
        ),
        "section": ParagraphStyle(
            "SectionHeader",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=14,
            textColor=colors.white,
            alignment=TA_LEFT,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=TEXT_MAIN,
        ),
        "muted": ParagraphStyle(
            "Muted",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=TEXT_MUTED,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=TEXT_MAIN,
            leftIndent=10,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=10,
            textColor=TEXT_MUTED,
        ),
        "metric_value": ParagraphStyle(
            "MetricValue",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=PRIMARY_DARK,
        ),
        "chip": ParagraphStyle(
            "Chip",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=PRIMARY_DARK,
        ),
    }
    return styles


def _section_header(text: str, width: float, styles: dict[str, ParagraphStyle]) -> Table:
    table = Table([[Paragraph(text, styles["section"])]], colWidths=[width])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PRIMARY),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("BOX", (0, 0), (-1, -1), 0, PRIMARY),
            ]
        )
    )
    return table


def _metric_cards(metrics: list[tuple[str, str]], width: float, styles: dict[str, ParagraphStyle]) -> Table:
    col_width = width / max(len(metrics), 1)
    cells = []
    for label, value in metrics:
        cells.append(
            Table(
                [[Paragraph(label, styles["metric_label"])], [Paragraph(value, styles["metric_value"])]],
                colWidths=[col_width - 8],
            )
        )
    wrapper = Table([cells], colWidths=[col_width] * len(cells))
    wrapper.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CARD),
                ("BOX", (0, 0), (-1, -1), 1, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 1, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    return wrapper


def _hero_block(title_text: str, subtitle_text: str, width: float, styles: dict[str, ParagraphStyle]) -> Table:
    content = [
        [Paragraph(title_text, styles["title"])],
        [Paragraph(subtitle_text, styles["subtitle"])],
    ]
    table = Table(content, colWidths=[width])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PRIMARY_DARK),
                ("BOX", (0, 0), (-1, -1), 0, PRIMARY_DARK),
                ("LEFTPADDING", (0, 0), (-1, -1), 18),
                ("RIGHTPADDING", (0, 0), (-1, -1), 18),
                ("TOPPADDING", (0, 0), (-1, -1), 18),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
            ]
        )
    )
    return table


def _list_card(title: str, items: list[str], width: float, styles: dict[str, ParagraphStyle], accent: colors.Color = PRIMARY_LIGHT) -> Table:
    rows: list[list[Any]] = [[Paragraph(f"<b>{title}</b>", styles["body"])]]
    if items:
        rows.extend([[Paragraph(f"- {item}", styles["bullet"])] for item in items])
    else:
        rows.append([Paragraph("No data available for this section.", styles["muted"])])

    table = Table(rows, colWidths=[width])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), accent),
                ("BOX", (0, 0), (-1, -1), 1, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return table


def _paired_cards(left: Table, right: Table, width: float) -> Table:
    gap = 10
    col_width = (width - gap) / 2
    wrapper = Table([[left, right]], colWidths=[col_width, col_width])
    wrapper.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return wrapper


def _snapshot_table(rows: list[list[str]], width: float, styles: dict[str, ParagraphStyle]) -> Table:
    formatted = [[Paragraph(f"<b>{label}</b>", styles["body"]), Paragraph(value, styles["body"])] for label, value in rows]
    table = Table(formatted, colWidths=[width * 0.35, width * 0.65])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, CARD]),
                ("BOX", (0, 0), (-1, -1), 1, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _detail_table(
    title: str,
    headers: list[str],
    rows: list[list[str]],
    width: float,
    styles: dict[str, ParagraphStyle],
    *,
    empty_text: str,
) -> list[Any]:
    table_rows: list[list[Any]] = [[Paragraph(f"<b>{header}</b>", styles["body"]) for header in headers]]
    if rows:
        for row in rows:
            table_rows.append([Paragraph(str(cell), styles["body"]) for cell in row])
    else:
        table_rows.append([Paragraph(empty_text, styles["muted"])] + [""] * (len(headers) - 1))

    column_width = width / max(len(headers), 1)
    table = Table(table_rows, colWidths=[column_width] * len(headers))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_LIGHT),
                ("TEXTCOLOR", (0, 0), (-1, 0), PRIMARY_DARK),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CARD]),
                ("BOX", (0, 0), (-1, -1), 1, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return [
        _section_header(title, width, styles),
        Spacer(1, 8),
        table,
    ]


def export_pdf_report(payload: dict[str, Any], output_path: str) -> str:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=32, leftMargin=32, topMargin=28, bottomMargin=28)
    styles = _build_styles()
    content_width = doc.width

    report = payload.get("report_agent_output", {})
    document = payload.get("document_agent_output", {})
    derived = payload.get("derived_features", {})
    feature_outputs = payload.get("feature_outputs", {})
    visual = payload.get("visual_report_output", {})
    enrichment = payload.get("dashboard_enrichment", {})
    snapshot = report.get("patient_snapshot", {})

    headline = report.get("headline", "Quick Health Report")
    summary = report.get("summary", "A structured clinical summary is available for this client.")
    summary_points = _safe_list(document.get("summary_points")) or _summary_points(summary)
    raw_intake = payload.get("raw_intake", {})
    ingestion = raw_intake.get("parsed_document", {}).get("document_ingestion", {})
    parsed_payload = raw_intake.get("parsed_document", {}).get("parsed_payload", {})

    metrics = [
        ("Urgency Score", str(derived.get("urgency_score", 0))),
        ("Care Priority", str(derived.get("care_priority_label", "Review"))),
        ("Abnormal Markers", str(snapshot.get("abnormal_marker_count", 0))),
        ("Systems Affected", str(len(snapshot.get("systems_affected", [])))),
    ]

    story: list[Any] = [
        _hero_block(
            headline,
            "Visual clinical report generated from parsed lab values, derived measures, and verified agent outputs.",
            content_width,
            styles,
        ),
        Spacer(1, 12),
    ]

    image_files = visual.get("saved_files", [])
    if image_files:
        image_path = image_files[0]
        if os.path.exists(image_path):
            story.append(Image(image_path, width=content_width, height=4.0 * inch))
            story.append(Spacer(1, 14))

    story.append(_metric_cards(metrics, content_width, styles))
    story.append(Spacer(1, 14))

    story.append(_section_header("Overall Report", content_width, styles))
    story.append(Spacer(1, 8))
    story.append(_list_card("Summary", summary_points, content_width, styles))
    story.append(Spacer(1, 12))

    overall_rows = [
        ["Patient", str(payload.get("case_metadata", {}).get("patient_name", "Imported Case"))],
        ["Source file", str(ingestion.get("file_name", "Uploaded report"))],
        ["Extraction mode", str(ingestion.get("extraction_mode", "local parsing"))],
        ["Parsed fields", str(parsed_payload.get("parsed_feature_count", 0))],
        ["Missing fields", str(parsed_payload.get("missing_feature_count", 0))],
        ["Verification", str(payload.get("verification_agent_output", {}).get("verification_status", "verified"))],
    ]
    story.append(_snapshot_table(overall_rows, content_width, styles))
    story.append(Spacer(1, 12))

    snapshot_rows = [
        ["Abnormal markers", str(snapshot.get("abnormal_marker_count", 0))],
        ["Normal markers", str(snapshot.get("normal_marker_count", 0))],
        ["Systems affected", ", ".join(snapshot.get("systems_affected", [])) or "Not flagged"],
        ["Urgency score", f"{derived.get('urgency_score', 0)}/100"],
        ["Care priority", str(derived.get("care_priority_label", "Review"))],
        ["Escalation level", str(derived.get("escalation_level", "monitor"))],
    ]
    story.append(_section_header("Patient Snapshot", content_width, styles))
    story.append(Spacer(1, 8))
    story.append(_snapshot_table(snapshot_rows, content_width, styles))
    story.append(Spacer(1, 12))

    key_findings = _safe_list(report.get("key_findings"))
    measured_highlights = _safe_list(report.get("measured_highlights") or document.get("measured_highlights"))
    monitoring_priorities = _safe_list(report.get("monitoring_priorities"))
    critical_markers = _safe_list(report.get("critical_markers"))
    next_steps = _safe_list(report.get("recommended_next_steps"))
    diet_examples = _safe_list(report.get("diet_examples") or document.get("diet_examples"))
    follow_up_questions = _safe_list(report.get("follow_up_questions"))
    agent_next_steps = _safe_list(report.get("agent_next_steps"))

    left_column = _list_card("Key Findings", key_findings[:5], (content_width - 10) / 2, styles)
    right_column = _list_card("Measured Highlights", measured_highlights[:5], (content_width - 10) / 2, styles, accent=colors.white)
    story.append(_paired_cards(left_column, right_column, content_width))
    story.append(Spacer(1, 12))

    left_column = _list_card("Critical Markers", critical_markers[:5], (content_width - 10) / 2, styles, accent=colors.HexColor("#FFF6ED"))
    right_column = _list_card("Monitoring Priorities", monitoring_priorities[:5], (content_width - 10) / 2, styles, accent=colors.white)
    story.append(_paired_cards(left_column, right_column, content_width))
    story.append(Spacer(1, 12))

    left_column = _list_card("Recommended Next Steps", next_steps[:5], (content_width - 10) / 2, styles)
    right_column = _list_card("Diet Examples", diet_examples[:5], (content_width - 10) / 2, styles, accent=colors.white)
    story.append(_paired_cards(left_column, right_column, content_width))
    story.append(Spacer(1, 12))

    if follow_up_questions or agent_next_steps:
        left_column = _list_card("Follow-up Questions", follow_up_questions[:6], (content_width - 10) / 2, styles)
        right_column = _list_card("Agent Next Steps", agent_next_steps[:6], (content_width - 10) / 2, styles, accent=colors.white)
        story.append(_paired_cards(left_column, right_column, content_width))
        story.append(Spacer(1, 12))

    system_blocks = []
    for system_name, system_items in feature_outputs.get("system_insights_card", {}).items():
        entries = _safe_list(system_items)[:3]
        if not entries:
            continue
        system_blocks.append(_list_card(system_name.title(), entries, (content_width - 10) / 2, styles, accent=colors.white))

    if system_blocks:
        story.append(_section_header("Systems Analysis", content_width, styles))
        story.append(Spacer(1, 8))
        for index in range(0, len(system_blocks), 2):
            left = system_blocks[index]
            right = system_blocks[index + 1] if index + 1 < len(system_blocks) else _list_card("Notes", [], (content_width - 10) / 2, styles)
            story.append(_paired_cards(left, right, content_width))
            story.append(Spacer(1, 10))

    story.append(_section_header("Detailed Report", content_width, styles))
    story.append(Spacer(1, 8))

    top_abnormal_rows = [
        [
            str(item.get("feature", "")),
            str(item.get("status", "")),
            str(item.get("severity_band", "")),
            str(round(float(item.get("deviation_ratio", 0)) * 100, 1)) + "%",
        ]
        for item in derived.get("top_abnormal_markers", [])[:8]
    ]
    story.extend(
        _detail_table(
            "Top Abnormal Markers",
            ["Marker", "Status", "Severity", "Deviation"],
            top_abnormal_rows,
            content_width,
            styles,
            empty_text="No abnormal markers were captured for this report.",
        )
    )
    story.append(Spacer(1, 12))

    measured_rows = []
    for line in measured_highlights[:8]:
        if ": " in line:
            marker, detail = line.split(": ", 1)
            measured_rows.append([marker, detail])
        else:
            measured_rows.append([line, "Measured highlight"])
    story.extend(
        _detail_table(
            "Measured Data",
            ["Marker", "Detail"],
            measured_rows,
            content_width,
            styles,
            empty_text="Measured data lines were not available.",
        )
    )
    story.append(Spacer(1, 12))

    comparison = enrichment.get("report_comparison") or {}
    comparison_rows = [
        [
            str(item.get("feature", "")),
            str(item.get("previous_value", "")),
            str(item.get("current_value", "")),
            str(item.get("delta", "")),
            str(item.get("current_status", "")),
        ]
        for item in comparison.get("rows", [])[:8]
    ]
    story.extend(
        _detail_table(
            "Last Report Vs This Report",
            ["Marker", "Previous", "Current", "Delta", "Current Status"],
            comparison_rows,
            content_width,
            styles,
            empty_text="No earlier report was available for comparison.",
        )
    )
    if comparison.get("summary"):
        story.append(Spacer(1, 8))
        story.append(_list_card("Comparison Summary", [comparison["summary"], *comparison.get("precautions", [])[:3]], content_width, styles, accent=colors.white))
    story.append(Spacer(1, 12))

    system_rows = []
    for system_name, system_items in feature_outputs.get("system_insights_card", {}).items():
        entries = _safe_list(system_items)[:2]
        if not entries:
            continue
        system_rows.append([system_name.title(), " | ".join(entries)])
    story.extend(
        _detail_table(
            "System Wise Review",
            ["System", "Findings"],
            system_rows,
            content_width,
            styles,
            empty_text="No strong system clusters were recorded.",
        )
    )
    story.append(Spacer(1, 12))

    patient_friendly_summary = document.get("patient_friendly_summary", "")
    if patient_friendly_summary:
        story.append(_section_header("Easy Language Summary", content_width, styles))
        story.append(Spacer(1, 8))
        summary_card = Table([[Paragraph(patient_friendly_summary, styles["body"])]], colWidths=[content_width])
        summary_card.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), CARD),
                    ("BOX", (0, 0), (-1, -1), 1, BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 14),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                    ("TOPPADDING", (0, 0), (-1, -1), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )
        story.append(summary_card)
        story.append(Spacer(1, 12))

    if visual.get("fallback_reason"):
        note_color = ALERT if "external" in visual.get("fallback_reason", "").lower() else TEXT_MUTED
        note_style = ParagraphStyle("VisualNote", parent=styles["muted"], textColor=note_color)
        story.append(Paragraph("Visual note: the downloadable PDF is using the local visual-hook infographic for consistent output.", note_style))

    doc.build(story)
    return output_path

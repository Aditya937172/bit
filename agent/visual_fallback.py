from __future__ import annotations

import os
from typing import Any

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1600
HEIGHT = 1040
BG = "#eef4fb"
CARD = "#ffffff"
NAVY = "#0f2742"
BLUE = "#2b6cb0"
TEAL = "#0f766e"
RED = "#c53030"
AMBER = "#b7791f"
GREEN = "#157f3b"
SLATE = "#cfd9e6"
TEXT = "#1f2937"
MUTED = "#5b6470"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = ["arialbd.ttf", "Arial Bold.ttf"] if bold else ["arial.ttf", "Arial.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_gradient_background(draw: ImageDraw.ImageDraw) -> None:
    top = (235, 244, 252)
    bottom = (247, 250, 253)
    for y in range(HEIGHT):
        ratio = y / max(HEIGHT - 1, 1)
        color = tuple(
            int(top[idx] + (bottom[idx] - top[idx]) * ratio)
            for idx in range(3)
        )
        draw.line((0, y, WIDTH, y), fill=color)


def _draw_card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, lines: list[str], accent: str) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle((x1 + 10, y1 + 12, x2 + 10, y2 + 12), radius=30, fill="#dbe5f0")
    draw.rounded_rectangle(box, radius=30, fill=CARD, outline="#d7e0ea", width=2)
    draw.rounded_rectangle((x1, y1, x1 + 12, y2), radius=28, fill=accent)
    draw.text((x1 + 28, y1 + 24), title, font=_font(28, bold=True), fill=NAVY)
    y = y1 + 72
    for line in lines[:7]:
        draw.text((x1 + 28, y), line, font=_font(22), fill=TEXT)
        y += 36


def _draw_chip(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, fill: str, text_fill: str = "#ffffff") -> int:
    font = _font(20, bold=True)
    bbox = draw.textbbox((0, 0), label, font=font)
    width = bbox[2] - bbox[0] + 34
    height = 38
    draw.rounded_rectangle((x, y, x + width, y + height), radius=18, fill=fill)
    draw.text((x + 17, y + 8), label, font=font, fill=text_fill)
    return width


def _draw_meter(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, score: int) -> None:
    draw.rounded_rectangle((x, y, x + width, y + 22), radius=11, fill=SLATE)
    fill_width = int(width * max(0, min(score, 100)) / 100)
    fill_color = GREEN if score < 35 else AMBER if score < 70 else RED
    draw.rounded_rectangle((x, y, x + fill_width, y + 22), radius=11, fill=fill_color)
    draw.text((x, y - 34), f"Urgency Meter  {score}/100", font=_font(22, bold=True), fill=NAVY)


def _spotlight_title(report: dict[str, Any]) -> tuple[str, str]:
    critical = report.get("critical_markers", [])
    if any("Blood Pressure" in item for item in critical):
        return "Blood Pressure Alert", "Elevated blood-pressure markers are leading this report."
    if any("Glucose" in item or "HbA1c" in item for item in critical):
        return "Metabolic Stress Pattern", "Glucose regulation markers are driving the risk picture."
    if any("Hemoglobin" in item or "Platelets" in item for item in critical):
        return "Hematology Concern", "Blood-count markers show the strongest abnormal signal."
    return "Clinical Priority Snapshot", "This visual summarizes the most relevant abnormal findings."


def generate_local_visual(payload: dict[str, Any], output_path: str) -> dict[str, Any]:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    _draw_gradient_background(draw)

    report = payload.get("report_agent_output", {})
    derived = payload.get("derived_features", {})
    features = payload.get("feature_outputs", {})
    snapshot = report.get("patient_snapshot", {})
    spotlight_title, spotlight_subtitle = _spotlight_title(report)

    draw.rounded_rectangle((48, 34, WIDTH - 48, 156), radius=34, fill="#f9fcff", outline="#d6e2ef", width=2)
    draw.text((74, 54), report.get("headline", "Clinical Visual Report"), font=_font(42, bold=True), fill=NAVY)
    draw.text((74, 104), report.get("summary", ""), font=_font(22), fill=MUTED)

    draw.rounded_rectangle((60, 184, WIDTH - 60, 308), radius=30, fill="#102a43")
    draw.text((88, 212), spotlight_title, font=_font(38, bold=True), fill="#ffffff")
    draw.text((88, 258), spotlight_subtitle, font=_font(24), fill="#d7e8ff")
    _draw_meter(draw, 960, 244, 480, int(derived.get("urgency_score", 0)))

    systems = snapshot.get("systems_affected", [])
    chip_x = 88
    chip_y = 324
    for system in systems[:6]:
        chip_x += _draw_chip(draw, chip_x, chip_y, system.title(), TEAL) + 12

    priority_color = RED if derived.get("care_priority_label") == "High Priority" else AMBER
    _draw_chip(draw, 1180, 324, derived.get("care_priority_label", "Routine"), priority_color)

    _draw_card(
        draw,
        (60, 370, 430, 635),
        "Snapshot",
        [
            f"Abnormal markers: {snapshot.get('abnormal_marker_count', 0)}",
            f"Normal markers: {snapshot.get('normal_marker_count', 0)}",
            f"Urgency score: {derived.get('urgency_score', 0)}",
            f"Care priority: {derived.get('care_priority_label', 'Routine')}",
        ],
        BLUE,
    )

    _draw_card(
        draw,
        (470, 370, 930, 635),
        "Critical Markers",
        report.get("critical_markers", [])[:6] or ["No critical markers flagged"],
        RED,
    )

    _draw_card(
        draw,
        (970, 370, 1540, 635),
        "Monitoring Priorities",
        report.get("monitoring_priorities", [])[:6] or ["No monitoring priorities"],
        BLUE,
    )

    top_abnormal = features.get("critical_markers_card", {}).get("top_abnormal_markers", [])
    top_lines = [
        f"{item['feature']}: {item['status']} | {item['reference_range']}"
        for item in top_abnormal[:6]
    ]
    _draw_card(
        draw,
        (60, 675, 760, 970),
        "Top Abnormal Markers",
        top_lines or ["No abnormal markers"],
        AMBER,
    )

    actions = features.get("action_card", {})
    action_lines = actions.get("recommended_next_steps", [])[:3] + actions.get("follow_up_questions", [])[:3]
    _draw_card(
        draw,
        (800, 675, 1540, 970),
        "Actions and Questions",
        action_lines or ["No follow-up actions"],
        BLUE,
    )

    img.save(output_path)
    return {
        "model": "local-visual-fallback",
        "saved_files": [output_path],
        "text_notes": ["Generated locally from derived features."],
    }

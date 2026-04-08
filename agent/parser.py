from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image
from pypdf import PdfReader
import pytesseract


FEATURE_ALIASES = {
    "Glucose": ["glucose", "blood glucose"],
    "Cholesterol": ["cholesterol", "total cholesterol"],
    "Hemoglobin": ["hemoglobin", "haemoglobin", "hb"],
    "Platelets": ["platelets", "platelet count"],
    "White Blood Cells": ["white blood cells", "wbc", "leukocytes"],
    "Red Blood Cells": ["red blood cells", "rbc", "erythrocytes"],
    "Hematocrit": ["hematocrit", "haematocrit", "hct"],
    "Mean Corpuscular Volume": ["mean corpuscular volume", "mcv"],
    "Mean Corpuscular Hemoglobin": ["mean corpuscular hemoglobin", "mch"],
    "Mean Corpuscular Hemoglobin Concentration": ["mean corpuscular hemoglobin concentration", "mchc"],
    "Insulin": ["insulin"],
    "BMI": ["bmi", "body mass index"],
    "Systolic Blood Pressure": ["systolic blood pressure", "systolic bp"],
    "Diastolic Blood Pressure": ["diastolic blood pressure", "diastolic bp"],
    "Triglycerides": ["triglycerides", "tg"],
    "HbA1c": ["hba1c", "a1c", "glycated hemoglobin"],
    "LDL Cholesterol": ["ldl cholesterol", "ldl"],
    "HDL Cholesterol": ["hdl cholesterol", "hdl"],
    "ALT": ["alt", "alanine aminotransferase"],
    "AST": ["ast", "aspartate aminotransferase"],
    "Heart Rate": ["heart rate", "pulse", "hr"],
    "Creatinine": ["creatinine"],
    "Troponin": ["troponin", "troponin i", "troponin t"],
    "C-reactive Protein": ["c-reactive protein", "crp"],
}


def extract_text(file_path: str) -> tuple[str, str, list[str]]:
    path = Path(file_path)
    suffix = path.suffix.lower()
    notes: list[str] = []

    if suffix == ".pdf":
        with path.open("rb") as stream:
            reader = PdfReader(stream)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text, "pdf_text", notes

    if suffix in {".txt", ".md", ".csv"}:
        return path.read_text(encoding="utf-8", errors="ignore"), "plain_text", notes

    if suffix == ".json":
        raw = path.read_text(encoding="utf-8", errors="ignore")
        try:
            return json.dumps(json.loads(raw), indent=2), "json_text", notes
        except json.JSONDecodeError:
            notes.append("JSON file could not be reformatted, raw content was used.")
            return raw, "json_text", notes

    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        try:
            image = Image.open(path)
            text = pytesseract.image_to_string(image)
            return text, "image_ocr", notes
        except pytesseract.TesseractNotFoundError:
            notes.append("Tesseract OCR is not installed locally, so image parsing is unavailable.")
            return "", "image_ocr_unavailable", notes

    notes.append("Unsupported file type.")
    return "", "unsupported", notes


def _extract_numeric_value(text: str, aliases: list[str]) -> float | None:
    for alias in aliases:
        escaped = re.escape(alias)
        patterns = [
            rf"(?im)\b{escaped}\b\s*[:=\-]?\s*(-?\d+(?:\.\d+)?)",
            rf"(?im)\b{escaped}\b[^\n\r\d-]*(-?\d+(?:\.\d+)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return float(match.group(1))
    return None


def parse_clinical_values(raw_text: str) -> dict[str, float]:
    parsed: dict[str, float] = {}
    clean_text = raw_text.replace(",", " ")

    bp_match = re.search(r"(?im)\b(?:blood pressure|bp)\b[^\d]*(\d{2,3})\s*/\s*(\d{2,3})", clean_text)
    if bp_match:
        parsed["Systolic Blood Pressure"] = float(bp_match.group(1))
        parsed["Diastolic Blood Pressure"] = float(bp_match.group(2))

    for feature, aliases in FEATURE_ALIASES.items():
        if feature in parsed:
            continue
        value = _extract_numeric_value(clean_text, aliases)
        if value is not None:
            parsed[feature] = value

    return parsed

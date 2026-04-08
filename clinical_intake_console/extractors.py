from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

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


SUPPORTED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/bmp",
}


def extract_text_from_upload(uploaded_file: Any) -> tuple[str, str, list[str]]:
    file_type = uploaded_file.type or ""
    file_name = uploaded_file.name
    file_bytes = uploaded_file.getvalue()
    notes: list[str] = []

    if file_type == "application/pdf" or file_name.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(file_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text, "pdf_text", notes

    if file_type in SUPPORTED_IMAGE_TYPES:
        try:
            image = Image.open(io.BytesIO(file_bytes))
            text = pytesseract.image_to_string(image)
            return text, "image_ocr", notes
        except pytesseract.TesseractNotFoundError:
            notes.append("Tesseract OCR is not installed on this machine, so image OCR could not run.")
            return "", "image_ocr_unavailable", notes

    suffix = Path(file_name).suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".json"}:
        decoded = file_bytes.decode("utf-8", errors="ignore")
        if suffix == ".json":
            try:
                parsed_json = json.loads(decoded)
                decoded = json.dumps(parsed_json, indent=2)
            except json.JSONDecodeError:
                notes.append("JSON file could not be reformatted, raw text was used.")
        return decoded, "plain_text", notes

    notes.append("Unsupported file type for automatic extraction.")
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

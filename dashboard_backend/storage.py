from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from typing import Any


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGED_DB_PATH = os.path.join(ROOT_DIR, "Database", "mediBase.db")
IS_VERCEL = os.getenv("VERCEL") == "1"
RUNTIME_BASE_DIR = os.path.join("/tmp", "medicore") if IS_VERCEL else ROOT_DIR
DB_PATH = os.path.join(RUNTIME_BASE_DIR, "Database", "mediBase.db")
CASE_OUTPUT_DIR = os.path.join(RUNTIME_BASE_DIR, "agent", "generated_cases")
UPLOAD_DIR = os.path.join(RUNTIME_BASE_DIR, "agent", "uploads")


LEGACY_COLUMN_TO_FEATURE = {
    "glucose": "Glucose",
    "cholesterol": "Cholesterol",
    "hemoglobin": "Hemoglobin",
    "platelets": "Platelets",
    "white_blood_cells": "White Blood Cells",
    "red_blood_cells": "Red Blood Cells",
    "hematocrit": "Hematocrit",
    "mean_corpuscular_volume": "Mean Corpuscular Volume",
    "mean_corpuscular_hemoglobin": "Mean Corpuscular Hemoglobin",
    "mean_corpuscular_hemoglobin_concentration": "Mean Corpuscular Hemoglobin Concentration",
    "insulin": "Insulin",
    "bmi": "BMI",
    "systolic_blood_pressure": "Systolic Blood Pressure",
    "diastolic_blood_pressure": "Diastolic Blood Pressure",
    "triglycerides": "Triglycerides",
    "hba1c": "HbA1c",
    "ldl_cholesterol": "LDL Cholesterol",
    "hdl_cholesterol": "HDL Cholesterol",
    "alt": "ALT",
    "ast": "AST",
    "heart_rate": "Heart Rate",
    "creatinine": "Creatinine",
    "troponin": "Troponin",
    "c_reactive_protein": "C-reactive Protein",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_storage() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(CASE_OUTPUT_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    if PACKAGED_DB_PATH != DB_PATH and os.path.exists(PACKAGED_DB_PATH) and not os.path.exists(DB_PATH):
        shutil.copyfile(PACKAGED_DB_PATH, DB_PATH)
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS agent_cases (
                case_id TEXT PRIMARY KEY,
                patient_name TEXT NOT NULL,
                source_file_name TEXT,
                source_file_type TEXT,
                source_path TEXT,
                mode TEXT NOT NULL DEFAULT 'Live',
                verification_status TEXT,
                care_priority TEXT,
                urgency_score INTEGER,
                summary TEXT,
                payload_json TEXT NOT NULL,
                pdf_path TEXT,
                image_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_agent_cases_created_at
            ON agent_cases(created_at DESC);

            CREATE TABLE IF NOT EXISTS agent_chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,
                user_message TEXT NOT NULL,
                assistant_message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES agent_cases(case_id)
            );

            CREATE INDEX IF NOT EXISTS idx_agent_chat_messages_case_id
            ON agent_chat_messages(case_id, created_at DESC);
            """
        )
        conn.commit()
    finally:
        conn.close()


def extract_patient_name(payload: dict[str, Any]) -> str:
    case_name = payload.get("case_metadata", {}).get("patient_name")
    if case_name and str(case_name).strip():
        return str(case_name).strip()
    preview = (
        payload.get("raw_intake", {})
        .get("parsed_document", {})
        .get("document_ingestion", {})
        .get("text_preview", "")
    )
    match = re.search(r"Patient Name:\s*(.+)", preview, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    file_name = (
        payload.get("raw_intake", {})
        .get("parsed_document", {})
        .get("document_ingestion", {})
        .get("file_name", "Imported Case")
    )
    return os.path.splitext(os.path.basename(file_name))[0].replace("_", " ").strip() or "Imported Case"


def save_case(
    *,
    case_id: str,
    payload: dict[str, Any],
    source_file_name: str,
    source_file_type: str,
    source_path: str,
    mode: str = "Live",
) -> None:
    patient_name = extract_patient_name(payload)
    verification_status = payload.get("verification_agent_output", {}).get("verification_status", "")
    care_priority = payload.get("derived_features", {}).get("care_priority_label", "")
    urgency_score = int(payload.get("derived_features", {}).get("urgency_score", 0) or 0)
    summary = payload.get("report_agent_output", {}).get("summary", "")
    pdf_path = payload.get("document_export_output", {}).get("pdf_path", "")
    saved_files = payload.get("visual_report_output", {}).get("saved_files", [])
    image_path = saved_files[0] if saved_files else ""
    timestamp = now_iso()

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO agent_cases (
                case_id, patient_name, source_file_name, source_file_type, source_path, mode,
                verification_status, care_priority, urgency_score, summary, payload_json,
                pdf_path, image_path, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(case_id) DO UPDATE SET
                patient_name = excluded.patient_name,
                source_file_name = excluded.source_file_name,
                source_file_type = excluded.source_file_type,
                source_path = excluded.source_path,
                mode = excluded.mode,
                verification_status = excluded.verification_status,
                care_priority = excluded.care_priority,
                urgency_score = excluded.urgency_score,
                summary = excluded.summary,
                payload_json = excluded.payload_json,
                pdf_path = excluded.pdf_path,
                image_path = excluded.image_path,
                updated_at = excluded.updated_at
            """,
            (
                case_id,
                patient_name,
                source_file_name,
                source_file_type,
                source_path,
                mode,
                verification_status,
                care_priority,
                urgency_score,
                summary,
                json.dumps(payload),
                pdf_path,
                image_path,
                timestamp,
                timestamp,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def load_case(case_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM agent_cases WHERE case_id = ?", (case_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    payload = json.loads(row["payload_json"])
    payload.setdefault("case_metadata", {})
    payload["case_metadata"].update(
        {
            "case_id": row["case_id"],
            "patient_name": row["patient_name"],
            "source_file_name": row["source_file_name"],
            "source_file_type": row["source_file_type"],
            "source_path": row["source_path"],
            "mode": row["mode"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
    )
    return payload


def list_case_rows(limit: int = 25) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT case_id, patient_name, source_file_name, source_file_type, mode,
                   verification_status, care_priority, urgency_score, summary,
                   pdf_path, image_path, created_at, updated_at
            FROM agent_cases
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def list_legacy_patient_rows(limit: int = 25) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT rowid AS legacy_id, * FROM patients ORDER BY rowid DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def get_legacy_patient_row(legacy_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT rowid AS legacy_id, * FROM patients WHERE rowid = ?",
            (legacy_id,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def record_chat_message(case_id: str, user_message: str, assistant_message: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO agent_chat_messages (case_id, user_message, assistant_message, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (case_id, user_message, assistant_message, now_iso()),
        )
        conn.commit()
    finally:
        conn.close()


def list_chat_messages(case_id: str, limit: int = 20) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT case_id, user_message, assistant_message, created_at
            FROM agent_chat_messages
            WHERE case_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (case_id, limit),
        ).fetchall()
    finally:
        conn.close()
    messages = [dict(row) for row in rows]
    messages.reverse()
    return messages


def delete_case(case_id: str) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT pdf_path, image_path, source_path FROM agent_cases WHERE case_id = ?",
            (case_id,),
        ).fetchone()
        if not row:
            return False

        conn.execute("DELETE FROM agent_chat_messages WHERE case_id = ?", (case_id,))
        conn.execute("DELETE FROM agent_cases WHERE case_id = ?", (case_id,))
        conn.commit()
    finally:
        conn.close()

    for path in [row["pdf_path"], row["image_path"], row["source_path"]]:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    return True


def persist_case_files(case_id: str, payload: dict[str, Any]) -> dict[str, str]:
    pdf_path = payload.get("document_export_output", {}).get("pdf_path")
    image_files = payload.get("visual_report_output", {}).get("saved_files", [])
    image_path = image_files[0] if image_files else None
    saved: dict[str, str] = {}

    if pdf_path and os.path.exists(pdf_path):
        ext = os.path.splitext(pdf_path)[1] or ".pdf"
        final_pdf_path = os.path.join(CASE_OUTPUT_DIR, f"{case_id}{ext}")
        if os.path.abspath(pdf_path) != os.path.abspath(final_pdf_path):
            shutil.copyfile(pdf_path, final_pdf_path)
        saved["pdf_path"] = final_pdf_path
        payload.setdefault("document_export_output", {})["pdf_path"] = final_pdf_path

    if image_path and os.path.exists(image_path):
        ext = os.path.splitext(image_path)[1] or ".png"
        final_image_path = os.path.join(CASE_OUTPUT_DIR, f"{case_id}{ext}")
        if os.path.abspath(image_path) != os.path.abspath(final_image_path):
            shutil.copyfile(image_path, final_image_path)
        saved["image_path"] = final_image_path
        payload.setdefault("visual_report_output", {})["saved_files"] = [final_image_path]

    return saved


def parse_legacy_confidence(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, bytes):
        try:
            return float(value.decode("utf-8", errors="ignore"))
        except ValueError:
            return None
    text = str(value).strip()
    if text.startswith("b'") and text.endswith("'"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_legacy_values(row: dict[str, Any]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for column, feature in LEGACY_COLUMN_TO_FEATURE.items():
        value = row.get(column)
        if value is None:
            continue
        normalized[feature] = float(value)
    return normalized

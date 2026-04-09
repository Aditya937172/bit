from __future__ import annotations

import json
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.agent_orchestrator import run_three_agent_pipeline
from agent.mcp_manager import build_case_memory_mcp
from agent.report_exporter import export_pdf_report
from agent.visual_fallback import generate_local_visual

from .chat_service import answer_case_question, build_specialist_agents
from .clinical_facts import build_available_details, build_medication_guidance
from .presentation import (
    build_dashboard_profile,
    build_payload_from_legacy_row,
    load_demo_payload,
    load_demo_profiles,
)
from .storage import (
    CASE_OUTPUT_DIR,
    UPLOAD_DIR,
    delete_case,
    ensure_storage,
    extract_patient_name,
    get_legacy_patient_row,
    list_case_rows,
    list_chat_messages,
    list_legacy_patient_rows,
    load_case,
    now_iso,
    persist_case_files,
    record_chat_message,
    save_case,
)


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_DIR = os.path.join(ROOT_DIR, "ui")
EXAMPLE_DOC_PATH = os.path.join(ROOT_DIR, "agent", "example_new_client_report.txt")


class AnalyzePathRequest(BaseModel):
    file_path: str
    fill_missing: bool = True
    prefer_local_agents: bool = True


class ChatRequest(BaseModel):
    case_id: str
    message: str
    agent_key: str | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_storage()
    yield


app = FastAPI(title="BodyWise Local Backend", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _normalized_input_from_payload(payload: dict[str, Any]) -> dict[str, float]:
    return payload.get("raw_intake", {}).get("normalized_patient_input", {}) or {}


def _feature_distance(value_a: float, value_b: float, low: float, high: float) -> float:
    span = max(float(high) - float(low), 1e-6)
    return abs(float(value_a) - float(value_b)) / span


def _similarity_score(base: dict[str, float], other: dict[str, float], ranges: dict[str, list[float]]) -> float:
    shared = [feature for feature in base if feature in other and feature in ranges]
    if not shared:
        return 0.0
    distances = [_feature_distance(base[feature], other[feature], ranges[feature][0], ranges[feature][1]) for feature in shared]
    avg_distance = sum(distances) / len(distances)
    return max(0.0, round(100.0 - min(avg_distance * 35.0, 100.0), 1))


def _overlap_markers(base_payload: dict[str, Any], other_payload: dict[str, Any]) -> list[str]:
    base_markers = {
        item.get("feature")
        for item in base_payload.get("derived_features", {}).get("top_abnormal_markers", [])
    }
    other_markers = {
        item.get("feature")
        for item in other_payload.get("derived_features", {}).get("top_abnormal_markers", [])
    }
    return [marker for marker in base_markers.intersection(other_markers) if marker][:4]


def _safe_patient_name(payload: dict[str, Any]) -> str:
    return (
        payload.get("case_metadata", {}).get("patient_name")
        or extract_patient_name(payload)
        or "Imported Case"
    )


def _find_previous_case_row(case_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    target_name = _safe_patient_name(payload).strip().lower()
    if not target_name:
        return None
    for row in list_case_rows(limit=120):
        if row["case_id"] == case_id:
            continue
        if str(row.get("patient_name", "")).strip().lower() == target_name:
            return row
    return None


def _build_report_comparison(case_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    previous_row = _find_previous_case_row(case_id, payload)
    if not previous_row:
        return None

    previous_payload = load_case(previous_row["case_id"])
    if not previous_payload:
        return None

    current_values = _normalized_input_from_payload(payload)
    previous_values = _normalized_input_from_payload(previous_payload)
    ranges = payload.get("raw_intake", {}).get("reference_ranges", {}) or {}
    current_status = payload.get("derived_features", {}).get("marker_status_map", {}) or {}
    previous_status = previous_payload.get("derived_features", {}).get("marker_status_map", {}) or {}

    comparison_rows: list[dict[str, Any]] = []
    for feature, current_value in current_values.items():
        if feature not in previous_values:
            continue
        previous_value = previous_values[feature]
        low, high = ranges.get(feature, [0, 1])
        span = max(float(high) - float(low), 1e-6)
        delta = round(float(current_value) - float(previous_value), 3)
        delta_ratio = abs(delta) / span
        if abs(delta) < 1e-6 and current_status.get(feature) == previous_status.get(feature):
            continue
        comparison_rows.append(
            {
                "feature": feature,
                "previous_value": previous_value,
                "current_value": current_value,
                "delta": delta,
                "direction": "up" if delta > 0 else "down" if delta < 0 else "same",
                "previous_status": previous_status.get(feature, "unknown"),
                "current_status": current_status.get(feature, "unknown"),
                "importance": round(delta_ratio, 4),
            }
        )

    comparison_rows.sort(key=lambda item: item["importance"], reverse=True)
    top_rows = comparison_rows[:8]
    if not top_rows:
        return None

    summary_bits = [
        f"{row['feature']} moved {row['direction']} by {row['delta']}"
        for row in top_rows[:3]
    ]
    return {
        "previous_case_id": previous_row["case_id"],
        "previous_created_at": previous_row.get("created_at"),
        "previous_summary": previous_row.get("summary", ""),
        "previous_patient_name": previous_row.get("patient_name"),
        "summary": "Compared with the last stored report, " + "; ".join(summary_bits) + ".",
        "rows": top_rows,
        "precautions": payload.get("report_agent_output", {}).get("recommended_next_steps", [])[:3],
    }


def _build_similar_cases(case_id: str, payload: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    base_values = _normalized_input_from_payload(payload)
    ranges = payload.get("raw_intake", {}).get("reference_ranges", {}) or {}
    if not base_values:
        return []

    candidates: list[dict[str, Any]] = []

    for row in list_case_rows(limit=40):
        other_case_id = row["case_id"]
        if other_case_id == case_id:
            continue
        other_payload = load_case(other_case_id)
        if not other_payload:
            continue
        other_values = _normalized_input_from_payload(other_payload)
        score = _similarity_score(base_values, other_values, ranges)
        if score <= 0:
            continue
        candidates.append(
            {
                "case_id": other_case_id,
                "patient_name": row.get("patient_name"),
                "mode": row.get("mode", "Live"),
                "similarity_score": score,
                "summary": row.get("summary", ""),
                "care_priority": row.get("care_priority", ""),
                "overlap_markers": _overlap_markers(payload, other_payload),
            }
        )

    for row in list_legacy_patient_rows(limit=40):
        legacy_case_id = f"legacy-{row['legacy_id']}"
        if legacy_case_id == case_id:
            continue
        other_payload = build_payload_from_legacy_row(row)
        other_values = _normalized_input_from_payload(other_payload)
        score = _similarity_score(base_values, other_values, ranges)
        if score <= 0:
            continue
        candidates.append(
            {
                "case_id": legacy_case_id,
                "patient_name": other_payload.get("case_metadata", {}).get("patient_name"),
                "mode": "History",
                "similarity_score": score,
                "summary": row.get("diagnosis") or other_payload.get("report_agent_output", {}).get("summary", ""),
                "care_priority": other_payload.get("derived_features", {}).get("care_priority_label", ""),
                "overlap_markers": _overlap_markers(payload, other_payload),
            }
        )

    candidates.sort(key=lambda item: item["similarity_score"], reverse=True)
    return candidates[:limit]


def _enrich_payload(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    medication_guidance = build_medication_guidance(payload)
    comparison = _build_report_comparison(case_id, payload) if not case_id.startswith("legacy-") and not case_id.startswith("demo-") else None
    payload.setdefault("dashboard_enrichment", {})
    payload["dashboard_enrichment"].update(
        {
            "similar_cases": _build_similar_cases(case_id, payload),
            "source_overview": {
                "file_name": payload.get("raw_intake", {}).get("parsed_document", {}).get("document_ingestion", {}).get("file_name"),
                "file_type": payload.get("raw_intake", {}).get("parsed_document", {}).get("document_ingestion", {}).get("file_type"),
                "extraction_mode": payload.get("raw_intake", {}).get("parsed_document", {}).get("document_ingestion", {}).get("extraction_mode"),
                "parsed_feature_count": payload.get("raw_intake", {}).get("parsed_document", {}).get("parsed_payload", {}).get("parsed_feature_count"),
                "missing_feature_count": payload.get("raw_intake", {}).get("parsed_document", {}).get("parsed_payload", {}).get("missing_feature_count"),
            },
            "medication_guidance": medication_guidance,
            "available_details": build_available_details(payload),
            "mcp_context": payload.get("mcp_context", []),
            "report_comparison": comparison,
            "specialist_agents": build_specialist_agents(payload),
        }
    )
    return payload


def _case_artifact_paths(case_id: str) -> tuple[str, str]:
    return (
        os.path.join(CASE_OUTPUT_DIR, f"{case_id}.pdf"),
        os.path.join(CASE_OUTPUT_DIR, f"{case_id}.png"),
    )


def _load_payload_from_json_file(path: str) -> dict[str, Any] | None:
    if not path.lower().endswith(".json"):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return None
    if isinstance(payload, dict) and "report_agent_output" in payload and "derived_features" in payload:
        return payload
    return None


def _ensure_payload_artifacts(case_id: str, payload: dict[str, Any]) -> dict[str, str]:
    pdf_target, image_target = _case_artifact_paths(case_id)

    saved_files = payload.get("visual_report_output", {}).get("saved_files", [])
    if not saved_files:
        fallback_payload = {
            "report_agent_output": payload.get("report_agent_output", {}),
            "derived_features": payload.get("derived_features", {}),
            "feature_outputs": payload.get("feature_outputs", {}),
        }
        visual_output = generate_local_visual(fallback_payload, image_target)
        payload["visual_report_output"] = visual_output

    export_pdf_report(payload, pdf_target)
    payload.setdefault("document_export_output", {})["pdf_path"] = pdf_target

    saved_files = payload.get("visual_report_output", {}).get("saved_files", [])
    if saved_files:
        image_source = saved_files[0]
        if os.path.exists(image_source) and os.path.abspath(image_source) != os.path.abspath(image_target):
            shutil.copyfile(image_source, image_target)
        elif os.path.exists(image_source) and not os.path.exists(image_target):
            shutil.copyfile(image_source, image_target)
        if os.path.exists(image_target):
            payload.setdefault("visual_report_output", {})["saved_files"] = [image_target]

    persisted = persist_case_files(case_id, payload)
    if os.path.exists(pdf_target):
        persisted["pdf_path"] = pdf_target
    if os.path.exists(image_target):
        persisted["image_path"] = image_target
    return persisted


def _load_case_payload(case_id: str) -> dict[str, Any]:
    if case_id.startswith("legacy-"):
        legacy_id = int(case_id.split("-", 1)[1])
        row = get_legacy_patient_row(legacy_id)
        if not row:
            raise HTTPException(status_code=404, detail="Legacy patient not found")
        payload = build_payload_from_legacy_row(row)
        payload.setdefault("case_metadata", {})
        payload["case_metadata"]["case_id"] = case_id
        return payload

    if case_id.startswith("demo-"):
        return load_demo_payload(case_id)

    payload = load_case(case_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Case not found")
    return payload


def _build_bootstrap_profiles() -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for row in list_case_rows(limit=24):
        payload = load_case(row["case_id"])
        if not payload:
            continue
        payload = _enrich_payload(row["case_id"], payload)
        profiles.append(build_dashboard_profile(payload, case_id=row["case_id"], mode="Live"))

    profiles.extend(load_demo_profiles())

    return profiles


def _store_payload(case_id: str, payload: dict[str, Any], *, source_file_name: str, source_file_type: str, source_path: str) -> dict[str, Any]:
    payload.setdefault("case_metadata", {})
    payload["case_metadata"].update(
        {
            "case_id": case_id,
            "patient_name": extract_patient_name(payload),
            "mode": "Live",
            "created_at": now_iso(),
        }
    )
    payload = _enrich_payload(case_id, payload)
    _ensure_payload_artifacts(case_id, payload)
    save_case(
        case_id=case_id,
        payload=payload,
        source_file_name=source_file_name,
        source_file_type=source_file_type,
        source_path=source_path,
        mode="Live",
    )
    return payload


@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/ui/index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"status": "ok"}


@app.get("/api/dashboard/bootstrap")
async def dashboard_bootstrap() -> dict[str, Any]:
    profiles = _build_bootstrap_profiles()
    return {
        "profiles": profiles,
        "default_case_id": profiles[0]["caseId"] if profiles else None,
    }


@app.get("/api/cases")
async def list_cases() -> dict[str, Any]:
    return {"cases": list_case_rows(limit=50)}


@app.get("/api/cases/{case_id}")
async def get_case(case_id: str) -> dict[str, Any]:
    payload = _load_case_payload(case_id)
    if case_id.startswith("legacy-"):
        _ensure_payload_artifacts(case_id, payload)
    return _enrich_payload(case_id, payload)


@app.delete("/api/cases/{case_id}")
async def remove_case(case_id: str) -> dict[str, Any]:
    if case_id.startswith("legacy-") or case_id.startswith("demo-"):
        raise HTTPException(status_code=400, detail="Only uploaded live cases can be deleted")
    deleted = delete_case(case_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"case_id": case_id, "deleted": True}


@app.get("/api/cases/{case_id}/pdf")
async def get_case_pdf(case_id: str) -> FileResponse:
    payload = _load_case_payload(case_id)
    payload = _enrich_payload(case_id, payload)
    artifact_paths = _ensure_payload_artifacts(case_id, payload)
    pdf_path = artifact_paths.get("pdf_path") or payload.get("document_export_output", {}).get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF not available")
    patient_name = _safe_patient_name(payload).replace(" ", "_")
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"{patient_name}.pdf")


@app.get("/api/cases/{case_id}/image")
async def get_case_image(case_id: str) -> FileResponse:
    payload = _load_case_payload(case_id)
    payload = _enrich_payload(case_id, payload)
    artifact_paths = _ensure_payload_artifacts(case_id, payload)
    image_path = artifact_paths.get("image_path")
    if not image_path or not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not available")
    return FileResponse(image_path, media_type="image/png", filename=os.path.basename(image_path))


@app.get("/api/example-document")
async def get_example_document() -> FileResponse:
    if not os.path.exists(EXAMPLE_DOC_PATH):
        raise HTTPException(status_code=404, detail="Example document not available")
    return FileResponse(
        EXAMPLE_DOC_PATH,
        media_type="text/plain",
        filename=os.path.basename(EXAMPLE_DOC_PATH),
    )


@app.post("/api/analyze-path")
async def analyze_local_path(request: AnalyzePathRequest) -> dict[str, Any]:
    try:
        if not os.path.exists(request.file_path):
            raise HTTPException(status_code=404, detail="Input file not found")

        imported_payload = _load_payload_from_json_file(request.file_path)
        if imported_payload is not None:
            payload = imported_payload
        else:
            payload = run_three_agent_pipeline(
                request.file_path,
                fill_missing=request.fill_missing,
                prefer_local_agents=request.prefer_local_agents,
            )

        case_id = f"case-{uuid.uuid4().hex[:12]}"
        payload = _store_payload(
            case_id,
            payload,
            source_file_name=os.path.basename(request.file_path),
            source_file_type=os.path.splitext(request.file_path)[1].lower(),
            source_path=request.file_path,
        )
        return {
            "case_id": case_id,
            "profile": build_dashboard_profile(payload, case_id=case_id, mode="Live"),
            "payload": payload,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"analyze-path failed: {exc}") from exc


@app.post("/api/analyze-upload")
async def analyze_upload(
    file: UploadFile = File(...),
    fill_missing: bool = Form(True),
    prefer_local_agents: bool = Form(True),
    patient_name: str | None = Form(None),
) -> dict[str, Any]:
    try:
        case_id = f"case-{uuid.uuid4().hex[:12]}"
        suffix = os.path.splitext(file.filename or "")[1].lower()
        local_path = os.path.join(UPLOAD_DIR, f"{case_id}{suffix or '.bin'}")

        with open(local_path, "wb") as handle:
            shutil.copyfileobj(file.file, handle)

        imported_payload = _load_payload_from_json_file(local_path)
        if imported_payload is not None:
            payload = imported_payload
        else:
            payload = run_three_agent_pipeline(
                local_path,
                fill_missing=fill_missing,
                prefer_local_agents=prefer_local_agents,
            )

        if patient_name and patient_name.strip():
            payload.setdefault("case_metadata", {})
            payload["case_metadata"]["patient_name"] = patient_name.strip()

        payload = _store_payload(
            case_id,
            payload,
            source_file_name=file.filename or os.path.basename(local_path),
            source_file_type=suffix,
            source_path=local_path,
        )
        return {
            "case_id": case_id,
            "profile": build_dashboard_profile(payload, case_id=case_id, mode="Live"),
            "payload": payload,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"analyze-upload failed: {exc}") from exc


@app.post("/api/chat")
async def chat(request: ChatRequest) -> dict[str, Any]:
    payload = _load_case_payload(request.case_id)
    payload = _enrich_payload(request.case_id, payload)
    persisted_history = [] if request.case_id.startswith("legacy-") or request.case_id.startswith("demo-") else list_chat_messages(request.case_id)
    case_memory_mcp = build_case_memory_mcp(
        case_id=request.case_id,
        payload=payload,
        history=persisted_history,
        current_question=request.message,
    )
    payload.setdefault("dashboard_enrichment", {})
    payload["dashboard_enrichment"]["case_memory"] = case_memory_mcp
    payload["dashboard_enrichment"]["mcp_context"] = [
        *payload["dashboard_enrichment"].get("mcp_context", []),
        case_memory_mcp,
    ]
    reply = answer_case_question(payload, request.message, history=persisted_history, agent_key=request.agent_key)
    if not request.case_id.startswith("legacy-") and not request.case_id.startswith("demo-"):
        record_chat_message(request.case_id, request.message, reply["answer"])
        persisted_history = list_chat_messages(request.case_id)
    return {
        "case_id": request.case_id,
        "message": request.message,
        "answer": reply["answer"],
        "agent": reply.get("agent"),
        "supporting_facts": reply.get("supporting_facts", []),
        "measure_lines": reply.get("measure_lines", []),
        "next_steps": reply.get("next_steps", []),
        "citations": reply.get("citations", []),
        "history": persisted_history,
    }


@app.get("/api/chat/{case_id}")
async def chat_history(case_id: str) -> dict[str, Any]:
    if case_id.startswith("legacy-") or case_id.startswith("demo-"):
        return {"case_id": case_id, "history": []}
    return {"case_id": case_id, "history": list_chat_messages(case_id)}


app.mount("/ui", StaticFiles(directory=UI_DIR, html=True), name="ui")

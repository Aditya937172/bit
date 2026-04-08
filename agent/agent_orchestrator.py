from __future__ import annotations

import os
import sys
import time
from typing import Any


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from agent import build_pipeline_output  # noqa: E402
from chat_context import build_chat_agent_context  # noqa: E402
from derived_features import build_derived_features  # noqa: E402
from document_agent import build_document_fallback  # noqa: E402
from fallback_agents import build_report_fallback, build_research_fallback, build_verification_fallback  # noqa: E402
from gemini_image_client import GeminiImageClient  # noqa: E402
from llm_client import LLMClient  # noqa: E402
from mcp_manager import get_active_mcp_summary  # noqa: E402
from prompts import DOCUMENT_AGENT_PROMPT, REPORT_AGENT_PROMPT, RESEARCH_AGENT_PROMPT, VERIFICATION_AGENT_PROMPT  # noqa: E402
from retrieval import build_retrieval_context  # noqa: E402
from skills_manager import build_skill_block  # noqa: E402
from visual_fallback import generate_local_visual  # noqa: E402


def _feature_cards(source_data: dict[str, Any], research_output: dict[str, Any], verification_output: dict[str, Any], report_output: dict[str, Any]) -> dict[str, Any]:
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


def _derive_data_view(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = payload["normalized_patient_input"]
    ranges = payload["reference_ranges"]
    findings = []
    abnormal = []

    for feature, value in normalized.items():
        low, high = ranges[feature]
        if value < low:
            status = "low"
        elif value > high:
            status = "high"
        else:
            status = "normal"
        findings.append(
            {
                "feature": feature,
                "value": value,
                "reference_low": low,
                "reference_high": high,
                "status": status,
            }
        )
        if status != "normal":
            abnormal.append(findings[-1])

    return {
        "document_summary": {
            "file_name": payload["parsed_document"]["document_ingestion"]["file_name"],
            "file_type": payload["parsed_document"]["document_ingestion"]["file_type"],
            "extraction_mode": payload["parsed_document"]["document_ingestion"]["extraction_mode"],
            "parsed_feature_count": payload["parsed_document"]["parsed_payload"]["parsed_feature_count"],
            "missing_feature_count": payload["parsed_document"]["parsed_payload"]["missing_feature_count"],
        },
        "abnormal_feature_status": abnormal,
        "normal_feature_count": len(findings) - len(abnormal),
        "all_feature_status": findings,
    }


def _build_fallback_pipeline_output(
    *,
    raw_payload: dict[str, Any],
    agent_input: dict[str, Any],
    retrieval_context: dict[str, Any],
    mcp_context: dict[str, Any],
    runtime_reason: str,
    llm_model: str,
) -> dict[str, Any]:
    research_output = build_research_fallback(agent_input)
    verification_output = build_verification_fallback(agent_input, research_output)
    report_output = build_report_fallback(agent_input, research_output, verification_output)
    derived_features = build_derived_features(
        source_data=agent_input,
        research_output=research_output,
        verification_output=verification_output,
        report_output=report_output,
    )
    document_payload = {
        "source_data": agent_input,
        "derived_features": derived_features,
        "report_output": report_output,
        "verification_output": verification_output,
    }
    document_output = build_document_fallback(
        source_data=agent_input,
        derived_features=derived_features,
        report_output=report_output,
        verification_output=verification_output,
    )
    try:
        image_client = GeminiImageClient()
        visual_output = image_client.generate_report_visual(
            document_output["image_prompt_for_visual_report"],
            os.path.join(CURRENT_DIR, "generated_report_visual.png"),
        )
    except Exception as image_exc:
        fallback_payload = {
            "report_agent_output": report_output,
            "derived_features": derived_features,
            "feature_outputs": _feature_cards(agent_input, research_output, verification_output, report_output),
        }
        visual_output = generate_local_visual(
            fallback_payload,
            os.path.join(CURRENT_DIR, "generated_report_visual.png"),
        )
        visual_output["fallback_reason"] = str(image_exc)
    chat_agent_context = build_chat_agent_context(
        source_data=agent_input,
        derived_features=derived_features,
        report_output=report_output,
        verification_output=verification_output,
    )
    return {
        "raw_intake": raw_payload,
        "retrieval_context": retrieval_context,
        "mcp_context": mcp_context,
        "agent_runtime_error": runtime_reason,
        "llm_trace": {
            "model": llm_model,
            "research_agent_input": {
                "source_data": agent_input,
                "retrieval_context": retrieval_context,
                "mcp_context": mcp_context,
            },
            "verification_agent_input": {
                "source_data": agent_input,
                "retrieval_context": retrieval_context,
                "mcp_context": mcp_context,
                "research_output": research_output,
            },
            "report_agent_input": {
                "source_data": agent_input,
                "retrieval_context": retrieval_context,
                "mcp_context": mcp_context,
                "research_output": research_output,
                "verification_output": verification_output,
            },
            "document_agent_input": document_payload,
        },
        "research_agent_output": research_output,
        "verification_agent_output": verification_output,
        "report_agent_output": report_output,
        "derived_features": derived_features,
        "document_agent_output": document_output,
        "chat_agent_context": chat_agent_context,
        "visual_report_output": visual_output,
        "feature_outputs": _feature_cards(agent_input, research_output, verification_output, report_output),
    }


def run_three_agent_pipeline(
    file_path: str,
    fill_missing: bool = True,
    prefer_local_agents: bool = False,
) -> dict[str, Any]:
    raw_payload = build_pipeline_output(file_path, fill_missing=fill_missing)
    raw_payload.pop("ml_output", None)

    agent_input = _derive_data_view(raw_payload)
    retrieval_context = build_retrieval_context()
    mcp_context = get_active_mcp_summary()
    llm_model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

    if prefer_local_agents:
        return _build_fallback_pipeline_output(
            raw_payload=raw_payload,
            agent_input=agent_input,
            retrieval_context=retrieval_context,
            mcp_context=mcp_context,
            runtime_reason="Hosted LLM skipped by configuration; local fallback agents were used.",
            llm_model="local-fallback",
        )

    client = LLMClient()
    research_prompt = RESEARCH_AGENT_PROMPT + "\n\n" + build_skill_block(["research_agent_skill.md"])
    verification_prompt = VERIFICATION_AGENT_PROMPT + "\n\n" + build_skill_block(["verification_agent_skill.md"])
    report_prompt = REPORT_AGENT_PROMPT + "\n\n" + build_skill_block(["report_agent_skill.md"])
    document_prompt = DOCUMENT_AGENT_PROMPT
    research_payload = {
        "source_data": agent_input,
        "retrieval_context": retrieval_context,
        "mcp_context": mcp_context,
    }
    verification_payload = {
        "source_data": agent_input,
        "retrieval_context": retrieval_context,
        "mcp_context": mcp_context,
    }
    report_payload = {
        "source_data": agent_input,
        "retrieval_context": retrieval_context,
        "mcp_context": mcp_context,
    }

    try:
        research_output = client.chat_json(
            system_prompt=research_prompt,
            user_payload=research_payload,
        )
        time.sleep(18)

        verification_payload["research_output"] = research_output
        verification_output = client.chat_json(
            system_prompt=verification_prompt,
            user_payload=verification_payload,
        )
        time.sleep(18)

        report_payload["research_output"] = research_output
        report_payload["verification_output"] = verification_output
        report_output = client.chat_json(
            system_prompt=report_prompt,
            user_payload=report_payload,
        )
        derived_features = build_derived_features(
            source_data=agent_input,
            research_output=research_output,
            verification_output=verification_output,
            report_output=report_output,
        )
        document_payload = {
            "source_data": agent_input,
            "derived_features": derived_features,
            "report_output": report_output,
            "verification_output": verification_output,
        }
        time.sleep(18)
        document_output = client.chat_json(
            system_prompt=document_prompt,
            user_payload=document_payload,
        )
    except Exception as exc:
        return _build_fallback_pipeline_output(
            raw_payload=raw_payload,
            agent_input=agent_input,
            retrieval_context=retrieval_context,
            mcp_context=mcp_context,
            runtime_reason=str(exc),
            llm_model=client.model,
        )

    try:
        image_client = GeminiImageClient()
        visual_output = image_client.generate_report_visual(
            document_output["image_prompt_for_visual_report"],
            os.path.join(CURRENT_DIR, "generated_report_visual.png"),
        )
    except Exception as exc:
        fallback_payload = {
            "report_agent_output": report_output,
            "derived_features": derived_features,
            "feature_outputs": _feature_cards(agent_input, research_output, verification_output, report_output),
        }
        visual_output = generate_local_visual(
            fallback_payload,
            os.path.join(CURRENT_DIR, "generated_report_visual.png"),
        )
        visual_output["fallback_reason"] = str(exc)

    chat_agent_context = build_chat_agent_context(
        source_data=agent_input,
        derived_features=derived_features,
        report_output=report_output,
        verification_output=verification_output,
    )

    return {
        "raw_intake": raw_payload,
        "retrieval_context": retrieval_context,
        "mcp_context": mcp_context,
        "llm_trace": {
            "model": client.model,
            "research_agent_input": research_payload,
            "verification_agent_input": verification_payload,
            "report_agent_input": report_payload,
            "document_agent_input": document_payload,
        },
        "research_agent_output": research_output,
        "verification_agent_output": verification_output,
        "report_agent_output": report_output,
        "derived_features": derived_features,
        "document_agent_output": document_output,
        "chat_agent_context": chat_agent_context,
        "visual_report_output": visual_output,
        "feature_outputs": _feature_cards(agent_input, research_output, verification_output, report_output),
    }

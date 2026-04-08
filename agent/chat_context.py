from __future__ import annotations

from typing import Any


def build_chat_agent_context(
    *,
    source_data: dict[str, Any],
    derived_features: dict[str, Any],
    report_output: dict[str, Any],
    verification_output: dict[str, Any],
) -> dict[str, Any]:
    return {
        "system_instruction": (
            "Answer only from parsed values, derived features, verified findings, final report output, "
            "and approved educational facts. Keep the answer conversational but data-backed. "
            "When useful, include exact measured values, reference ranges, and short next steps. "
            "Do not diagnose disease unless explicitly present."
        ),
        "response_contract": {
            "preferred_sections": ["main_answer", "measured_data", "next_steps"],
            "keep_language": "slightly easier than a specialist note",
        },
        "source_data": source_data,
        "derived_features": derived_features,
        "verified_findings": verification_output.get("verified_claims", []),
        "report_output": report_output,
        "starter_questions": [
            "What are the highest priority abnormalities?",
            "Summarize this report in simple language.",
            "What should a clinician review first?",
            "What key diet changes fit these markers?",
            "What are the exact measured highlights and next steps?",
        ],
    }

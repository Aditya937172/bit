from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient

from dashboard_backend.app import app


SAMPLE_REPORT = ROOT_DIR / "agent" / "sample_report.txt"


def assert_ok(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    client = TestClient(app)

    health = client.get("/api/health")
    assert_ok(health.status_code == 200, f"Health check failed: {health.status_code}")

    example_doc = client.get("/api/example-document")
    assert_ok(example_doc.status_code == 200, f"Example document failed: {example_doc.status_code}")

    bootstrap = client.get("/api/dashboard/bootstrap")
    assert_ok(bootstrap.status_code == 200, f"Bootstrap failed: {bootstrap.status_code}")
    bootstrap_json = bootstrap.json()
    assert_ok("profiles" in bootstrap_json, "Bootstrap payload missing profiles")

    assert_ok(SAMPLE_REPORT.exists(), f"Missing sample report: {SAMPLE_REPORT}")
    with SAMPLE_REPORT.open("rb") as handle:
        analyze = client.post(
            "/api/analyze-upload",
            files={"file": ("sample_report.txt", handle, "text/plain")},
            data={"fill_missing": "true", "prefer_local_agents": "true"},
        )
    assert_ok(analyze.status_code == 200, f"Analyze upload failed: {analyze.status_code}")
    analyze_json = analyze.json()
    case_id = analyze_json["case_id"]

    case_response = client.get(f"/api/cases/{case_id}")
    assert_ok(case_response.status_code == 200, f"Case retrieval failed: {case_response.status_code}")
    case_payload = case_response.json()
    assert_ok("report_agent_output" in case_payload, "Case payload missing report_agent_output")
    assert_ok("derived_features" in case_payload, "Case payload missing derived_features")

    pdf = client.get(f"/api/cases/{case_id}/pdf")
    assert_ok(pdf.status_code == 200, f"PDF retrieval failed: {pdf.status_code}")
    image = client.get(f"/api/cases/{case_id}/image")
    assert_ok(image.status_code == 200, f"Image retrieval failed: {image.status_code}")

    questions = {
        "Summarize this report in simple language.": ["Measured data:", "Next steps:"],
        "What should a clinician review first?": ["Measured data:", "Next steps:"],
        "What data do you have for this patient?": ["parsed", "Next steps:"],
        "Explain the blood pressure findings.": ["systolic", "Next steps:"],
        "What does the report suggest about kidneys or liver?": ["Next steps:", "Hepatic"],
        "What medication classes are commonly discussed for this pattern?": ["educational", "Next steps:"],
    }

    for question, expected_markers in questions.items():
        chat = client.post("/api/chat", json={"case_id": case_id, "message": question})
        assert_ok(chat.status_code == 200, f"Chat failed for {question!r}: {chat.status_code}")
        answer = chat.json()["answer"]
        assert_ok(len(answer) < 1400, f"Chat answer too long for {question!r}")
        for expected in expected_markers:
            assert_ok(expected.lower() in answer.lower(), f"Unexpected chat answer for {question!r}: {answer}")

    history = client.get(f"/api/chat/{case_id}")
    assert_ok(history.status_code == 200, f"Chat history failed: {history.status_code}")
    assert_ok(len(history.json().get("history", [])) >= 1, "Chat history did not store messages")

    print("Smoke test passed.")
    print(f"Case: {case_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

from __future__ import annotations

import os
import sys


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from agent import build_pipeline_output  # noqa: E402


def main() -> None:
    sample_path = os.path.join(CURRENT_DIR, "sample_report.txt")
    payload = build_pipeline_output(sample_path)

    assert "normalized_patient_input" in payload
    assert len(payload["normalized_patient_input"]) == 24
    assert "ml_output" in payload
    assert payload["ml_output"]["inference"]["predicted_condition"]
    assert payload["ml_output"]["inference"]["class_probabilities"]

    print("Local agent smoke test passed.")
    print(payload["ml_output"]["inference"]["predicted_condition"])
    print(round(payload["ml_output"]["inference"]["confidence"], 2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import os
import sys


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from agent_orchestrator import run_three_agent_pipeline  # noqa: E402
from report_exporter import export_pdf_report  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local multi-agent clinical report workflow")
    parser.add_argument("--file", required=True, help="Path to local report file")
    parser.add_argument("--output", default="agent/agent_report_output.json", help="Path to save output JSON")
    parser.add_argument("--pdf-output", help="Optional path to save output PDF")
    parser.add_argument("--no-fill-missing", action="store_true")
    args = parser.parse_args()

    payload = run_three_agent_pipeline(args.file, fill_missing=not args.no_fill_missing)
    pdf_output_path = args.pdf_output
    if not pdf_output_path:
        base_name, _ = os.path.splitext(args.output)
        pdf_output_path = f"{base_name}.pdf"
    try:
        export_pdf_report(payload, pdf_output_path)
        payload["document_export_output"] = {"pdf_path": pdf_output_path}
    except Exception as exc:
        payload["document_export_output"] = {"error": str(exc)}

    output_path = args.output
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print(f"Saved agent report output to {output_path}")
    if "pdf_path" in payload.get("document_export_output", {}):
        print(f"Saved PDF report to {payload['document_export_output']['pdf_path']}")


if __name__ == "__main__":
    main()

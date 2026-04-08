from __future__ import annotations

import argparse
import os
import sys


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from model_adapter import dumps_pretty, fill_missing_with_midpoints, get_reference_ranges, run_existing_model  # noqa: E402
from parser import extract_text, parse_clinical_values  # noqa: E402
from schema import build_ingestion_schema, build_output_schema  # noqa: E402


def build_pipeline_output(file_path: str, fill_missing: bool = True) -> dict:
    extracted_text, extraction_mode, notes = extract_text(file_path)
    parsed_values = parse_clinical_values(extracted_text)
    reference_ranges = get_reference_ranges()
    missing_features = [feature for feature in reference_ranges if feature not in parsed_values]

    parsed_document = build_ingestion_schema(
        file_name=os.path.basename(file_path),
        file_type=os.path.splitext(file_path)[1].lower(),
        extraction_mode=extraction_mode,
        extracted_text=extracted_text,
        parsed_values=parsed_values,
        missing_features=missing_features,
        notes=notes,
    )

    normalized_patient_input = fill_missing_with_midpoints(parsed_values) if fill_missing else parsed_values
    if len(normalized_patient_input) != len(reference_ranges):
        raise ValueError(
            "Clinical payload is incomplete. Provide a richer report or enable midpoint filling."
        )

    ml_output = run_existing_model(normalized_patient_input)
    return build_output_schema(
        parsed_document=parsed_document,
        normalized_patient_input=normalized_patient_input,
        reference_ranges=reference_ranges,
        ml_output=ml_output,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Local report parser + existing ML model runner")
    parser.add_argument("--file", required=True, help="Path to local PDF, image, or text report")
    parser.add_argument("--output", help="Optional path to save the final JSON")
    parser.add_argument(
        "--no-fill-missing",
        action="store_true",
        help="Do not auto-fill missing clinical fields from reference range midpoints",
    )
    args = parser.parse_args()

    payload = build_pipeline_output(args.file, fill_missing=not args.no_fill_missing)
    pretty = dumps_pretty(payload)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(pretty)
        print(f"Saved output to {args.output}")
    else:
        print(pretty)


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
import sys

import pandas as pd
import streamlit as st


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from extractors import parse_clinical_values, extract_text_from_upload  # noqa: E402
from model_bridge import build_model_output, dumps_pretty, get_reference_ranges, midpoint_fill  # noqa: E402
from schema import build_analysis_schema, build_parsed_document_schema  # noqa: E402


st.set_page_config(page_title="Clinical Intake Console", page_icon="C", layout="wide")

st.title("Clinical Intake Console")
st.caption("Upload a report or image, parse structured clinical data, and run the existing ML model without changing the original app.")

uploaded_file = st.file_uploader(
    "Upload report",
    type=["pdf", "png", "jpg", "jpeg", "webp", "bmp", "txt", "md", "csv", "json"],
)

use_midpoint_fill = st.checkbox("Auto-fill missing clinical fields from reference-range midpoints", value=True)

if uploaded_file is None:
    st.info("Upload a PDF, text file, or image report to begin.")
    st.stop()

text, extraction_mode, notes = extract_text_from_upload(uploaded_file)
parsed_values = parse_clinical_values(text)
ranges = get_reference_ranges()
missing_features = [feature for feature in ranges.keys() if feature not in parsed_values]
parsed_document = build_parsed_document_schema(
    file_name=uploaded_file.name,
    file_type=uploaded_file.type or "unknown",
    extraction_mode=extraction_mode,
    extracted_text=text,
    parsed_values=parsed_values,
    missing_features=missing_features,
    notes=notes,
)

left_col, right_col = st.columns([1.1, 1])

with left_col:
    st.subheader("Extracted Text")
    st.text_area("Text preview", value=text, height=320)

    st.subheader("Parsed Clinical Values")
    if parsed_values:
        parsed_df = pd.DataFrame(
            [{"Feature": key, "Value": value} for key, value in parsed_values.items()]
        ).sort_values("Feature")
        st.dataframe(parsed_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No clinical values were parsed from the uploaded file.")

with right_col:
    st.subheader("Parsing Status")
    st.metric("Fields Parsed", len(parsed_values))
    st.metric("Fields Missing", len(missing_features))
    st.write("Extraction mode:", extraction_mode)
    if notes:
        for note in notes:
            st.warning(note)

    if missing_features:
        st.write("Missing features:")
        st.code("\n".join(missing_features))

normalized_values = midpoint_fill(parsed_values) if use_midpoint_fill else parsed_values

if len(normalized_values) != len(ranges):
    st.error("The payload is still incomplete. Enable midpoint fill or provide a richer report.")
    st.json(parsed_document)
    st.stop()

st.subheader("Normalized Schema")
st.json(
    {
        "normalized_patient_input": normalized_values,
        "reference_ranges": ranges,
    }
)

if st.button("Run Existing ML Model", type="primary", use_container_width=True):
    inference = build_model_output(normalized_values)
    analysis_payload = build_analysis_schema(
        parsed_document=parsed_document,
        patient_values=normalized_values,
        ranges=ranges,
        inference=inference,
    )

    summary_col, detail_col = st.columns([1, 1.2])
    with summary_col:
        st.subheader("Prediction Summary")
        st.metric("Predicted Condition", inference["inference"]["predicted_condition"])
        st.metric("Confidence", f'{inference["inference"]["confidence"]:.2f}%')

        probability_df = pd.DataFrame(inference["inference"]["class_probabilities"]).sort_values(
            "probability_percent",
            ascending=False,
        )
        st.write("Class probabilities")
        st.dataframe(probability_df, use_container_width=True, hide_index=True)

    with detail_col:
        st.subheader("Structured Output")
        st.code(dumps_pretty(analysis_payload), language="json")

    st.subheader("Top Model Contributors")
    explainability = inference.get("explainability", {})
    if "top_contributors" in explainability:
        contrib_df = pd.DataFrame(explainability["top_contributors"])
        st.dataframe(contrib_df, use_container_width=True, hide_index=True)
    else:
        st.warning(explainability.get("error", "No explainability output available."))

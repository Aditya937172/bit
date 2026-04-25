# BIT

A lightweight, end‑to‑end pipeline for ingesting medical reports, extracting key clinical values, normalizing the data, and generating a structured **JSON output** suitable for downstream analytics or machine‑learning inference.

This repository contains a local Python agent (CLI-style pipeline) that can read common document formats (PDF/TXT/CSV/JSON/Markdown and images via OCR), parse a fixed set of clinical fields, optionally fill missing values using reference ranges, and run an existing trained ML model through an adapter layer.

## Key Features

- **Multi-format ingestion**: Parse input from **PDF, TXT, CSV, JSON, Markdown** and (optionally) images via **Tesseract OCR**.
- **Clinical field extraction**: Extracts a predefined set of **24 clinical fields** from raw text.
- **Normalization & validation**: Normalizes values and can fill missing fields using reference ranges.
- **Model integration (no refactor needed)**: Uses a **model adapter** to run the existing trained model without modifying it.
- **Structured output**: Produces a single **well-structured JSON** containing:
  - ingestion metadata
  - parsed fields
  - normalized patient input
  - reference ranges
  - prediction output (class/probabilities/confidence)
  - explainability artifacts (feature importances / SHAP, when available)
- **Local testing**: Includes a **sample report** and a **smoke test** script to verify the pipeline.

## Repository Structure

- `agent/`
  - `agent.py` — main entry point (runs the full pipeline)
  - `parser.py` — text extraction + clinical field parsing
  - `model_adapter.py` — loads ranges/model artifacts and performs inference
  - `schema.py` — builds the final structured JSON schema
  - `sample_report.txt` — sample input for local testing
  - `test_local_agent.py` — quick smoke test for the agent

## Requirements

- Python 3.9+ (recommended)
- Typical dependencies include PDF parsing libs and ML stack packages (see `requirements.txt` if present).
- Optional: **Tesseract** installed locally for OCR support.

## Usage

Run the agent on a local file:

```bash
python agent/agent.py /path/to/report.pdf
```

For a quick local check using the included sample report:

```bash
python agent/test_local_agent.py
```

## Output

The pipeline writes one structured JSON output containing parsed values, normalized fields, reference ranges, and ML inference results.

## Contributing

Contributions are welcome.

1. Fork the repository
2. Create a new branch
3. Commit your changes
4. Open a pull request

## License

Add a license for this project (e.g., MIT) if you plan to distribute it.

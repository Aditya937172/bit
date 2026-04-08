# Agent Folder

This folder is a plain local Python pipeline. It does not use Streamlit.

Files:

- `agent.py`
  - Main entry point.
  - Takes a local file path.
  - Extracts text, parses clinical values, fills missing values if needed, runs the existing ML model, and writes one structured JSON output.

- `parser.py`
  - Handles file text extraction.
  - Supports PDF text extraction.
  - Supports TXT, JSON, CSV, and Markdown text extraction.
  - Supports image OCR if Tesseract is installed locally.
  - Parses the 24 clinical fields from raw text.

- `model_adapter.py`
  - Calls the existing project model without changing it.
  - Loads ranges from `Data/`.
  - Loads the trained model from `Data/`.
  - Runs scaling and prediction.
  - Returns probabilities, predicted class, confidence, feature importances, and SHAP explainability output.

- `schema.py`
  - Builds the structured JSON schema for:
  - document ingestion
  - parsed payload
  - normalized patient input
  - reference ranges
  - ML output

- `sample_report.txt`
  - Local sample medical report text for testing.

- `test_local_agent.py`
  - Local smoke test.
  - Runs the pipeline on `sample_report.txt` and checks that the JSON output contains parsed values and model output.

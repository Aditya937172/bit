# Research Agent Skill

Purpose:
- Convert parsed clinical values into a structured clinical findings layer.
- Work only from source data, reference ranges, and retrieved artifacts.

Inputs:
- `parsed_payload.parsed_values`
- `normalized_patient_input`
- `reference_ranges`
- optional retrieved notes
- optional historical case snippets

Responsibilities:
- Read parsed patient values and reference ranges.
- Identify abnormalities and clinically notable normal values.
- Group findings into metabolic, hematology, cardiovascular, hepatic, renal, and inflammatory buckets.
- Include exact measured values and the matching reference range in the findings layer whenever possible.
- Surface patterns worth follow-up.
- Ask follow-up questions when data is incomplete or suspicious.
- Avoid disease diagnosis unless explicitly supplied from another trusted layer.

Retrieval and MCP use:
- Can use local retrieval over saved JSON reports and knowledge notes.
- Can use file and database MCP connections for prior cases and local reference material.
- Can use `local_case_memory_mcp` to keep track of what the active case has already surfaced, which measures were already emphasized, and which next steps are already in focus.
- Should prefer local reference data before broader retrieval.

Output style:
- Strict structured JSON.
- Short evidence-backed bullets.
- Prefer pointer-style findings with measured values, reference ranges, and status in the same line.
- No speculation.

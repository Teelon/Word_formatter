import os
import json
import re
from openai import OpenAI
from pydantic import ValidationError
from docx import Document
from docx.shared import Pt

from models import SessionReport, SessionMetadata
from sections import add_header, add_summary, add_details, add_next_steps, add_footer

# Initialize OpenAI client for LM Studio
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

# ── Configurable clinician name ──────────────────────────────────────────
CLINICIAN_NAME = "Gabrielle"  # Change this for a different clinician

# ── Build the system prompt dynamically from the Pydantic model ──────────
EXTRACTION_RULES = f"""You are a Data Extraction Specialist. Your task is to extract information from clinical session notes and return a single, valid JSON object.

### EXTRACTION RULES:
1. CITATION REMOVAL: Remove all "" tags from every string.
2. REFERENCE REMOVAL: Remove all bracketed references such as [i], [j], [1], [2], [a], etc. from every string.
3. REPLACEMENT: Replace the word "clinician" and "clinician shared" with "{CLINICIAN_NAME}" in all extracted text.
4. PRESERVATION: Do not summarize or change the meaning; keep the clinical detail intact.
"""

def build_system_prompt() -> str:
    """Generates the system prompt with the JSON schema derived from the Pydantic model."""
    schema = SessionReport.model_json_schema()
    schema_str = json.dumps(schema, indent=2)

    return (
        f"{EXTRACTION_RULES}\n"
        f"### JSON SCHEMA (follow this exactly):\n"
        f"```json\n{schema_str}\n```\n\n"
        f"Output ONLY the raw JSON. No conversational text or markdown backticks."
    )


def get_session_data() -> SessionReport | None:
    """Reads session data, queries LLM, and returns a validated SessionReport."""

    if not os.path.exists("session_data.txt"):
        raise FileNotFoundError("Error: Ensure session_data.txt exists.")

    with open("session_data.txt", "r", encoding="utf-8") as f:
        session_data = f.read()

    system_prompt = build_system_prompt()

    print("--- Sending data to Local LLM ---")

    completion = client.chat.completions.create(
        model="local-model",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": session_data}
        ],
        temperature=0.2,
    )

    response_content = completion.choices[0].message.content
    print("--- LLM Response Received ---")

    # Strip markdown code blocks if present
    response_content = response_content.replace('```json', '').replace('```', '').strip()

    # Remove bracketed references like [i], [i, j], [1, 2], etc. (safety net)
    response_content = re.sub(r'\[\s*[a-zA-Z0-9]+(?:\s*,\s*[a-zA-Z0-9]+)*\s*\]', '', response_content)

    # Force-replace "clinician shared" and "clinician" (safety net – LLM may miss some)
    response_content = response_content.replace("clinician shared", CLINICIAN_NAME)
    response_content = response_content.replace("Clinician shared", CLINICIAN_NAME)
    response_content = response_content.replace("clinician", CLINICIAN_NAME)
    response_content = response_content.replace("Clinician", CLINICIAN_NAME)

    try:
        raw = json.loads(response_content)
        report = SessionReport.model_validate(raw)
        print("--- Validation passed ✓ ---")
        return report
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON: {e}")
        print(f"Raw response:\n{response_content}")
        return None
    except ValidationError as e:
        print(f"LLM response did not match expected schema:\n{e}")
        return None


# ── Document generation ─────────────────────────────────────────────────

def create_word_doc(report: SessionReport):
    """Generates a Word document from a validated SessionReport."""

    doc = Document()

    # Configure default style
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Times New Roman'
    font.size = Pt(9)

    # Default paragraph spacing (single, no extra space)
    pf = style.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing = 1.0

    meta: SessionMetadata = report.metadata

    # Build each section
    add_header(doc, meta)
    add_summary(doc, report.summary)
    add_details(doc, report.details)
    add_next_steps(doc, report.next_steps)
    add_footer(doc)

    # ── Build filename from metadata ────────────────────────────────────
    try:
        from dateutil import parser as dateparser
        dt_date = dateparser.parse(meta.session_date)
        dt_time = dateparser.parse(meta.session_time)
        date_slug = dt_date.strftime("%Y_%m_%d")
        time_slug = dt_time.strftime("%H_%M")
    except Exception:
        date_slug = meta.session_date.replace(" ", "_").replace(",", "")
        time_slug = meta.session_time.replace(":", "_")

    # Force last name to uppercase for filename
    name_parts = meta.patient_name.split(",", 1)
    display_name = f"{name_parts[0].upper()},{name_parts[1]}" if len(name_parts) == 2 else meta.patient_name.upper()

    filename = (
        f"{display_name} ({meta.session_type.replace('(', '').replace(')', '')})_"
        f"{meta.session_date} - {date_slug} {time_slug} EST - Notes by Gemini.docx"
    )
    doc.save(filename)
    print(f"Success! '{filename}' has been created.")


if __name__ == "__main__":
    report = get_session_data()
    if report:
        create_word_doc(report)
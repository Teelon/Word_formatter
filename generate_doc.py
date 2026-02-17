import os
import json
import re
from openai import OpenAI
from pydantic import ValidationError
from docx import Document
from docx.shared import Pt, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

from models import SessionReport, SessionMetadata, DetailItem

# Initialize OpenAI client for LM Studio
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

# ── Configurable clinician name ──────────────────────────────────────────
CLINICIAN_NAME = "Gabrielle"  # Change this for a different clinician

# ── Build the system prompt dynamically from the Pydantic model ──────────
EXTRACTION_RULES = f"""You are a Data Extraction Specialist. Your task is to extract information from therapy session notes and return a single, valid JSON object.

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


# ── Document generation (uses typed model directly) ─────────────────────

def create_word_doc(report: SessionReport):
    """Generates a Word document from a validated SessionReport."""

    doc = Document()

    # Configure default style
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Times New Roman'
    font.size = Pt(11)

    # Default paragraph spacing (single, no extra space)
    pf = style.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing = 1.0

    meta: SessionMetadata = report.metadata

    # ── Page Header (Word header section) ────────────────────────────
    section = doc.sections[0]
    header = section.header
    header.is_linked_to_previous = False

    # Remove the default empty paragraph from the header
    for p in header.paragraphs:
        p._element.getparent().remove(p._element)

    # Line 1: Two-column borderless table for left/right alignment
    #   Left cell:  LASTNAME, Firstname (DOB)
    #   Right cell: January 28, 2026; 10:00am
    header_table = header.add_table(rows=1, cols=2, width=Inches(6.5))
    header_table.autofit = True

    # Remove all table borders
    tbl = header_table._tbl
    tbl_pr = tbl.tblPr if tbl.tblPr is not None else tbl._add_tblPr()
    borders = tbl_pr.find(qn('w:tblBorders'))
    if borders is not None:
        tbl_pr.remove(borders)
    borders = tbl_pr.makeelement(qn('w:tblBorders'), {})
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        element = borders.makeelement(qn(f'w:{edge}'), {
            qn('w:val'): 'none', qn('w:sz'): '0',
            qn('w:space'): '0', qn('w:color'): 'auto'
        })
        borders.append(element)
    tbl_pr.append(borders)

    # Left cell – patient info
    patient_info = meta.patient_name
    if meta.dob:
        patient_info += f" ({meta.dob})"

    left_cell = header_table.cell(0, 0)
    left_para = left_cell.paragraphs[0]
    left_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    left_para.paragraph_format.space_before = Pt(0)
    left_para.paragraph_format.space_after = Pt(0)
    run_left = left_para.add_run(patient_info)
    run_left.font.name = 'Times New Roman'
    run_left.font.size = Pt(9)

    # Right cell – date / time
    session_datetime = f"{meta.session_date}; {meta.session_time}"

    right_cell = header_table.cell(0, 1)
    right_para = right_cell.paragraphs[0]
    right_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    right_para.paragraph_format.space_before = Pt(0)
    right_para.paragraph_format.space_after = Pt(0)
    run_right = right_para.add_run(session_datetime)
    run_right.font.name = 'Times New Roman'
    run_right.font.size = Pt(9)

    # Line 2: Session Type (bold, left-aligned paragraph below the table)
    header_para2 = header.add_paragraph()
    header_para2.paragraph_format.space_before = Pt(0)
    header_para2.paragraph_format.space_after = Pt(0)
    run2 = header_para2.add_run(meta.session_type)
    run2.font.name = 'Times New Roman'
    run2.font.size = Pt(9)
    run2.bold = True

    # ── Summary ──────────────────────────────────────────────────────
    summary_label = doc.add_paragraph()
    summary_label.paragraph_format.space_after = Pt(0)
    summary_label.add_run("Summary").bold = False

    summary_para = doc.add_paragraph(report.summary)
    summary_para.paragraph_format.space_before = Pt(0)

    doc.add_paragraph()  # Spacer

    # ── Details ──────────────────────────────────────────────────────
    details_label = doc.add_paragraph()
    details_label.paragraph_format.space_after = Pt(0)
    details_label.add_run("Details").bold = False

    for item in report.details:
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.left_indent = Inches(0.5)

        heading_run = p.add_run(f"{item.heading} ")
        heading_run.bold = True
        heading_run.font.name = 'Times New Roman'
        heading_run.font.size = Pt(9)

        content_run = p.add_run(item.content)
        content_run.font.name = 'Times New Roman'
        content_run.font.size = Pt(9)

    doc.add_paragraph()  # Spacer

    # ── Suggested Next Steps ─────────────────────────────────────────
    steps_label = doc.add_paragraph()
    steps_label.paragraph_format.space_after = Pt(0)
    steps_label.add_run("Suggested next steps").bold = False

    if not report.next_steps:
        doc.add_paragraph("No suggested next steps were found for this meeting.")
    else:
        for step in report.next_steps:
            sp = doc.add_paragraph(step, style='List Bullet')
            sp.paragraph_format.left_indent = Inches(0.5)

    # ── Footer (all pages) ─────────────────────────────────────────────
    footer = section.footer
    footer.is_linked_to_previous = False

    footer_para1 = footer.paragraphs[0]
    footer_para1.alignment = WD_ALIGN_PARAGRAPH.LEFT
    footer_para1.paragraph_format.space_before = Pt(0)
    footer_para1.paragraph_format.space_after = Pt(0)
    f_run1 = footer_para1.add_run("G. Maynard MSc. (Sup. Prac.)")
    f_run1.font.name = 'Times New Roman'
    f_run1.font.size = Pt(11)

    footer_para2 = footer.add_paragraph()
    footer_para2.alignment = WD_ALIGN_PARAGRAPH.LEFT
    footer_para2.paragraph_format.space_before = Pt(0)
    footer_para2.paragraph_format.space_after = Pt(0)
    f_run2 = footer_para2.add_run("G. Townsend, MSc. C. Psych. PsyD")
    f_run2.font.name = 'Times New Roman'
    f_run2.font.size = Pt(11)

    # ── Build filename from metadata ────────────────────────────────────
    # Format: LASTNAME, Firstname (Session Type) Date - YYYY_MM_DD HH_MM EST - Notes by Gemini.docx
    try:
        from dateutil import parser as dateparser
        dt_date = dateparser.parse(meta.session_date)
        dt_time = dateparser.parse(meta.session_time)
        date_slug = dt_date.strftime("%Y_%m_%d")
        time_slug = dt_time.strftime("%H_%M")
    except Exception:
        # Fallback if parsing fails
        date_slug = meta.session_date.replace(" ", "_").replace(",", "")
        time_slug = meta.session_time.replace(":", "_")

    # Force last name to uppercase for filename
    name_parts = meta.patient_name.split(",", 1)
    display_name = f"{name_parts[0].upper()},{name_parts[1]}" if len(name_parts) == 2 else meta.patient_name.upper()

    filename = (
        f"{display_name} ({meta.session_type}) "
        f"{meta.session_date} - {date_slug} {time_slug} EST - Notes by Gemini.docx"
    )
    doc.save(filename)
    print(f"Success! '{filename}' has been created.")


if __name__ == "__main__":
    report = get_session_data()
    if report:
        create_word_doc(report)
import os
import json
import re
import time
import shutil
import glob
from datetime import datetime
from openai import OpenAI
from pydantic import ValidationError
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_LINE_SPACING, WD_ALIGN_PARAGRAPH

from src.models import SessionReport, SessionMetadata
from src.sections import add_header, add_summary, add_details, add_next_steps, add_footer
from src.startup import preflight

# Initialize OpenAI client for LM Studio
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

# ── Configurable clinician name ──────────────────────────────────────────
CLINICIAN_NAME = "Gabrielle"  # Change this for a different clinician

# ── Directories ──────────────────────────────────────────────────────────
INPUT_DIR = "input_docs"
PROCESSED_DIR = "processed_docs"
OUTPUT_DIR = "output_docs"

# ── Build the system prompt dynamically from the Pydantic model ──────────
EXTRACTION_RULES = f"""You are a Data Extraction Specialist. Your task is to extract information from clinical session notes and return a single, valid JSON object.

### EXTRACTION RULES:
1. CITATION REMOVAL: Remove all "" tags from every string.
2. REFERENCE REMOVAL: Remove all bracketed references such as [i], [j], [1], [2], [a], etc. from every string.
3. REPLACEMENT: Replace the word "clinician" and "clinician shared" with "{CLINICIAN_NAME}" in all extracted text.
4. PRESERVATION: Do not summarize or change the meaning; keep the clinical detail intact.
"""

def log(message: str, style: str = "info"):
    """Helper for structured logging."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    if style == "header":
        print(f"\n[{timestamp}] ════ {message} ════")
    elif style == "success":
        print(f"[{timestamp}] ✓ {message}")
    elif style == "error":
        print(f"[{timestamp}] ✗ {message}")
    elif style == "info":
        print(f"[{timestamp}]   {message}")
    elif style == "dim":
        print(f"[{timestamp}]     {message}")

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


def extract_text_from_docx(file_path: str) -> str:
    """Extracts text from a Word document."""
    try:
        doc = Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)
    except Exception as e:
        log(f"Error reading {os.path.basename(file_path)}: {e}", "error")
        return ""


def parse_filename_metadata(filename: str) -> dict:
    """
    Extracts metadata from the filename.
    Expected format: 
    MITCHELL, Teelon (Structured Background History Interview)_February 17, 2026 - 2026_02_17 04_47_PM EST - Notes by Gemini.docx
    Returns a dictionary of found metadata.
    """
    meta = {}
    
    # Remove extension
    name_only = os.path.splitext(filename)[0]
    
    # Regex to handle the format
    pattern = r"^(.*?) \((.*?)\)_(.*?) - (\d{4}_\d{2}_\d{2} \d{2}_\d{2}_[AP]M [A-Z]{3})"
    
    match = re.search(pattern, name_only)
    if match:
        meta['patient_name'] = match.group(1).strip()
        meta['session_type'] = match.group(2).strip()
        timestamp_str = match.group(4)
        
        try:
            parts = timestamp_str.split(' ')
            if len(parts) >= 2:
                date_part = parts[0]
                time_part = parts[1]
                zone_part = parts[2] if len(parts) > 2 else ""
                
                dt_date = datetime.strptime(date_part, "%Y_%m_%d")
                meta['session_date'] = dt_date.strftime("%B %d, %Y")
                
                t_parts = time_part.split('_')
                if len(t_parts) == 3:
                     hour = t_parts[0]
                     minute = t_parts[1]
                     ampm = t_parts[2]
                     meta['session_time'] = f"{hour}:{minute} {ampm} {zone_part}".strip()
                else:
                    meta['session_time'] = time_part.replace('_', ':')
        except Exception as e:
            log(f"Error parsing timestamp: {e}", "error")

    return meta


def get_session_data(session_text: str, filename_meta: dict = None, model_id: str = "local-model") -> SessionReport | None:
    """Queries LLM with the provided session text and returns a validated SessionReport."""

    if not session_text.strip():
        log("Session text is empty.", "error")
        return None

    system_prompt = build_system_prompt()

    log("Sending data to Local LLM...", "info")

    start_time = time.time()
    try:
        completion = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": session_text}
            ],
            temperature=0.2,
        )
    except Exception as e:
        log(f"Error communicating with LLM: {e}", "error")
        return None

    end_time = time.time()
    elapsed_time = end_time - start_time
    usage = completion.usage
    total_tokens = usage.total_tokens if usage else 0

    log(f"LLM Response Received ({elapsed_time:.2f}s | {total_tokens} tokens)", "success")

    response_content = completion.choices[0].message.content
    response_content = response_content.replace('```json', '').replace('```', '').strip()
    response_content = re.sub(r'\[\s*[a-zA-Z0-9]+(?:\s*,\s*[a-zA-Z0-9]+)*\s*\]', '', response_content)
    
    # Force-replace clinician name
    for phrase in ["clinician shared", "Clinician shared", "clinician", "Clinician"]:
        response_content = response_content.replace(phrase, CLINICIAN_NAME)

    try:
        raw = json.loads(response_content)
        
        # Override metadata from filename if available
        if filename_meta and 'metadata' in raw:
            overrides = []
            if 'patient_name' in filename_meta:
                raw['metadata']['patient_name'] = filename_meta['patient_name']
                overrides.append("Name")
            if 'session_type' in filename_meta:
                raw['metadata']['session_type'] = filename_meta['session_type']
                overrides.append("Type")
            if 'session_date' in filename_meta:
                raw['metadata']['session_date'] = filename_meta['session_date']
                overrides.append("Date")
            if 'session_time' in filename_meta:
                raw['metadata']['session_time'] = filename_meta['session_time']
                overrides.append("Time")
            
            if overrides:
                log(f"Applied metadata from filename: {', '.join(overrides)}", "dim")
        
        report = SessionReport.model_validate(raw)
        log("JSON Validation passed", "success")
        return report
    except json.JSONDecodeError as e:
        log(f"Failed to decode JSON: {e}", "error")
        return None
    except ValidationError as e:
        log(f"Schema validation failed: {e}", "error")
        return None


# ── Document generation ─────────────────────────────────────────────────

def create_word_doc(report: SessionReport, output_dir: str):
    """Generates a Word document from a validated SessionReport and saves it to output_dir."""
    doc = Document()
    
    # [Rest of styling code omitted for brevity but preserved in behavior]
    # Configure default style
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Times New Roman'
    font.size = Pt(9)
    pf = style.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(4)
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = 1.15

    try:
        lb_style = doc.styles['List Bullet']
        lb_font = lb_style.font
        lb_font.name = 'Times New Roman'
        lb_font.size = Pt(9)
        lb_pf = lb_style.paragraph_format
        lb_pf.space_before = Pt(0)
        lb_pf.space_after = Pt(4)
        lb_pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        lb_pf.line_spacing = 1.15
    except KeyError:
        pass

    meta: SessionMetadata = report.metadata

    # Date/Time formatting attempt
    try:
        from dateutil import parser as dateparser
        time_str = meta.session_time
        for tz in ["EST", "EDT", "CST", "CDT", "PST", "PDT"]:
            time_str = time_str.replace(f" {tz}", "").replace(tz, "")
        time_str = time_str.strip()
        dt_time = dateparser.parse(time_str)
        meta.session_time = dt_time.strftime("%I:%M %p")
        
        dt_date = dateparser.parse(meta.session_date)
        date_slug = dt_date.strftime("%Y_%m_%d")
        time_slug = dt_time.strftime("%I_%M_%p")
    except Exception:
        date_slug = meta.session_date.replace(" ", "_").replace(",", "")
        time_slug = meta.session_time.replace(":", "_").replace(" ", "") + "_ERROR"

    add_header(doc, meta)
    add_summary(doc, report.summary)
    add_details(doc, report.details)
    add_next_steps(doc, report.next_steps)
    add_footer(doc)

    # Build filename
    name_parts = meta.patient_name.split(",", 1)
    if len(name_parts) >= 2:
        display_name = f"{name_parts[0].upper()},{name_parts[1]}"
    else:
        display_name = meta.patient_name.upper()

    filename = (
        f"{display_name} ({meta.session_type.replace('(', '').replace(')', '')})_"
        f"{meta.session_date} - {date_slug} {time_slug} EST - Notes by Gemini.docx"
    )
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    output_path = os.path.join(output_dir, filename)
    
    doc.save(output_path)
    log(f"Generated Report: {filename}", "success")


def process_batch(model_id: str):
    """Batches processes word docs in INPUT_DIR."""
    
    # Ensure directories exist
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    input_pattern = os.path.join(INPUT_DIR, "*.docx")
    files_to_process = glob.glob(input_pattern)

    print(f"\nScanning '{INPUT_DIR}'...")
    if not files_to_process:
        print(f"No .docx files found. Waiting for inputs.\n")
        return

    print(f"Found {len(files_to_process)} document(s).\n")

    for i, file_path in enumerate(files_to_process, 1):
        filename = os.path.basename(file_path)
        log(f"Processing File {i}/{len(files_to_process)}: {filename}", "header")
        
        # 1. Extract text
        session_text = extract_text_from_docx(file_path)
        file_meta = parse_filename_metadata(filename)
        
        if not session_text:
            log("Skipping empty or unreadable file", "error")
            continue

        # 2. Get data from LLM
        report = get_session_data(session_text, file_meta, model_id)

        if report:
            # 3. Create Output Doc
            create_word_doc(report, OUTPUT_DIR)

            # 4. Move processed file
            try:
                destination = os.path.join(PROCESSED_DIR, filename)
                if os.path.exists(destination):
                    base, ext = os.path.splitext(filename)
                    timestamp = time.strftime("%Y%m%d-%H%M%S")
                    destination = os.path.join(PROCESSED_DIR, f"{base}_{timestamp}{ext}")
                
                shutil.move(file_path, destination)
                log(f"Moved source to processed folder", "dim")
            except Exception as e:
                log(f"Error moving file: {e}", "error")
        else:
            log(f"Failed to generate report", "error")

if __name__ == "__main__":
    model_id_to_use = preflight()
    process_batch(model_id_to_use)
# Clinical Session Note Processor

A local-first, AI-powered tool that converts raw clinical session notes (`.docx`) into structured, professionally formatted Word documents. It uses a locally hosted LLM via **LM Studio** to extract patient metadata, session summaries, key details, and suggested next steps — then assembles them into a clean report.

## How It Works

1. **Drop** one or more `.docx` session note files into the `input_docs/` folder.
2. **Run** `python generate_doc.py`.
3. The script performs preflight checks (packages, LM Studio server, model), then for each file:
   - Extracts text from the Word document.
   - Parses metadata (patient name, session type, date/time) from the filename.
   - Sends the text to the local LLM, which returns structured JSON validated against a Pydantic schema.
   - Generates a formatted Word report with header, summary, details, next steps, and footer.
4. Completed source files are moved to `processed_docs/`; generated reports land in `output_docs/`.

## Project Structure

```
project/
├── generate_doc.py          # Main entry point — orchestrates the full pipeline
├── input_docs/              # Place raw session note .docx files here
├── output_docs/             # Generated reports appear here
├── processed_docs/          # Source files are moved here after processing
└── src/
    ├── models.py            # Pydantic data models (SessionReport, SessionMetadata, DetailItem)
    ├── startup.py           # Preflight checks — packages, LM Studio server & model loading
    └── sections/            # Document section builders
        ├── header.py        # Patient info header block
        ├── summary.py       # Summary paragraph
        ├── details.py       # Detail bullet points
        ├── next_steps.py    # Suggested next steps list
        └── footer.py        # Clinician footer
```

## Prerequisites

Before running the tool, make sure the following are installed and available:

### 1. Python 3.10+

Download from [python.org](https://www.python.org/downloads/). Verify with:

```bash
python --version
```

### 2. LM Studio

This tool uses [LM Studio](https://lmstudio.ai/) to run a local LLM. Install it and ensure the `lms` CLI is available in your system PATH.

```bash
lms --version
```

> **Note:** The preflight script will attempt to start the LM Studio server and load the model automatically if they aren't already running.

### 3. LLM Model

The default model is **`ibm/granite-4-h-tiny`**. Download it through LM Studio before first run. You can change the preferred model in `src/startup.py` by editing the `PREFERRED_MODEL` variable.

### 4. Python Packages

The following packages are required (auto-installed by the preflight script if missing):

| Package            | Purpose                                 |
| ------------------ | --------------------------------------- |
| `openai`           | OpenAI-compatible client for LM Studio  |
| `pydantic`         | Data validation & JSON schema generation|
| `python-docx`      | Reading and writing Word documents      |
| `python-dateutil`  | Flexible date/time parsing              |
| `requests`         | HTTP requests to LM Studio API          |

To install manually:

```bash
pip install openai pydantic python-docx python-dateutil requests
```

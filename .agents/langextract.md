Agent Knowledge: LangExtract Library
Core Purpose
LangExtract is a Python library used to extract structured information from unstructured text (clinical notes, reports, etc.) using LLMs. Its primary advantage is Source Grounding, which maps extracted data back to its exact location in the original text.

Key Technical Capabilities

Structured Output: Uses lx.data.Extraction and lx.data.ExampleData to enforce schemas.

Chunking Strategy: Optimized for long documents by using parallel processing and multiple extraction passes (extraction_passes) to increase recall.

Traceability: Generates interactive HTML visualizations to verify extractions in context.

Model Support: Primarily optimized for Gemini (using controlled generation) but supports OpenAI and Ollama (local LLMs).

Implementation Pattern for the Agent

Define the Task: A clear text description of what to extract.

Provide Few-Shot Examples: The library is highly dependent on ExampleData. Each example must include the text and a list of Extraction objects containing extraction_class, extraction_text (verbatim from source), and attributes.

Execute: Use the lx.extract() function.

Default Model: gemini-2.5-flash (balanced) or gemini-2.5-pro (complex reasoning).

Save/Visualize: Use lx.io.save_annotated_documents() and lx.visualize().

Constraint for the Agent

Verbatim Extraction: The library works best when extraction_text is quoted exactly from the source to avoid "Prompt alignment" warnings.

Privacy: For health data, usage is subject to Health AI Developer Foundations Terms.
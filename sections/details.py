"""Details section: label + indented bullet points with bold headings."""

from docx.shared import Pt, Inches

from models import DetailItem


def add_details(doc, details: list[DetailItem]):
    """Adds the Details label and bullet-point items to the document body."""
    details_label = doc.add_paragraph()
    details_label.paragraph_format.space_after = Pt(0)
    run_label = details_label.add_run("Details")
    run_label.bold = False
    run_label.font.name = 'Times New Roman'
    run_label.font.size = Pt(9)

    for item in details:
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

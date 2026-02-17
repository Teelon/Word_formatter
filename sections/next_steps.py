"""Suggested Next Steps section: label + bullet list."""

from docx.shared import Pt, Inches


def add_next_steps(doc, next_steps: list[str]):
    """Adds the Suggested Next Steps label and items to the document body."""
    steps_label = doc.add_paragraph()
    steps_label.paragraph_format.space_after = Pt(0)
    run_label = steps_label.add_run("Suggested next steps")
    run_label.bold = False
    run_label.font.name = 'Times New Roman'
    run_label.font.size = Pt(9)

    if not next_steps:
        p = doc.add_paragraph()
        run = p.add_run("No suggested next steps were found for this meeting.")
        run.font.name = 'Times New Roman'
        run.font.size = Pt(9)
    else:
        for step in next_steps:
            sp = doc.add_paragraph(style='List Bullet')
            sp.paragraph_format.left_indent = Inches(0.5)
            # Clear the auto-generated run and re-add with correct font
            sp.clear()
            run = sp.add_run(step)
            run.font.name = 'Times New Roman'
            run.font.size = Pt(9)

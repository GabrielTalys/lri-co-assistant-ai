from datetime import datetime
from pathlib import Path

from fpdf import FPDF


def _latin1_safe(text: str) -> str:
    return str(text or '').encode('latin-1', errors='replace').decode('latin-1')


def _write_wrapped_text(pdf: FPDF, text: str, line_height: float = 6) -> None:
    width = pdf.w - pdf.l_margin - pdf.r_margin
    for raw_line in _latin1_safe(text).split('\n'):
        line = raw_line.rstrip()
        if line:
            # Char-level wrapping keeps long unbroken strings (URLs, ids) inside the page.
            pdf.multi_cell(width, line_height, line, new_x='LMARGIN', new_y='NEXT', wrapmode='CHAR')
        else:
            pdf.ln(line_height)


def _write_section(pdf: FPDF, heading: str, content: str) -> None:
    pdf.set_font('Helvetica', 'B', 12)
    _write_wrapped_text(pdf, heading, line_height=7)
    pdf.set_font('Helvetica', '', 11)
    _write_wrapped_text(pdf, content, line_height=6)


def build_pdf(output_path: str, title: str, phase_data: dict, decision_text: str) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    generated_on = datetime.now().strftime('%B %d, %Y')

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_compression(False)
    pdf.add_page()
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(
        0,
        6,
        _latin1_safe(f'Workshop date: {generated_on}'),
        align='R',
        new_x='LMARGIN',
        new_y='NEXT',
    )
    pdf.set_font('Helvetica', 'B', 16)
    _write_wrapped_text(pdf, f'LRI Report - {title}', line_height=10)

    for phase, content in phase_data.items():
        pdf.ln(3)
        _write_section(pdf, phase, content)

    if (decision_text or '').strip():
        pdf.ln(2)
        _write_section(pdf, 'Decision', decision_text)

    pdf.output(str(path))
    return str(path)

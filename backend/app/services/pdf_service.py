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
            try:
                # fpdf2 path: keep cursor consistent and allow char-level wrapping.
                pdf.multi_cell(
                    width,
                    line_height,
                    line,
                    new_x='LMARGIN',
                    new_y='NEXT',
                    wrapmode='CHAR',
                )
            except TypeError:
                # Legacy compatibility when running with older fpdf signature.
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(width, line_height, line)
        else:
            pdf.ln(line_height)


def build_pdf(output_path: str, title: str, phase_data: dict, summary_text: str, decision_text: str) -> str:
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

    pdf.set_font('Helvetica', '', 11)
    for phase, content in phase_data.items():
        pdf.ln(3)
        pdf.set_font('Helvetica', 'B', 12)
        _write_wrapped_text(pdf, phase, line_height=7)
        pdf.set_font('Helvetica', '', 11)
        _write_wrapped_text(pdf, content, line_height=6)

    if (summary_text or '').strip():
        pdf.ln(4)
        pdf.set_font('Helvetica', 'B', 12)
        _write_wrapped_text(pdf, 'AI Summary', line_height=7)
        pdf.set_font('Helvetica', '', 11)
        _write_wrapped_text(pdf, summary_text, line_height=6)

    if (decision_text or '').strip():
        pdf.ln(2)
        pdf.set_font('Helvetica', 'B', 12)
        _write_wrapped_text(pdf, 'Decision', line_height=7)
        pdf.set_font('Helvetica', '', 11)
        _write_wrapped_text(pdf, decision_text, line_height=6)

    pdf.output(str(path))
    return str(path)

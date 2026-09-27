import os
import re
from typing import Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from app.config import settings


def sanitize_filename(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name).strip('_')


def generate_cover_letter_pdf(
    candidate_name: str,
    company_name: str,
    job_title: str,
    cover_letter_markdown: str,
    output_dir: Optional[str] = None
) -> str:
    """
    Compiles cover letter markdown into a sleek, professional,
    single-page PDF using ReportLab.
    """
    target_dir = output_dir or settings.STORAGE_DIR
    os.makedirs(target_dir, exist_ok=True)

    company_slug = sanitize_filename(company_name)
    filename = f"Emmanuel_Okeibunor_Cover_Letter_{company_slug}.pdf"
    file_path = os.path.join(target_dir, filename)

    # Document setup with compact 0.5 inch margins to ensure single-page fit
    doc = SimpleDocTemplate(
        file_path,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    header_name_style = ParagraphStyle(
        'HeaderName',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=3
    )

    header_sub_style = ParagraphStyle(
        'HeaderSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#475569'),
        spaceAfter=8
    )

    meta_style = ParagraphStyle(
        'MetaStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=10
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=8,
        alignment=0  # Left-aligned
    )

    signoff_style = ParagraphStyle(
        'SignoffStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=6
    )

    story = []

    # Header
    story.append(Paragraph("EMMANUEL OKEIBUNOR", header_name_style))
    contact_line = (
        "Lagos, Nigeria (Open to Relocation & Remote) &nbsp;|&nbsp; "
        "okeibunoremma@gmail.com &nbsp;|&nbsp; "
        "+234 9015379412 &nbsp;|&nbsp; "
        "okeibunoremma.work"
    )
    story.append(Paragraph(contact_line, header_sub_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    # Re: Line
    story.append(Paragraph(f"<b>Application:</b> {job_title} &mdash; <i>{company_name}</i>", meta_style))

    # Process markdown paragraphs
    # Strip any markdown symbols like # or *
    clean_text = cover_letter_markdown.replace("**", "<b>").replace("__", "<b>")
    paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]

    for p in paragraphs:
        # Check if it is a list or regular paragraph
        clean_p = p.replace("\n", " ").strip()
        story.append(Paragraph(clean_p, body_style))

    # Signoff
    story.append(Paragraph("Sincerely,<br/><b>Emmanuel Okeibunor</b>", signoff_style))

    # Build PDF
    doc.build(story)
    return file_path

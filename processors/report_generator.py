"""
Generates a Hebrew/English PDF report for the doctor using ReportLab.
Uses Arial (Windows) for Hebrew glyph support + python-bidi for RTL rendering.
"""

import io
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER
from bidi.algorithm import get_display

from models.report import AllergyReport, AllergySeverity
from models.document import AnalyzedDocument, AllergyRelevance

# ── Font registration ─────────────────────────────────────────────────────────

def _register_fonts():
    try:
        fonts = Path("C:/Windows/Fonts")
        pdfmetrics.registerFont(TTFont("Arial",        str(fonts / "arial.ttf")))
        pdfmetrics.registerFont(TTFont("Arial-Bold",   str(fonts / "arialbd.ttf")))
        pdfmetrics.registerFont(TTFont("Arial-Italic", str(fonts / "ariali.ttf")))
        return "Arial", "Arial-Bold", "Arial-Italic"
    except Exception:
        return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"

FN, FNB, FNI = _register_fonts()   # normal, bold, italic


def _he(text: str) -> str:
    """Apply BiDi so Hebrew displays RTL inside ReportLab's LTR engine."""
    if not text:
        return ""
    return get_display(str(text))


# ── Severity metadata ─────────────────────────────────────────────────────────

_SEV_COLOR = {
    AllergySeverity.CONFIRMED_SEVERE:   colors.HexColor("#C0392B"),
    AllergySeverity.CONFIRMED_MODERATE: colors.HexColor("#E67E22"),
    AllergySeverity.PROBABLE:           colors.HexColor("#F1C40F"),
    AllergySeverity.QUESTIONABLE:       colors.HexColor("#2980B9"),
    AllergySeverity.INSUFFICIENT_DATA:  colors.HexColor("#7F8C8D"),
}

_SEV_EN = {
    AllergySeverity.CONFIRMED_SEVERE:   "Confirmed Severe Allergy",
    AllergySeverity.CONFIRMED_MODERATE: "Confirmed Moderate Allergy",
    AllergySeverity.PROBABLE:           "Probable Allergy",
    AllergySeverity.QUESTIONABLE:       "Questionable / Unconfirmed",
    AllergySeverity.INSUFFICIENT_DATA:  "Insufficient Data",
}

_SEV_HE = {
    AllergySeverity.CONFIRMED_SEVERE:   _he("אלרגיה חמורה מאושרת"),
    AllergySeverity.CONFIRMED_MODERATE: _he("אלרגיה בינונית מאושרת"),
    AllergySeverity.PROBABLE:           _he("אלרגיה סבירה"),
    AllergySeverity.QUESTIONABLE:       _he("אלרגיה לא מאושרת / מפוקפקת"),
    AllergySeverity.INSUFFICIENT_DATA:  _he("נתונים לא מספיקים"),
}


# ── Main generator ────────────────────────────────────────────────────────────

def generate_pdf(report: AllergyReport, analyzed_docs: list[AnalyzedDocument]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    base = getSampleStyleSheet()["Normal"]

    def style(name, **kw):
        kw.setdefault("fontName", FN)
        return ParagraphStyle(name, parent=base, **kw)

    title_s   = style("T",  fontSize=18, spaceAfter=6,  textColor=colors.HexColor("#1A252F"), alignment=TA_CENTER)
    sub_s     = style("S",  fontSize=11, spaceAfter=4,  textColor=colors.grey, alignment=TA_CENTER)
    section_s = style("H",  fontSize=13, spaceBefore=12, spaceAfter=4, textColor=colors.HexColor("#2C3E50"), fontName=FNB)
    body_s    = style("B",  fontSize=10, spaceAfter=4,  leading=14)
    flag_s    = style("F",  fontSize=10, spaceAfter=4,  leading=14, textColor=colors.HexColor("#922B21"))
    footer_s  = style("Ft", fontSize=8,  textColor=colors.grey, alignment=TA_CENTER)
    exc_s     = style("E",  fontSize=8,  leading=11, fontName=FNI)
    sig_s     = style("Si", fontSize=10, spaceAfter=4, leading=14, textColor=colors.HexColor("#884EA0"))
    ban_s     = style("Ba", fontSize=13, alignment=TA_CENTER, fontName=FNB)

    story = []

    # Header
    story += [
        Paragraph("Allergy Validation Report", title_s),
        Paragraph(f"Meuhedet Health Services | Generated: {report.generated_at}", sub_s),
        HRFlowable(width="100%", thickness=2, color=colors.HexColor("#2C3E50")),
        Spacer(1, 0.4*cm),
    ]

    # Patient info
    story.append(Paragraph("Patient Information", section_s))
    pt = Table([
        ["Patient ID:", report.patient_id,
         "Patient Name:", _he(report.patient_name)],
        ["Reported Allergy:", _he(report.reported_allergy),
         "Documents Reviewed:", str(report.total_documents_reviewed)],
    ], colWidths=[3.5*cm, 5.5*cm, 3.5*cm, 4*cm])
    pt.setStyle(TableStyle([
        ("FONTNAME",    (0, 0), (-1, -1), FN),
        ("FONTNAME",    (0, 0), (0, -1),  FNB),
        ("FONTNAME",    (2, 0), (2, -1),  FNB),
        ("FONTSIZE",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [pt, Spacer(1, 0.3*cm)]

    # Severity banner
    sev_color = _SEV_COLOR[report.severity]
    bt = Table([[
        Paragraph(f'<font color="white">SEVERITY: {_SEV_EN[report.severity]}</font>', ban_s),
        Paragraph(f'<font color="white">{_SEV_HE[report.severity]}</font>', ban_s),
    ]], colWidths=[8.25*cm, 8.25*cm])
    bt.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), sev_color),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [bt, Spacer(1, 0.3*cm),
              Paragraph(report.severity_explanation, body_s),
              Spacer(1, 0.2*cm)]

    # Statistics
    story.append(Paragraph("Document Statistics", section_s))
    st = Table([
        ["Total reviewed", "Relevant", "Allergist visits", "Derm. visits", "ER / Hosp."],
        [str(report.total_documents_reviewed), str(report.relevant_documents_count),
         str(report.allergist_visits), str(report.dermatologist_visits),
         str(report.er_or_hospitalization_events)],
    ], colWidths=[3.6*cm]*5)
    st.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), FNB),
        ("FONTNAME",      (0, 1), (-1, 1), FN),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BACKGROUND",    (0, 1), (-1, 1), colors.HexColor("#EBF5FB")),
    ]))
    story.append(st)

    # Conditions
    if report.confirmed_conditions:
        story.append(Paragraph("Confirmed Conditions / Diagnoses", section_s))
        for c in report.confirmed_conditions:
            story.append(Paragraph(f"&#x2022; {_he(c)}", body_s))

    # Symptoms
    if report.reported_symptoms:
        story.append(Paragraph("Reported Symptoms", section_s))
        for s in report.reported_symptoms:
            story.append(Paragraph(f"&#x2022; {_he(s)}", body_s))

    # Timeline
    if report.timeline:
        story.append(Paragraph("Clinical Timeline", section_s))
        tl_rows = [["Date", "Event", "Doc"]]
        for e in sorted(report.timeline, key=lambda x: x.get("date", "")):
            tl_rows.append([e.get("date",""), _he(e.get("event","")), e.get("doc_id","")])
        tlt = Table(tl_rows, colWidths=[2.5*cm, 12.5*cm, 1.5*cm])
        tlt.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), FNB),
            ("FONTNAME",      (0, 1), (-1, -1), FN),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("GRID",          (0, 0), (-1, -1), 0.5, colors.grey),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F3F4")]),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(tlt)

    # Red flags
    if report.flags:
        story.append(Paragraph("Red Flags", section_s))
        for flag in report.flags:
            story.append(Paragraph(f"&#9888; {_he(flag)}", flag_s))

    # Recommendation
    story.append(Paragraph("Recommendation for Treating Physician", section_s))
    rec = Table(
        [[Paragraph(_he(report.doctor_recommendation), body_s)]],
        colWidths=[16.5*cm],
    )
    rec.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#EBF5FB")),
        ("BOX",           (0, 0), (-1, -1), 1, colors.HexColor("#2980B9")),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
    ]))
    story.append(KeepTogether(rec))

    # Relevant documents with source excerpts
    relevant = [d for d in analyzed_docs
                if d.relevance in (AllergyRelevance.HIGH, AllergyRelevance.MEDIUM)]
    if relevant:
        story.append(Paragraph("Relevant Documents Summary", section_s))
        for ad in sorted(relevant, key=lambda x: x.document.date):
            rel_badge = "HIGH" if ad.relevance == AllergyRelevance.HIGH else "MED"
            rel_color = "#C0392B" if ad.relevance == AllergyRelevance.HIGH else "#E67E22"
            header = (
                f'<b>[{ad.document.doc_id}]</b> {ad.document.date}'
                f' &nbsp;|&nbsp; {ad.document.source}'
                f' &nbsp;|&nbsp; {_he(ad.document.specialty or "")}'
                f' &nbsp;<font color="{rel_color}"><b>[{rel_badge}]</b></font>'
            )
            story.append(Paragraph(header, body_s))
            story.append(Paragraph(f"Summary: {_he(ad.summary)}", body_s))
            if ad.allergy_signals:
                story.append(Paragraph("Signals: " + ", ".join(ad.allergy_signals), sig_s))

            if ad.document.content:
                raw = ad.document.content[:220]
                if len(ad.document.content) > 220:
                    raw += "..."
                exc = _he(raw).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                exc_box = Table(
                    [[Paragraph(f'<font color="#555555">Source [{ad.document.doc_id}]: {exc}</font>', exc_s)]],
                    colWidths=[16.5*cm],
                )
                exc_box.setStyle(TableStyle([
                    ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
                    ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
                    ("TOPPADDING",    (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                story.append(exc_box)

            story += [Spacer(1, 0.15*cm),
                      HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey)]

    # Footer
    story += [
        Spacer(1, 0.5*cm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2C3E50")),
        Paragraph(
            "This report was generated automatically by the Allergy Validator system. "
            "It is intended to assist clinical decision-making and does not replace physician judgment.",
            footer_s,
        ),
    ]

    doc.build(story)
    buffer.seek(0)
    return buffer.read()

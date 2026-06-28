"""
Uses Claude to analyze medical documents and determine allergy severity.
Two-pass approach:
  1. Per-document: classify relevance and extract allergy signals.
  2. Holistic: synthesize all relevant docs into a final report.
"""

import json
import os
from anthropic import Anthropic

from models.document import MedicalDocument, AnalyzedDocument, AllergyRelevance
from models.report import AllergyReport, AllergySeverity

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = "claude-sonnet-4-6"

# ── Prompts ────────────────────────────────────────────────────────────────────

DOC_CLASSIFICATION_SYSTEM = """אתה מערכת רפואית המנתחת מסמכים רפואיים של מטופלים.
תפקידך לזהות האם מסמך רפואי קשור לאלרגיה של המטופל ומה רמת הרלוונטיות שלו.

החזר תמיד JSON בלבד (ללא טקסט נוסף) בפורמט הבא:
{
  "relevance": "high" | "medium" | "low" | "not_relevant",
  "allergy_signals": ["רשימת סממנים", "שמצאת"],
  "summary": "סיכום קצר של הממצא הרלוונטי לאלרגיה",
  "confidence": 0.0-1.0
}

הגדרות רלוונטיות:
- high: ביקור אלרגולוג, תגובה אנפילקטית, מבחן עור חיובי, אשפוז בגלל אלרגיה
- medium: פריחה/גרד/אורטיקריה שמוזכרת, ביקור עורולוג בהקשר אלרגי, עלייה ב-IgE
- low: תסמינים כללאיים שיכולים להיות קשורים (שלשולים, כאב בטן), תיעוד היסטורי
- not_relevant: מסמך שאינו קשור כלל לאלרגיה"""


def classify_document(doc: MedicalDocument, reported_allergy: str) -> AnalyzedDocument:
    """Pass 1: classify a single document's relevance to the reported allergy."""
    prompt = (
        f"האלרגיה המדווחת של המטופל: {reported_allergy}\n\n"
        f"מסמך רפואי:\n"
        f"תאריך: {doc.date}\n"
        f"מקור: {doc.source} | {doc.specialty or ''}\n"
        f"רופא: {doc.doctor_name or 'לא ידוע'}\n\n"
        f"תוכן:\n{doc.content}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=DOC_CLASSIFICATION_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw)

    return AnalyzedDocument(
        document=doc,
        relevance=AllergyRelevance(data["relevance"]),
        allergy_signals=data.get("allergy_signals", []),
        summary=data.get("summary", ""),
        confidence=float(data.get("confidence", 0.5)),
    )


SYNTHESIS_SYSTEM = """אתה רופא בכיר המתמחה באלרגולוגיה.
קיבלת ממצאים מסוכמים של מסמכים רפואיים של מטופל ואתה צריך לסנתז דוח מקיף לרופא המטפל.

החזר JSON בלבד (ללא טקסט נוסף) בפורמט הבא:
{
  "severity": "confirmed_severe" | "confirmed_moderate" | "probable" | "questionable" | "insufficient_data",
  "severity_explanation": "הסבר תמציתי",
  "confirmed_conditions": ["רשימת אבחנות/מחלות מאושרות"],
  "reported_symptoms": ["רשימת תסמינים שדווחו"],
  "timeline": [
    {"date": "YYYY-MM-DD", "event": "תיאור אירוע", "doc_id": "D001"}
  ],
  "doctor_recommendation": "המלצה לרופא המטפל — מה לבדוק, מה לשקול",
  "flags": ["דגלים אדומים שדורשים תשומת לב"]
}

הגדרות חומרה:
- confirmed_severe: תגובה אנפילקטית מתועדת, אשפוז בשל אלרגיה, מבחן עור חיובי חזק
- confirmed_moderate: ביקורי אלרגולוג עם ממצאים, תגובות חוזרות ומתועדות
- probable: סממנים עקיפים ברורים אך ללא אישור ישיר מאלרגולוג
- questionable: אירוע בודד לא מאושר, תיעוד חלקי
- insufficient_data: אין מספיק מסמכים לקביעה"""


def synthesize_report(
    patient_id: str,
    patient_name: str,
    reported_allergy: str,
    analyzed_docs: list[AnalyzedDocument],
    generated_at: str,
) -> AllergyReport:
    """Pass 2: synthesize all relevant documents into a final AllergyReport."""

    relevant = [
        d for d in analyzed_docs
        if d.relevance in (AllergyRelevance.HIGH, AllergyRelevance.MEDIUM)
    ]
    low = [d for d in analyzed_docs if d.relevance == AllergyRelevance.LOW]

    # Build context for Claude
    lines = [f"מטופל: {patient_name} | אלרגיה מדווחת: {reported_allergy}\n"]
    lines.append("=== מסמכים בעלי רלוונטיות גבוהה/בינונית ===")
    for ad in relevant:
        lines.append(
            f"[{ad.document.doc_id}] {ad.document.date} | {ad.document.source} | "
            f"{ad.document.specialty or ''}\n"
            f"סיכום: {ad.summary}\n"
            f"סממנים: {', '.join(ad.allergy_signals)}\n"
        )

    if low:
        lines.append("=== מסמכים בעלי רלוונטיות נמוכה ===")
        for ad in low:
            lines.append(f"[{ad.document.doc_id}] {ad.document.date} | {ad.summary}")

    context = "\n".join(lines)

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYNTHESIS_SYSTEM,
        messages=[{"role": "user", "content": context}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw)

    allergist_visits = sum(
        1 for d in analyzed_docs
        if d.document.source in ("allergist",) and d.relevance != AllergyRelevance.NOT_RELEVANT
    )
    derm_visits = sum(
        1 for d in analyzed_docs
        if d.document.source in ("dermatologist",) and d.relevance != AllergyRelevance.NOT_RELEVANT
    )
    er_events = sum(
        1 for d in analyzed_docs
        if d.document.source in ("er", "hospital") and d.relevance != AllergyRelevance.NOT_RELEVANT
    )

    return AllergyReport(
        patient_id=patient_id,
        patient_name=patient_name,
        reported_allergy=reported_allergy,
        generated_at=generated_at,
        severity=AllergySeverity(data["severity"]),
        severity_explanation=data["severity_explanation"],
        confirmed_conditions=data.get("confirmed_conditions", []),
        reported_symptoms=data.get("reported_symptoms", []),
        relevant_document_ids=[d.document.doc_id for d in relevant],
        timeline=data.get("timeline", []),
        doctor_recommendation=data["doctor_recommendation"],
        flags=data.get("flags", []),
        total_documents_reviewed=len(analyzed_docs),
        relevant_documents_count=len(relevant),
        allergist_visits=allergist_visits,
        dermatologist_visits=derm_visits,
        er_or_hospitalization_events=er_events,
    )


def analyze_patient(
    patient_id: str,
    patient_name: str,
    reported_allergy: str,
    documents: list[MedicalDocument],
    generated_at: str,
) -> tuple[AllergyReport, list[AnalyzedDocument]]:
    """Full pipeline: classify each doc, then synthesize report."""
    analyzed = [classify_document(doc, reported_allergy) for doc in documents]
    report = synthesize_report(
        patient_id, patient_name, reported_allergy, analyzed, generated_at
    )
    return report, analyzed

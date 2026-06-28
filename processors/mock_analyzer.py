"""
Mock analyzer — returns pre-built responses for demo purposes (no API key needed).
Used when MOCK_MODE=true in .env or when ANTHROPIC_API_KEY is not set.
"""

from models.document import MedicalDocument, AnalyzedDocument, AllergyRelevance, DocumentType
from models.report import AllergyReport, AllergySeverity

_RELEVANCE_MAP = {
    DocumentType.ALLERGIST_VISIT: AllergyRelevance.HIGH,
    DocumentType.DERMATOLOGIST_VISIT: AllergyRelevance.MEDIUM,
    DocumentType.ER_VISIT: AllergyRelevance.HIGH,
    DocumentType.HOSPITALIZATION: AllergyRelevance.HIGH,
    DocumentType.LAB_RESULT: AllergyRelevance.MEDIUM,
    DocumentType.FAMILY_DOCTOR_VISIT: AllergyRelevance.LOW,
    DocumentType.PRESCRIPTION: AllergyRelevance.LOW,
    DocumentType.OTHER: AllergyRelevance.NOT_RELEVANT,
}

_SIGNALS_MAP = {
    DocumentType.ALLERGIST_VISIT: ["allergy evaluation", "skin test", "specialist referral"],
    DocumentType.DERMATOLOGIST_VISIT: ["urticaria", "skin rash", "dermatological reaction"],
    DocumentType.ER_VISIT: ["anaphylaxis", "emergency treatment", "epinephrine"],
    DocumentType.LAB_RESULT: ["elevated IgE", "eosinophilia"],
    DocumentType.FAMILY_DOCTOR_VISIT: ["allergic reaction reported", "allergy documented"],
}


def mock_classify_document(doc: MedicalDocument, reported_allergy: str) -> AnalyzedDocument:
    relevance = _RELEVANCE_MAP.get(doc.document_type, AllergyRelevance.NOT_RELEVANT)
    signals = _SIGNALS_MAP.get(doc.document_type, [])

    # Boost relevance if allergy drug name appears in content
    if reported_allergy.lower() in doc.content.lower() or any(
        word in doc.content.lower()
        for word in ["אלרגי", "allerg", "פריחה", "rash", "אנפילקס", "anaphyl"]
    ):
        if relevance == AllergyRelevance.LOW:
            relevance = AllergyRelevance.MEDIUM
        elif relevance == AllergyRelevance.NOT_RELEVANT:
            relevance = AllergyRelevance.LOW

    summary = f"[DEMO] {doc.document_type.value} on {doc.date} — {doc.source}"

    return AnalyzedDocument(
        document=doc,
        relevance=relevance,
        allergy_signals=signals,
        summary=summary,
        confidence=0.85,
    )


def mock_synthesize_report(
    patient_id: str,
    patient_name: str,
    reported_allergy: str,
    analyzed_docs: list[AnalyzedDocument],
    generated_at: str,
) -> AllergyReport:
    relevant = [
        d for d in analyzed_docs
        if d.relevance in (AllergyRelevance.HIGH, AllergyRelevance.MEDIUM)
    ]

    has_er = any(d.document.document_type == DocumentType.ER_VISIT for d in relevant)
    has_allergist = any(d.document.document_type == DocumentType.ALLERGIST_VISIT for d in relevant)

    if has_er and has_allergist:
        severity = AllergySeverity.CONFIRMED_SEVERE
        explanation = (
            f"Patient has documented ER visit and allergist confirmation for {reported_allergy}. "
            "Evidence strongly supports a confirmed severe allergy."
        )
        flags = [
            "Anaphylaxis event on record — verify EpiPen prescription",
            "Cross-reactivity risk — alert treating physicians",
        ]
    elif has_allergist:
        severity = AllergySeverity.CONFIRMED_MODERATE
        explanation = (
            f"Allergist documented allergy to {reported_allergy} with supporting evidence."
        )
        flags = ["Ensure alternative treatments are documented in record"]
    elif relevant:
        severity = AllergySeverity.PROBABLE
        explanation = (
            f"Indirect evidence of allergy to {reported_allergy} found in medical records, "
            "but no direct allergist confirmation."
        )
        flags = ["Recommend formal allergist evaluation to confirm label"]
    else:
        severity = AllergySeverity.INSUFFICIENT_DATA
        explanation = "No allergy-related evidence found in available documents."
        flags = ["Consider removing allergy label until confirmed"]

    allergist_visits = sum(1 for d in analyzed_docs if d.document.document_type == DocumentType.ALLERGIST_VISIT)
    derm_visits = sum(1 for d in analyzed_docs if d.document.document_type == DocumentType.DERMATOLOGIST_VISIT)
    er_events = sum(1 for d in analyzed_docs if d.document.document_type in (DocumentType.ER_VISIT, DocumentType.HOSPITALIZATION))

    timeline = [
        {"date": ad.document.date, "event": ad.summary, "doc_id": ad.document.doc_id}
        for ad in sorted(relevant, key=lambda x: x.document.date)
    ]

    return AllergyReport(
        patient_id=patient_id,
        patient_name=patient_name,
        reported_allergy=reported_allergy,
        generated_at=generated_at,
        severity=severity,
        severity_explanation=explanation,
        confirmed_conditions=[f"Drug allergy: {reported_allergy}"] if has_allergist else [],
        reported_symptoms=["rash", "urticaria", "anaphylaxis"] if has_er else ["rash", "itching"],
        relevant_document_ids=[d.document.doc_id for d in relevant],
        timeline=timeline,
        doctor_recommendation=(
            f"Review all {len(relevant)} relevant documents before prescribing. "
            "Consult allergist if alternative treatment is required."
        ),
        flags=flags,
        total_documents_reviewed=len(analyzed_docs),
        relevant_documents_count=len(relevant),
        allergist_visits=allergist_visits,
        dermatologist_visits=derm_visits,
        er_or_hospitalization_events=er_events,
    )


def mock_analyze_patient(
    patient_id: str,
    patient_name: str,
    reported_allergy: str,
    documents: list[MedicalDocument],
    generated_at: str,
) -> tuple[AllergyReport, list[AnalyzedDocument]]:
    analyzed = [mock_classify_document(doc, reported_allergy) for doc in documents]
    report = mock_synthesize_report(
        patient_id, patient_name, reported_allergy, analyzed, generated_at
    )
    return report, analyzed

"""
Parses incoming medical documents from various formats into MedicalDocument objects.
Supports: plain dict/JSON, FHIR Encounter/Observation resources, and free-text.
"""

from models.document import MedicalDocument, DocumentType

SPECIALTY_TO_TYPE: dict[str, DocumentType] = {
    "אלרגולוגיה": DocumentType.ALLERGIST_VISIT,
    "אלרגולוגיה ואימונולוגיה": DocumentType.ALLERGIST_VISIT,
    "allergist": DocumentType.ALLERGIST_VISIT,
    "עור ומין": DocumentType.DERMATOLOGIST_VISIT,
    "דרמטולוגיה": DocumentType.DERMATOLOGIST_VISIT,
    "dermatologist": DocumentType.DERMATOLOGIST_VISIT,
    "רפואת משפחה": DocumentType.FAMILY_DOCTOR_VISIT,
    "family_doctor": DocumentType.FAMILY_DOCTOR_VISIT,
    "רפואה דחופה": DocumentType.ER_VISIT,
    "er": DocumentType.ER_VISIT,
    "מעבדה": DocumentType.LAB_RESULT,
    "lab": DocumentType.LAB_RESULT,
}

SOURCE_TO_TYPE: dict[str, DocumentType] = {
    "allergist": DocumentType.ALLERGIST_VISIT,
    "dermatologist": DocumentType.DERMATOLOGIST_VISIT,
    "family_doctor": DocumentType.FAMILY_DOCTOR_VISIT,
    "er": DocumentType.ER_VISIT,
    "hospital": DocumentType.HOSPITALIZATION,
    "lab": DocumentType.LAB_RESULT,
    "prescription": DocumentType.PRESCRIPTION,
}


def _infer_type(source: str, specialty: str | None) -> DocumentType:
    if specialty:
        for key, doc_type in SPECIALTY_TO_TYPE.items():
            if key.lower() in specialty.lower():
                return doc_type
    if source:
        for key, doc_type in SOURCE_TO_TYPE.items():
            if key.lower() in source.lower():
                return doc_type
    return DocumentType.OTHER


def parse_plain_document(raw: dict) -> MedicalDocument:
    """Parse a plain dict document (our internal format / mock data)."""
    source = raw.get("source", "unknown")
    specialty = raw.get("specialty")
    doc_type = _infer_type(source, specialty)

    return MedicalDocument(
        doc_id=raw["doc_id"],
        date=raw["date"],
        source=source,
        doctor_name=raw.get("doctor_name"),
        specialty=specialty,
        content=raw.get("content", ""),
        document_type=doc_type,
        raw=raw,
    )


def parse_fhir_encounter(fhir: dict) -> MedicalDocument:
    """
    Parse an HL7 FHIR Encounter resource into a MedicalDocument.
    Extracts participant (doctor), period, serviceType, and text.
    """
    doc_id = fhir.get("id", "fhir-unknown")
    date = ""
    if "period" in fhir:
        date = fhir["period"].get("start", "")[:10]

    doctor_name = None
    for participant in fhir.get("participant", []):
        ref = participant.get("individual", {})
        if "display" in ref:
            doctor_name = ref["display"]
            break

    specialty = None
    service_type = fhir.get("serviceType", {})
    for coding in service_type.get("coding", []):
        specialty = coding.get("display")
        break

    content_parts = []
    reason_codes = fhir.get("reasonCode", [])
    for rc in reason_codes:
        for coding in rc.get("coding", []):
            content_parts.append(coding.get("display", ""))
    narrative = fhir.get("text", {}).get("div", "")
    if narrative:
        content_parts.append(narrative)
    content = " | ".join(filter(None, content_parts)) or "FHIR Encounter (no text)"

    source = fhir.get("class", {}).get("display", "hospital")
    doc_type = _infer_type(source, specialty)

    return MedicalDocument(
        doc_id=doc_id,
        date=date,
        source=source,
        doctor_name=doctor_name,
        specialty=specialty,
        content=content,
        document_type=doc_type,
        raw=fhir,
    )


def parse_fhir_observation(fhir: dict) -> MedicalDocument:
    """
    Parse an HL7 FHIR Observation resource (e.g. lab result).
    """
    doc_id = fhir.get("id", "fhir-obs-unknown")
    date = fhir.get("effectiveDateTime", "")[:10]

    code_display = ""
    for coding in fhir.get("code", {}).get("coding", []):
        code_display = coding.get("display", "")
        break

    value = ""
    if "valueQuantity" in fhir:
        vq = fhir["valueQuantity"]
        value = f"{vq.get('value', '')} {vq.get('unit', '')}"
    elif "valueString" in fhir:
        value = fhir["valueString"]

    content = f"{code_display}: {value}".strip(": ")
    if not content:
        content = "FHIR Observation (no text)"

    return MedicalDocument(
        doc_id=doc_id,
        date=date,
        source="lab",
        doctor_name=None,
        specialty="מעבדה",
        content=content,
        document_type=DocumentType.LAB_RESULT,
        raw=fhir,
    )


def parse_documents(raw_docs: list[dict]) -> list[MedicalDocument]:
    """
    Auto-detect format (FHIR or plain) and parse a list of documents.
    """
    result = []
    for raw in raw_docs:
        resource_type = raw.get("resourceType", "")
        if resource_type == "Encounter":
            result.append(parse_fhir_encounter(raw))
        elif resource_type == "Observation":
            result.append(parse_fhir_observation(raw))
        else:
            result.append(parse_plain_document(raw))
    return result

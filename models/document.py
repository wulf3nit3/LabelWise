from pydantic import BaseModel
from typing import Optional
from enum import Enum


class DocumentType(str, Enum):
    ALLERGIST_VISIT = "allergist_visit"
    DERMATOLOGIST_VISIT = "dermatologist_visit"
    FAMILY_DOCTOR_VISIT = "family_doctor_visit"
    HOSPITALIZATION = "hospitalization"
    LAB_RESULT = "lab_result"
    ER_VISIT = "er_visit"
    PRESCRIPTION = "prescription"
    OTHER = "other"


class AllergyRelevance(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NOT_RELEVANT = "not_relevant"


class MedicalDocument(BaseModel):
    doc_id: str
    date: str
    source: str  # e.g. "allergist", "family_doctor", "hospital"
    doctor_name: Optional[str] = None
    specialty: Optional[str] = None
    content: str  # free text or structured text
    document_type: DocumentType = DocumentType.OTHER
    raw: Optional[dict] = None  # original parsed data (FHIR, JSON, etc.)


class AnalyzedDocument(BaseModel):
    document: MedicalDocument
    relevance: AllergyRelevance
    allergy_signals: list[str]  # e.g. ["rash", "anaphylaxis", "IgE elevated"]
    summary: str
    confidence: float  # 0-1

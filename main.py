"""
Allergy Validator API
Hackathon: Meuhedet — Beyond The Label: Rethinking Drug Allergy Records

Endpoints:
  GET  /patients                          — list demo patients
  GET  /patients/{patient_id}             — get raw patient data
  POST /analyze                           — analyze documents and return JSON report
  POST /analyze/pdf                       — analyze and return PDF report
  GET  /analyze/demo/{patient_id}         — run full demo pipeline for a mock patient
  GET  /analyze/demo/{patient_id}/pdf     — run demo and return PDF
"""

import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, JSONResponse, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from mock_data.patients import get_patient, list_patients, MOCK_PATIENTS
from models.document import MedicalDocument
from processors.document_parser import parse_documents
from processors.report_generator import generate_pdf

_MOCK_MODE = os.environ.get("MOCK_MODE", "").lower() == "true" or not os.environ.get("ANTHROPIC_API_KEY")

if _MOCK_MODE:
    from processors.mock_analyzer import mock_analyze_patient as analyze_patient
    print("[MOCK MODE] No API key detected, using pre-built responses")
else:
    from processors.allergy_analyzer import analyze_patient

app = FastAPI(
    title="Allergy Validator",
    description=(
        "AI-powered tool that reviews patient medical records, "
        "identifies allergy-related evidence, and generates structured "
        "clinical reports to help physicians validate drug allergy labels."
    ),
    version="1.0.0",
)


# ── Request / Response schemas ─────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    patient_id: str
    patient_name: str
    reported_allergy: str
    documents: list[dict]  # raw dicts — can be plain JSON or FHIR resources


# ── Endpoints ─────────────────────────────────────────────────────────────────

_TEMPLATES_DIR = Path(__file__).parent / "templates"


@app.get("/ui", response_class=HTMLResponse)
def ui():
    """Web dashboard for demo."""
    html = (_TEMPLATES_DIR / "dashboard.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@app.get("/")
def root():
    return {
        "service": "Allergy Validator",
        "hackathon": "Meuhedet — Beyond The Label",
        "endpoints": [
            "GET  /patients",
            "GET  /patients/{patient_id}",
            "POST /analyze          → JSON report",
            "POST /analyze/pdf      → PDF report",
            "GET  /analyze/demo/{patient_id}      → JSON report (mock data)",
            "GET  /analyze/demo/{patient_id}/pdf  → PDF report (mock data)",
        ],
    }


@app.get("/patients")
def get_patients():
    """List all demo patients."""
    return list_patients()


@app.get("/patients/{patient_id}")
def get_patient_data(patient_id: str):
    """Return raw patient data (for inspection)."""
    patient = get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    return patient


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    """
    Analyze a set of medical documents for allergy evidence.
    Returns a structured JSON report.
    """
    documents = parse_documents(req.documents)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    report, analyzed_docs = analyze_patient(
        patient_id=req.patient_id,
        patient_name=req.patient_name,
        reported_allergy=req.reported_allergy,
        documents=documents,
        generated_at=generated_at,
    )
    return {
        "report": report.model_dump(),
        "analyzed_documents": [
            {
                "doc_id": ad.document.doc_id,
                "date": ad.document.date,
                "source": ad.document.source,
                "relevance": ad.relevance,
                "allergy_signals": ad.allergy_signals,
                "summary": ad.summary,
                "confidence": ad.confidence,
            }
            for ad in analyzed_docs
        ],
    }


@app.post("/analyze/pdf")
def analyze_pdf(req: AnalyzeRequest):
    """
    Analyze documents and return a PDF report (binary).
    """
    documents = parse_documents(req.documents)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    report, analyzed_docs = analyze_patient(
        patient_id=req.patient_id,
        patient_name=req.patient_name,
        reported_allergy=req.reported_allergy,
        documents=documents,
        generated_at=generated_at,
    )
    pdf_bytes = generate_pdf(report, analyzed_docs)

    filename = f"allergy_report_{req.patient_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/analyze/demo/{patient_id}")
def demo_analyze(patient_id: str):
    """Run the full analysis pipeline on mock patient data. Returns JSON."""
    patient = get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    documents = parse_documents(patient["documents"])
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    report, analyzed_docs = analyze_patient(
        patient_id=patient["patient_id"],
        patient_name=patient["patient_name"],
        reported_allergy=patient["reported_allergy"],
        documents=documents,
        generated_at=generated_at,
    )
    return {
        "report": report.model_dump(),
        "analyzed_documents": [
            {
                "doc_id": ad.document.doc_id,
                "date": ad.document.date,
                "source": ad.document.source,
                "relevance": ad.relevance,
                "allergy_signals": ad.allergy_signals,
                "summary": ad.summary,
                "confidence": ad.confidence,
            }
            for ad in analyzed_docs
        ],
    }


@app.get("/analyze/demo/{patient_id}/pdf")
def demo_analyze_pdf(patient_id: str):
    """Run the full analysis pipeline on mock patient data. Returns PDF."""
    patient = get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    documents = parse_documents(patient["documents"])
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    report, analyzed_docs = analyze_patient(
        patient_id=patient["patient_id"],
        patient_name=patient["patient_name"],
        reported_allergy=patient["reported_allergy"],
        documents=documents,
        generated_at=generated_at,
    )
    pdf_bytes = generate_pdf(report, analyzed_docs)

    filename = f"allergy_report_{patient_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

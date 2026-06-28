from pydantic import BaseModel
from typing import Optional
from enum import Enum


class AllergySeverity(str, Enum):
    CONFIRMED_SEVERE = "confirmed_severe"       # אנפילקסיס, אשפוז, מבחן עור חיובי
    CONFIRMED_MODERATE = "confirmed_moderate"   # תגובות חוזרות, ביקורי אלרגולוג
    PROBABLE = "probable"                        # סממנים עקיפים, ללא אישור ישיר
    QUESTIONABLE = "questionable"                # תלונה בודדת, ללא תיעוד תומך
    INSUFFICIENT_DATA = "insufficient_data"


class AllergyReport(BaseModel):
    patient_id: str
    patient_name: str
    reported_allergy: str  # מה שמדווח בתיק (e.g. "פניצילין")
    generated_at: str

    # ממצאים
    severity: AllergySeverity
    severity_explanation: str

    confirmed_conditions: list[str]       # מחלות/אבחנות מאושרות
    reported_symptoms: list[str]          # תסמינים שדווחו לאורך הזמן
    relevant_document_ids: list[str]      # מסמכים שנמצאו רלוונטיים
    timeline: list[dict]                  # ציר זמן של אירועים רלוונטיים

    # המלצה לרופא
    doctor_recommendation: str
    flags: list[str]                      # דגלים אדומים שדורשים תשומת לב

    # סטטיסטיקות
    total_documents_reviewed: int
    relevant_documents_count: int
    allergist_visits: int
    dermatologist_visits: int
    er_or_hospitalization_events: int

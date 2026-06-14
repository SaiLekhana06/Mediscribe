"""
schemas.py
Defines the shape of data for API requests and responses.
Think of these as contracts — the API promises to always
return data in exactly these shapes.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime


# ── Authentication ────────────────────────────────────────────
class UserRegister(BaseModel):
    email:     EmailStr
    password:  str
    full_name: str


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user_id:      int
    full_name:    str


# ── Audio Upload ──────────────────────────────────────────────
class AudioUploadResponse(BaseModel):
    conversation_id: int
    status:          str
    message:         str
    quality_score:   Optional[float]
    quality_warnings: Optional[list]


# ── SOAP Note ─────────────────────────────────────────────────
class SOAPContent(BaseModel):
    subjective: Optional[str]
    objective:  Optional[str]
    assessment: Optional[str]
    plan:       Optional[str]


class SOAPGenerateResponse(BaseModel):
    note_id:           int
    conversation_id:   int
    soap:              SOAPContent
    confidence_scores: Optional[Dict[str, Any]]
    confidence_labels: Optional[Dict[str, str]]
    status:            str


class SOAPEditRequest(BaseModel):
    subjective: Optional[str]
    objective:  Optional[str]
    assessment: Optional[str]
    plan:       Optional[str]


class SOAPApproveRequest(BaseModel):
    doctor_name: str


class SOAPApproveResponse(BaseModel):
    note_id:     int
    status:      str
    approved_at: datetime
    message:     str


# ── History ───────────────────────────────────────────────────
class NoteHistoryItem(BaseModel):
    note_id:         int
    conversation_id: int
    patient_code:    str
    status:          str
    created_at:      datetime
    approved_at:     Optional[datetime]

    class Config:
        from_attributes = True
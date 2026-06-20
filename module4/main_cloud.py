"""
Cloud-only version of MediScribe API.
No AI components. Handles auth, storage, CRUD only.
Audio processing happens on the demo machine locally.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from database import engine, Base
from routers import auth_router, soap_router

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MediScribe API",
    description="MediScribe — Storage and Auth Layer",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Only lightweight routers — no audio processing
app.include_router(auth_router.router)
app.include_router(soap_router.router)

# Add a direct SOAP submission endpoint
# This accepts a pre-processed transcript + SOAP note
# from the local pipeline and saves it
from fastapi import Depends
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
import models, schemas
from pydantic import BaseModel
from typing import Optional, Dict

class DirectSOAPSubmit(BaseModel):
    patient_code:        str
    transcript:          str
    anonymous_transcript: str
    soap:                Dict[str, str]
    confidence_scores:   Dict[str, float]
    confidence_labels:   Dict[str, str]

@app.post("/api/submit-soap")
def submit_soap_direct(
    data:         DirectSOAPSubmit,
    db:           Session     = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Accepts a fully processed SOAP note from the local pipeline.
    Saves it to the cloud database without running any AI.
    """
    conversation = models.Conversation(
        doctor_id=current_user.id,
        patient_code=data.patient_code,
        raw_transcript=data.transcript,
        anonymous_transcript=data.anonymous_transcript,
        status="generated"
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    soap_note = models.SOAPNote(
        conversation_id=conversation.id,
        subjective=data.soap.get("subjective", ""),
        objective=data.soap.get("objective", ""),
        assessment=data.soap.get("assessment", ""),
        plan=data.soap.get("plan", ""),
        confidence_scores=data.confidence_scores,
        confidence_labels=data.confidence_labels,
        status="pending_review"
    )
    db.add(soap_note)
    conversation.status = "generated"
    db.commit()
    db.refresh(soap_note)

    log = models.AuditLog(
        user_id=current_user.id,
        action="SOAP_SUBMITTED_LOCAL",
        resource_type="soap_note",
        resource_id=soap_note.id,
        details={"patient_code": data.patient_code}
    )
    db.add(log)
    db.commit()

    return {
        "conversation_id": conversation.id,
        "note_id": soap_note.id,
        "status": "success"
    }

@app.get("/")
def root():
    return {"message": "MediScribe API running", "mode": "cloud-storage-only"}

@app.get("/health")
def health():
    return {"status": "healthy"}
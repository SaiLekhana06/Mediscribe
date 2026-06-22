"""
Audio upload endpoint.
Receives audio file, runs full pipeline, saves to database.
"""

import os
import uuid
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
import models
import schemas
from pipeline import run_full_pipeline
from dotenv import load_dotenv

load_dotenv()

AUDIO_UPLOAD_DIR = os.getenv("AUDIO_UPLOAD_DIR", "./uploaded_audio")
os.makedirs(AUDIO_UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".ogg", ".m4a", ".mp4", ".webm"}

router = APIRouter(prefix="/api", tags=["Audio"])


@router.post("/upload-audio", response_model=schemas.AudioUploadResponse)
async def upload_audio(
    file:         UploadFile = File(...),
    patient_code: str        = Form(...),
    cloud_token:  str        = Form(default=""),
    db:           Session    = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Receives audio file and runs the full pipeline.
    
    Steps:
    1. Save audio file to disk temporarily
    2. Run Module 1 → Module 2 → Module 3
    3. Save results to database
    4. Delete audio file (privacy)
    5. Return conversation_id for frontend to use
    """
    
    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Allowed: {ALLOWED_EXTENSIONS}"
        )
    
    # Save file with a UUID name (not the original name — privacy)
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    audio_path = os.path.join(AUDIO_UPLOAD_DIR, unique_filename)
    
    try:
        # Save uploaded file to disk
        async with aiofiles.open(audio_path, "wb") as f:
            content = await file.read()
            await f.write(content)
        
        # Create conversation record in database
        conversation = models.Conversation(
            doctor_id=current_user.id,
            patient_code=patient_code,
            audio_filename=unique_filename,
            status="processing"
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        
        # Run the full pipeline
        result = run_full_pipeline(audio_path, patient_code,cloud_token=cloud_token)
        
        # Delete audio file immediately after processing
        # Audio never stays on disk longer than needed
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        if result["status"] == "error":
            conversation.status = "failed"
            db.commit()
            raise HTTPException(status_code=500, detail=result["error"])
        
        quality = result.get("quality", {})
        
        if result["status"] == "quality_error":
            conversation.status = "quality_failed"
            conversation.quality_score = quality.get("quality_score", 0)
            conversation.quality_warnings = quality.get("warnings", [])
            db.commit()
            
            return schemas.AudioUploadResponse(
                conversation_id=conversation.id,
                status="quality_error",
                message=quality.get("recommendation", "Audio quality too low"),
                quality_score=quality.get("quality_score"),
                quality_warnings=quality.get("warnings", [])
            )
        
        # Save transcripts and quality info
        conversation.raw_transcript       = result["transcript"]
        conversation.anonymous_transcript = result["anonymous_transcript"]
        conversation.quality_score        = quality.get("quality_score", 100)
        conversation.quality_warnings     = quality.get("warnings", [])
        conversation.status               = "transcribed"
        db.commit()
        
        # Save SOAP note as draft
        soap_note = models.SOAPNote(
            conversation_id=conversation.id,
            subjective=result["soap"].get("subjective", ""),
            objective=result["soap"].get("objective", ""),
            assessment=result["soap"].get("assessment", ""),
            plan=result["soap"].get("plan", ""),
            confidence_scores=result["confidence_scores"],
            confidence_labels=result["confidence_labels"],
            status="pending_review"
        )
        db.add(soap_note)
        conversation.status = "generated"
        db.commit()
        db.refresh(soap_note)
        
        # Audit log
        log = models.AuditLog(
            user_id=current_user.id,
            action="SOAP_GENERATED",
            resource_type="soap_note",
            resource_id=soap_note.id,
            details={
                "patient_code":  patient_code,
                "pii_found":     result["pii_found"],
                "quality_score": quality.get("quality_score", 100)
            }
        )
        db.add(log)
        db.commit()
        
        return schemas.AudioUploadResponse(
            conversation_id=conversation.id,
            status="success",
            message="SOAP note generated successfully",
            quality_score=quality.get("quality_score", 100),
            quality_warnings=quality.get("warnings", [])
        )
    
    except HTTPException:
        raise
    except Exception as e:
        # Clean up audio file if something went wrong
        if os.path.exists(audio_path):
            os.remove(audio_path)
        raise HTTPException(status_code=500, detail=str(e))

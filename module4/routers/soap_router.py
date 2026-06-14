"""
SOAP note endpoints — retrieve, edit, approve.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
import models
import schemas

router = APIRouter(prefix="/api/notes", tags=["SOAP Notes"])


@router.get("/{conversation_id}", response_model=schemas.SOAPGenerateResponse)
def get_soap_note(
    conversation_id: int,
    db:              Session     = Depends(get_db),
    current_user:    models.User = Depends(get_current_user)
):
    """
    Retrieves the SOAP note for a conversation.
    Frontend calls this to display the note in the editor.
    """
    
    conversation = db.query(models.Conversation).filter(
        models.Conversation.id        == conversation_id,
        models.Conversation.doctor_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    note = db.query(models.SOAPNote).filter(
        models.SOAPNote.conversation_id == conversation_id
    ).first()
    
    if not note:
        raise HTTPException(status_code=404, detail="SOAP note not found")
    
    return schemas.SOAPGenerateResponse(
        note_id=note.id,
        conversation_id=conversation_id,
        soap=schemas.SOAPContent(
            subjective=note.subjective,
            objective=note.objective,
            assessment=note.assessment,
            plan=note.plan
        ),
        confidence_scores=note.confidence_scores,
        confidence_labels=note.confidence_labels,
        status=note.status
    )


@router.put("/{note_id}")
def edit_soap_note(
    note_id:      int,
    edits:        schemas.SOAPEditRequest,
    db:           Session     = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Updates one or more SOAP sections.
    Called every time the doctor edits any field.
    """
    
    note = db.query(models.SOAPNote).filter(
        models.SOAPNote.id == note_id
    ).first()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Only update fields that were provided
    if edits.subjective is not None:
        note.subjective = edits.subjective
    if edits.objective is not None:
        note.objective = edits.objective
    if edits.assessment is not None:
        note.assessment = edits.assessment
    if edits.plan is not None:
        note.plan = edits.plan
    
    db.commit()
    
    # Audit log every edit
    log = models.AuditLog(
        user_id=current_user.id,
        action="NOTE_EDITED",
        resource_type="soap_note",
        resource_id=note_id,
        details={"fields_edited": [
            k for k, v in edits.dict().items() if v is not None
        ]}
    )
    db.add(log)
    db.commit()
    
    return {"status": "updated", "note_id": note_id}


@router.post("/{note_id}/approve",
             response_model=schemas.SOAPApproveResponse)
def approve_soap_note(
    note_id:      int,
    approval:     schemas.SOAPApproveRequest,
    db:           Session     = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Doctor gives final approval to the SOAP note.
    This is the human-in-the-loop gate.
    Nothing becomes permanent until this is called.
    """
    
    note = db.query(models.SOAPNote).filter(
        models.SOAPNote.id == note_id
    ).first()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if note.status == "approved":
        raise HTTPException(
            status_code=400,
            detail="Note is already approved"
        )
    
    note.status      = "approved"
    note.approved_at = datetime.utcnow()
    note.approved_by = current_user.id
    db.commit()
    
    # Audit log
    log = models.AuditLog(
        user_id=current_user.id,
        action="NOTE_APPROVED",
        resource_type="soap_note",
        resource_id=note_id,
        details={"doctor_name": approval.doctor_name}
    )
    db.add(log)
    db.commit()
    
    return schemas.SOAPApproveResponse(
        note_id=note_id,
        status="approved",
        approved_at=note.approved_at,
        message="SOAP note approved and saved permanently"
    )


@router.get("/history/{doctor_id}")
def get_history(
    doctor_id:    int,
    db:           Session     = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Returns all conversations for a doctor.
    Used to populate the history screen in the frontend.
    """
    
    conversations = db.query(models.Conversation).filter(
        models.Conversation.doctor_id == current_user.id
    ).order_by(models.Conversation.created_at.desc()).all()
    
    history = []
    for conv in conversations:
        note = db.query(models.SOAPNote).filter(
            models.SOAPNote.conversation_id == conv.id
        ).first()
        
        history.append({
            "conversation_id": conv.id,
            "patient_code":    conv.patient_code,
            "status":          note.status if note else conv.status,
            "created_at":      conv.created_at,
            "approved_at":     note.approved_at if note else None
        })
    
    return {"history": history, "total": len(history)}
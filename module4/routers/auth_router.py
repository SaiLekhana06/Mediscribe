"""
Auth endpoints — register and login.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=schemas.TokenResponse)
def register(user_data: schemas.UserRegister, db: Session = Depends(get_db)):
    """
    Creates a new doctor account.
    Returns a JWT token immediately so they are logged in.
    """
    
    # Check if email already exists
    existing = db.query(models.User).filter(
        models.User.email == user_data.email
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    new_user = models.User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        role="doctor"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create audit log entry
    log = models.AuditLog(
        user_id=new_user.id,
        action="USER_REGISTERED",
        resource_type="user",
        resource_id=new_user.id,
        details={"email": user_data.email}
    )
    db.add(log)
    db.commit()
    
    token = create_access_token(new_user.id, new_user.email)
    
    return schemas.TokenResponse(
        access_token=token,
        user_id=new_user.id,
        full_name=new_user.full_name
    )


@router.post("/login", response_model=schemas.TokenResponse)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    """
    Logs in an existing doctor.
    Returns a JWT token valid for 8 hours.
    """
    
    user = db.query(models.User).filter(
        models.User.email == credentials.email
    ).first()
    
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )
    
    # Audit log
    log = models.AuditLog(
        user_id=user.id,
        action="USER_LOGIN",
        resource_type="user",
        resource_id=user.id
    )
    db.add(log)
    db.commit()
    
    token = create_access_token(user.id, user.email)
    
    return schemas.TokenResponse(
        access_token=token,
        user_id=user.id,
        full_name=user.full_name
    )
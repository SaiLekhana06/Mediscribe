"""
auth.py
Handles all authentication logic.
Password hashing and JWT token creation/verification.
"""

import os
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
import models

# Load settings
JWT_SECRET_KEY     = os.getenv("JWT_SECRET_KEY", "fallback_secret_change_this")
JWT_ALGORITHM      = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

# Password hashing setup
# bcrypt is industry standard for password hashing
# It is deliberately slow to make brute force attacks impractical
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTPBearer extracts the JWT token from the Authorization header
security = HTTPBearer()


def hash_password(plain_password: str) -> str:
    """Converts plain text password to secure hash."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Checks if a plain password matches a stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: int, email: str) -> str:
    """
    Creates a JWT token for a logged-in user.
    
    The token contains the user's ID and email
    and expires after JWT_EXPIRE_MINUTES.
    """
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub":   str(user_id),
        "email": email,
        "exp":   expire
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> models.User:
    """
    FastAPI dependency — verifies JWT token on every protected route.
    
    When you add this as a dependency to a route, FastAPI automatically:
    1. Extracts the token from the Authorization header
    2. Verifies it is valid and not expired
    3. Loads the user from the database
    4. Injects the user object into your route function
    
    If the token is invalid it automatically returns 401 Unauthorized.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"}
    )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = int(payload.get("sub"))
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception
    
    return user
"""
database.py
Sets up the connection between FastAPI and PostgreSQL.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# create_engine creates the actual connection to PostgreSQL
# pool_pre_ping=True means it tests the connection before using it
# This prevents errors if the database was temporarily disconnected
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

# SessionLocal is a factory for creating database sessions
# A session is like opening a conversation with the database
# You open it, do your operations, then close it
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base is the parent class all database table models will inherit from
Base = declarative_base()


def get_db():
    """
    Creates a database session for each API request.
    Automatically closes it when the request is done.
    
    This is used as a FastAPI dependency — FastAPI automatically
    calls this function and injects the session into your routes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
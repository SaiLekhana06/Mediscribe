"""
main.py
The FastAPI application entry point.
This is the file you run to start the server.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from database import engine, Base
from pipeline import initialize_all_components
from routers import auth_router, audio_router, soap_router

load_dotenv()

# Create all database tables
# This is safe to run multiple times — it only creates
# tables that do not exist yet
Base.metadata.create_all(bind=engine)

# Create the FastAPI app
app = FastAPI(
    title="MediScribe API",
    description="AI Medical Scribe — Privacy-First SOAP Note Generation",
    version="1.0.0"
)

# CORS middleware
# This allows your React/Streamlit frontend to call this API
# Without this, browsers block cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # in production, list specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Register all routers
app.include_router(auth_router.router)
app.include_router(audio_router.router)
app.include_router(soap_router.router)


@app.on_event("startup")
async def startup_event():
    """
    Runs once when the server starts.
    Loads all AI models into memory so they are ready
    for the first request without delay.
    """
    print("MediScribe API starting up...")
    initialize_all_components()
    print("MediScribe API ready.")


@app.get("/")
def root():
    return {
        "message": "MediScribe API is running",
        "docs":    "Visit /docs for API documentation",
        "version": "1.0.0"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
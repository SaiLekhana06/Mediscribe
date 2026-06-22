"""
pipeline.py
Connects Module 1, Module 2, and Module 3 into one pipeline.

This file imports functions from the other modules and
runs them in sequence whenever audio is uploaded.

IMPORTANT: Update the paths below to match where your
module files actually are on your computer.
"""

import sys
import os
from dotenv import load_dotenv
import requests 

load_dotenv()

from audio_pipeline import (
    process_audio as m1_process,
    load_whisper_model,
)

from anonymizer import (
    process_transcript as m2_process,
    create_engines,
)

from soap_generator import (
    process_transcript as m3_process,
    load_components,
)

# Global component storage
# These are loaded once when the server starts
# Loading them on every request would be too slow
_whisper_model = None
_presidio_engines = None
_ai_components = None

def initialize_all_components():
    """
    Loads all AI components once at server startup.
    Call this when FastAPI starts up.
    """
    global _whisper_model, _presidio_engines, _ai_components
    
    print("Initializing Module 1 — Whisper...")
    _whisper_model = load_whisper_model("base")
    
    print("Initializing Module 2 — Presidio...")
    _presidio_engines = create_engines()
    
    print("Initializing Module 3 — Gemini + ChromaDB...")
    _ai_components = load_components()
    
    print("All components ready.")


def run_full_pipeline(audio_path: str, patient_code: str, cloud_token: str = ""):
    """
    Runs the complete MediScribe pipeline for one consultation.
    
    audio_path:   path to the uploaded audio file
    patient_code: anonymous identifier for the patient
    
    Returns:
    {
        "status":               "success" or "error",
        "transcript":           "Doctor: ...\nPatient: ...",
        "anonymous_transcript": "Doctor: [PERSON_1]...",
        "pii_mapping":          {"[PERSON_1]": "Rajesh", ...},
        "pii_found":            True/False,
        "quality":              {...quality check results...},
        "soap":                 {subjective, objective, assessment, plan},
        "confidence_scores":    {subjective: 0.92, ...},
        "confidence_labels":    {subjective: "HIGH", ...},
        "error":                "error message if failed"
    }
    """
    
    try:
        # ── STEP 1: Audio → Transcript (Module 1) ────────────
        print(f"Pipeline: Processing audio {audio_path}")
        m1_result = m1_process(
            audio_path,
            model=_whisper_model,
            pause_threshold=0.2
        )
        
        if m1_result["status"] == "error":
            return {
                "status": "error",
                "error":  f"Transcription failed: {m1_result['error']}"
            }
        
        # Check audio quality
        quality = m1_result.get("quality", {})
        if quality and not quality.get("is_acceptable", True):
            return {
                "status":          "quality_error",
                "error":           "Audio quality too low",
                "quality":         quality,
                "transcript":      m1_result["transcript"],
            }
        
        transcript = m1_result["transcript"]
        print(f"Pipeline: Transcription complete. "
              f"{len(m1_result['segments'])} speaker turns.")
        
        # ── STEP 2: Transcript → Anonymous (Module 2) ────────
        analyzer, anonymizer_engine = _presidio_engines
        m2_result = m2_process(transcript, analyzer, anonymizer_engine)
        
        if m2_result["status"] == "error":
            return {
                "status": "error",
                "error":  f"Anonymization failed: {m2_result['error']}",
                "transcript": transcript
            }
        
        anonymous_transcript = m2_result["anonymous_transcript"]
        pii_mapping = m2_result["pii_mapping"]
        print(f"Pipeline: Anonymization complete. "
              f"PII found: {m2_result['pii_found']}")
        
        # ── STEP 3: Anonymous → SOAP (Module 3) ──────────────
        m3_result = m3_process(anonymous_transcript, _ai_components)
        
        if m3_result["status"] == "error":
            return {
                "status": "error",
                "error":  f"SOAP generation failed: {m3_result['error']}",
                "transcript": transcript,
                "anonymous_transcript": anonymous_transcript
            }
        
        print("Pipeline: SOAP generation complete.")
        
       # ── STEP 4: Build result ─────────────────────────
        result = {
            "status":               "success",
            "transcript":           transcript,
            "anonymous_transcript": anonymous_transcript,
            "pii_mapping":          pii_mapping,
            "pii_found":            m2_result["pii_found"],
            "quality":              quality,
            "soap":                 m3_result["soap"],
            "confidence_scores":    m3_result["confidence_scores"],
            "confidence_labels":    m3_result["confidence_labels"],
        }

try:
    cloud_url = os.getenv("CLOUD_API_URL", "")

    # Use token passed from Streamlit, otherwise fall back to .env
    token_to_use = cloud_token or os.getenv("CLOUD_API_TOKEN", "")

    if cloud_url and token_to_use:
        headers = {"Authorization": f"Bearer {token_to_use}"}

        payload = {
            "patient_code": patient_code,
            "transcript": result["transcript"],
            "anonymous_transcript": result["anonymous_transcript"],
            "soap": result["soap"],
            "confidence_scores": result["confidence_scores"],
            "confidence_labels": result["confidence_labels"],
        }

        cloud_resp = requests.post(
            f"{cloud_url}/api/submit-soap",
            json=payload,
            headers=headers,
            timeout=30,
        )

        if cloud_resp.status_code == 200:
            cloud_data = cloud_resp.json()
            result["conversation_id"] = cloud_data["conversation_id"]
            result["note_id"] = cloud_data["note_id"]
            print("Pipeline: Submitted to cloud successfully")

        elif cloud_resp.status_code == 401:
            print("Pipeline: Cloud token expired or invalid — note saved locally only")

        else:
            print(f"Pipeline: Cloud submission failed — {cloud_resp.status_code}")

    else:
        print("Pipeline: No cloud URL configured — skipping cloud submission")

except Exception as e:
    print(f"Pipeline: Cloud submission error — {str(e)}")
    # Never fail the whole pipeline because of cloud submission
    # Don't fail the whole pipeline if cloud submission fails

        return result
    
    except Exception as e:
        return {
            "status": "error",
            "error":  f"Pipeline error: {str(e)}"
        }


def submit_to_cloud(pipeline_result, patient_code, token, cloud_api_url):
    """
    After local pipeline finishes, send the SOAP note to cloud for storage.
    """
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "patient_code":          patient_code,
        "transcript":            pipeline_result["transcript"],
        "anonymous_transcript":  pipeline_result["anonymous_transcript"],
        "soap":                  pipeline_result["soap"],
        "confidence_scores":     pipeline_result["confidence_scores"],
        "confidence_labels":     pipeline_result["confidence_labels"]
    }
    resp = requests.post(
        f"{cloud_api_url}/api/submit-soap",
        json=payload,
        headers=headers,
        timeout=30
    )
    return resp.json()

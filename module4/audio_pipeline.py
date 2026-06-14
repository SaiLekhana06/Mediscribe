"""
Module 1 — Audio Pipeline
MediScribe Project

This module handles everything from audio file to labeled transcript.

Input:  Path to an audio file (WAV, MP3, M4A, MP4)
Output: Dictionary containing full transcript and labeled speaker turns
"""

import whisper
import os


def load_whisper_model(model_size="base"):
    """
    Loads the Whisper model into memory.
    
    We load it once and reuse it because loading takes a few seconds.
    Loading it every time you transcribe would be slow.
    
    model_size options: tiny, base, small, medium, large
    """
    print(f"Loading Whisper {model_size} model...")
    model = whisper.load_model(model_size)
    print("Model ready.")
    return model


def transcribe_audio(model, audio_path):
    """
    Takes an audio file and converts it to text using Whisper.
    
    audio_path: the full path to the audio file on your computer
    
    Returns the raw Whisper result dictionary.
    """
    
    # Check the file actually exists before trying to transcribe
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    print(f"Transcribing: {audio_path}")
    print("This may take a moment...")
    
    # fp16=False means use regular precision math
    # On most laptops without a GPU you need this set to False
    # Otherwise you get a warning and it falls back anyway
    result = model.transcribe(
        audio_path,
        fp16=False,
        language="en"
    )
    
    print("Transcription complete.")
    return result


def label_speakers(segments, pause_threshold=1.5):
    """
    Assigns Doctor or Patient labels to transcript segments.
    
    Strategy: Medical consultations follow Doctor-Patient-Doctor-Patient
    alternating pattern. We detect speaker switches by looking for 
    pauses longer than pause_threshold seconds.
    
    segments: list of Whisper segments (each has start, end, text)
    pause_threshold: seconds of silence before we assume speaker changed
    
    Returns: list of labeled turns like
    [
        {"speaker": "Doctor", "text": "Good morning, how are you?", "start": 0.0},
        {"speaker": "Patient", "text": "I have chest pain.", "start": 3.5},
        ...
    ]
    """
    
    if not segments:
        return []
    
    labeled_turns = []
    current_speaker = "Doctor"
    current_text = segments[0]["text"].strip()
    current_start = segments[0]["start"]
    
    for i in range(1, len(segments)):
        previous_end = segments[i - 1]["end"]
        next_start = segments[i]["start"]
        pause = next_start - previous_end
        
        if pause > pause_threshold:
            # Speaker changed — save the current turn
            labeled_turns.append({
                "speaker": current_speaker,
                "text": current_text,
                "start": current_start
            })
            # Flip speaker
            current_speaker = "Patient" if current_speaker == "Doctor" else "Doctor"
            # Start fresh for new speaker
            current_text = segments[i]["text"].strip()
            current_start = segments[i]["start"]
        else:
            # Same speaker — keep adding to current turn
            current_text += " " + segments[i]["text"].strip()
    
    # Save the very last turn (loop ends before saving it)
    labeled_turns.append({
        "speaker": current_speaker,
        "text": current_text,
        "start": current_start
    })
    
    return labeled_turns


def clean_transcript(labeled_turns):
    """
    Takes labeled turns and creates two things:
    
    1. A clean readable transcript string that looks like:
       Doctor: Good morning, what brings you in?
       Patient: I have been having chest pain.
       
    2. The same data but as a structured list for the AI pipeline
    """
    
    # Build the readable string version
    transcript_lines = []
    for turn in labeled_turns:
        line = f"{turn['speaker']}: {turn['text']}"
        transcript_lines.append(line)
    
    full_transcript = "\n".join(transcript_lines)
    
    return full_transcript 

def validate_transcript_quality(transcript, segments):
    """
    Automatically checks if the transcript is good enough
    to proceed through the pipeline.
    
    This runs silently — no human involvement.
    If quality is too low it returns a warning so the
    frontend can ask the doctor to re-upload better audio.
    
    Returns:
    {
        "is_acceptable": True or False,
        "quality_score": 0 to 100,
        "warnings": ["list of issues found"],
        "recommendation": "what to do"
    }
    """
    
    warnings = []
    quality_score = 100
    
    # Check 1: Is the transcript completely empty?
    if not transcript or len(transcript.strip()) == 0:
        return {
            "is_acceptable": False,
            "quality_score": 0,
            "warnings": ["Transcript is empty — no speech detected"],
            "recommendation": "Please check your audio file and re-upload"
        }
    
    # Check 2: Is it too short to be a real consultation?
    # A real consultation should have at least 20 words
    word_count = len(transcript.split())
    if word_count < 20:
        warnings.append(
            f"Transcript is very short ({word_count} words) — "
            f"may be incomplete"
        )
        quality_score -= 30
    
    # Check 3: Were at least 2 speakers detected?
    # A consultation needs a doctor AND a patient
    speakers_found = set()
    for segment in segments:
        speakers_found.add(segment["speaker"])
    
    if len(speakers_found) < 2:
        warnings.append(
            "Only one speaker detected — "
            "could not identify both Doctor and Patient"
        )
        quality_score -= 40
    
    # Check 4: Does it contain any medical-sounding content?
    # Very basic check — does it mention symptoms, body parts, or
    # common medical words? If not it might be wrong audio entirely.
    medical_keywords = [
        "pain", "fever", "cough", "breathe", "breath", "hurt",
        "ache", "symptom", "medication", "medicine", "doctor",
        "patient", "chest", "head", "stomach", "nausea", "dizzy",
        "vomit", "bleed", "swelling", "pressure", "heart", "blood",
        "treatment", "diagnosis", "weeks", "days", "months"
    ]
    
    transcript_lower = transcript.lower()
    medical_words_found = [
        word for word in medical_keywords 
        if word in transcript_lower
    ]
    
    if len(medical_words_found) == 0:
        warnings.append(
            "No medical terminology detected — "
            "this may not be a medical consultation audio"
        )
        quality_score -= 25
    
    # Check 5: Is it mostly gibberish?
    # Whisper sometimes hallucinates repeated phrases when audio is unclear
    words = transcript.lower().split()
    if len(words) > 10:
        unique_words = set(words)
        repetition_ratio = len(unique_words) / len(words)
        if repetition_ratio < 0.3:
            # Less than 30% unique words means heavy repetition
            warnings.append(
                "High repetition detected in transcript — "
                "audio quality may be poor"
            )
            quality_score -= 30
    
    # Final quality score cannot go below 0
    quality_score = max(0, quality_score)
    
    # Decide if acceptable
    # Score below 40 means too many problems — reject
    is_acceptable = quality_score >= 40
    
    if is_acceptable and len(warnings) == 0:
        recommendation = "Transcript looks good — proceeding"
    elif is_acceptable and len(warnings) > 0:
        recommendation = (
            "Transcript has minor issues but is acceptable — "
            "doctor should review carefully"
        )
    else:
        recommendation = (
            "Transcript quality is too low to proceed — "
            "please re-upload with clearer audio"
        )
    
    return {
        "is_acceptable": is_acceptable,
        "quality_score": quality_score,
        "warnings": warnings,
        "recommendation": recommendation
    }


def process_audio(audio_path,model=None,model_size="base",pause_threshold=1.5):
    """
    MAIN FUNCTION — this is what Module 4 will call.
    
    Takes an audio file path.
    Returns a dictionary with everything Module 2 needs.
    
    audio_path: path to the audio file
    model: pre-loaded Whisper model (pass this if you have already loaded it
           to avoid reloading every time)
    model_size: which Whisper model to use if loading fresh
    
    Returns:
    {
        "transcript": "Doctor: Good morning...\nPatient: I have chest pain...",
        "segments": [
            {"speaker": "Doctor", "text": "Good morning...", "start": 0.0},
            {"speaker": "Patient", "text": "I have chest pain...", "start": 3.5}
        ],
        "raw_text": "Good morning what brings you in I have chest pain...",
        "audio_path": "/path/to/audio.wav",
        "status": "success"
    }
    """
    
    try:
        # Load model if not provided
        if model is None:
            model = load_whisper_model(model_size)
        
        # Step 1: Transcribe
        whisper_result = transcribe_audio(model, audio_path)

        print("\nSEGMENTS:")
        for seg in whisper_result["segments"]:
            print(
                f"[{seg['start']:.2f} - {seg['end']:.2f}] "
                f"{seg['text']}"
            )
        
        # Step 2: Label speakers
        labeled_turns = label_speakers(whisper_result["segments"],pause_threshold=pause_threshold)
        
        # Step 3: Build clean transcript
        full_transcript = clean_transcript(labeled_turns)

        
        
        # Automatically validate quality
        quality_check = validate_transcript_quality(
            full_transcript, 
            labeled_turns
        )
        
        return {
            "transcript": full_transcript,
            "segments": labeled_turns,
            "raw_text": whisper_result["text"],
            "audio_path": audio_path,
            "status": "success",
            # Add quality information to the output
            "quality": quality_check
        }
        
        
    
    except FileNotFoundError as e:
        return {
            "transcript": "",
            "segments": [],
            "raw_text": "",
            "audio_path": audio_path,
            "status": "error",
            "error": str(e)
        }
    
    except Exception as e:
        return {
            "transcript": "",
            "segments": [],
            "raw_text": "",
            "audio_path": audio_path,
            "status": "error",
            "error": f"Unexpected error: {str(e)}"
        }


# This block only runs when you execute this file directly
# It does NOT run when Module 4 imports this file
# This is your built-in test
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python audio_pipeline.py path/to/audio.wav [pause_threshold]")
        print("Example: python audio_pipeline.py test.wav 0.3")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    
    # Optional second argument for threshold
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
    
    model = load_whisper_model("base")
    result = process_audio(audio_file, model=model, pause_threshold=threshold)
    
    if result["status"] == "success":
        print("\n" + "="*50)
        print("TRANSCRIPT")
        print("="*50)
        print(result["transcript"])
        print("\n" + "="*50)
        print(f"Total speaker turns detected: {len(result['segments'])}")
        for i, turn in enumerate(result["segments"]):
            print(f"  Turn {i+1}: {turn['speaker']} — {turn['text'][:60]}...")
    else:
        print(f"\nError: {result['error']}")
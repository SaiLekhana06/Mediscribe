"""
Module 2 — PII Anonymizer and Re-identifier
MediScribe Project
"""

import re
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine


# PII types we actually care about in medical context
# Removed DATE_TIME from this list — we handle it separately
# because Presidio is too aggressive with it
PII_ENTITIES = [
    "PERSON",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "LOCATION",
    "URL",
    "IP_ADDRESS",
    "IN_PAN",
    "IN_AADHAAR",
    "MEDICAL_LICENSE",
]

# Words that Presidio wrongly flags as DATE_TIME
# These are common English words that are NOT PII
DATE_TIME_FALSE_POSITIVES = {
    "morning", "afternoon", "evening", "night", "today",
    "yesterday", "tomorrow", "now", "then", "soon",
    "later", "earlier", "recently", "currently", "previously",
    "always", "never", "sometimes", "often", "weekly",
    "daily", "monthly", "annually", "correct", "right",
    "last", "next", "this", "that", "these", "those"
}

# Medical facility keywords to catch with our own regex
# because Presidio misses these
HOSPITAL_PATTERN = re.compile(
    r'\b(?:Apollo|AIIMS|Fortis|Manipal|Max|Medanta|Narayana|'
    r'Lilavati|Breach Candy|KEM|Sir Ganga Ram|NIMHANS|'
    r'CMC Vellore|Christian Medical|Ruby Hall|Wockhardt|'
    r'Columbia Asia|Global|Care|City|General|Memorial|'
    r'District|Government|Govt|Municipal|Trust|Mission)'
    r'(?:\s+(?:Hospital|Clinic|Medical|Healthcare|Health|'
    r'Centre|Center|Care|Institute|College))*\b',
    re.IGNORECASE
)

# Age pattern — Presidio misses "45 years old" sometimes
AGE_PATTERN = re.compile(
    r'\b(\d{1,3})\s*(?:years?|yrs?)?\s*(?:old|of age)\b',
    re.IGNORECASE
)

# Indian phone numbers — extra pattern beyond Presidio
PHONE_PATTERN = re.compile(
    r'(?<!\d)(?:\+91[\s\-]?)?[6-9]\d{9}(?!\d)'
)


def create_engines():
    """
    Creates Presidio analyzer and anonymizer engines.
    Load once and reuse.
    """
    print("Initializing Presidio engines...")
    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()
    print("Presidio ready.")
    return analyzer, anonymizer


def get_custom_detections(text):
    """
    Our own regex-based PII detection to catch things
    Presidio misses — hospital names, ages, Indian phones.
    
    Returns list of (start, end, entity_type, value) tuples.
    """
    custom_hits = []
    
    # Find hospital names
    for match in HOSPITAL_PATTERN.finditer(text):
        custom_hits.append((
            match.start(),
            match.end(),
            "LOCATION",
            match.group()
        ))
    
    # Find ages like "45 years old"
    for match in AGE_PATTERN.finditer(text):
        custom_hits.append((
            match.start(),
            match.end(),
            "AGE",
            match.group()
        ))
    
    # Find Indian phone numbers
    for match in PHONE_PATTERN.finditer(text):
        custom_hits.append((
            match.start(),
            match.end(),
            "PHONE_NUMBER",
            match.group()
        ))
    
    return custom_hits


def should_keep_datetime(text_value):
    """
    Decides whether a DATE_TIME detection is real PII
    or just a common word like "morning" or "today".
    
    Returns True if we should KEEP the anonymization (it is real PII).
    Returns False if we should SKIP it (it is a false positive).
    """
    cleaned = text_value.strip().lower()
    
    # Skip single common words
    if cleaned in DATE_TIME_FALSE_POSITIVES:
        return False
    
    # Skip very short detections (1-2 chars) — always false positives
    if len(cleaned) <= 2:
        return False
    
    # Keep specific dates — things that contain numbers or month names
    month_names = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
        "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep",
        "oct", "nov", "dec"
    ]
    
    # If it contains a number it is probably a real date
    if any(char.isdigit() for char in cleaned):
        return True
    
    # If it contains a month name it is a real date
    if any(month in cleaned for month in month_names):
        return True
    
    # Multi-word phrases that contain time words are real PII
    # e.g. "Monday the 12th", "last Tuesday"
    day_names = [
        "monday", "tuesday", "wednesday", "thursday",
        "friday", "saturday", "sunday"
    ]
    if any(day in cleaned for day in day_names):
        return True
    
    # "last year", "last month" — keep these
    if "last" in cleaned and len(cleaned) > 4:
        return True
    
    # Otherwise skip — too risky of being a false positive
    return False


def anonymize(transcript, analyzer, anonymizer):
    """
    Removes all PII from transcript.
    
    Returns:
    {
        "anonymous_transcript": cleaned text,
        "pii_mapping": {placeholder: real_value},
        "pii_found": bool
    }
    """
    
    # ── Step 1: Run Presidio detection ───────────────────────
    presidio_results = analyzer.analyze(
        text=transcript,
        entities=PII_ENTITIES,
        language="en"
    )
    
    # ── Step 2: Run DATE_TIME separately with filter ──────────
    datetime_results = analyzer.analyze(
        text=transcript,
        entities=["DATE_TIME"],
        language="en"
    )
    
    # Filter out false positives from DATE_TIME results
    
    # Filter out false positives from DATE_TIME results
    filtered_datetime = []

    for result in datetime_results:
        detected_text = transcript[result.start:result.end]

    # Don't allow ages to become DATE_TIME
        if AGE_PATTERN.fullmatch(detected_text.strip()):
            continue

        if should_keep_datetime(detected_text):
            filtered_datetime.append(result)
    
    # Combine all Presidio results
    all_presidio = list(presidio_results) + filtered_datetime
    
    # ── Step 3: Add custom regex detections ──────────────────
    custom_hits = get_custom_detections(transcript)
    
    # ── Step 4: Build unified list and remove overlaps ────────
    # Convert custom hits to same format for easier processing
    all_detections = []
    
    for result in all_presidio:
        all_detections.append({
            "start": result.start,
            "end": result.end,
            "entity_type": result.entity_type,
            "value": transcript[result.start:result.end],
            "score": result.score
        })
    
    for start, end, entity_type, value in custom_hits:
        all_detections.append({
            "start": start,
            "end": end,
            "entity_type": entity_type,
            "value": value,
            "score": 0.85  # our regex is reliable
        })
    
    # Remove overlapping detections
    # Priority: AGE/custom regex > Presidio

    custom_set = set()
    for start, end, entity_type, value in custom_hits:
        custom_set.add((start, end))

    for detection in all_detections:
        if detection["entity_type"] == "AGE":
            detection["priority"] = 2
        elif (detection["start"], detection["end"]) in custom_set:
            detection["priority"] = 1
        else:
            detection["priority"] = 0

    all_detections.sort(key=lambda x: x["start"])

    non_overlapping = []
    last_end = -1

    for detection in all_detections:

        if detection["start"] >= last_end:
            non_overlapping.append(detection)
            last_end = detection["end"]

        else:
            current = non_overlapping[-1]
            incoming = detection

            if incoming["priority"] > current["priority"]:
                non_overlapping[-1] = incoming
                last_end = incoming["end"]

            elif incoming["priority"] == current["priority"]:

                current_len = current["end"] - current["start"]
                incoming_len = incoming["end"] - incoming["start"]

                if incoming_len > current_len:
                    non_overlapping[-1] = incoming
                    last_end = incoming["end"]
    
    if not non_overlapping:
        return {
            "anonymous_transcript": transcript,
            "pii_mapping": {},
            "pii_found": False
        }
    
    # ── Step 5: Build mapping and replace from right to left ──
    # Sort by position, rightmost first
    non_overlapping.sort(key=lambda x: x["start"], reverse=True)
    
    pii_mapping = {}
    anonymous_text = transcript
    type_counters = {}
    
    for detection in non_overlapping:
        entity_type = detection["entity_type"]
        original_value = detection["value"]
        
        # Check if this exact value already has a placeholder
        existing_placeholder = None
        for ph, val in pii_mapping.items():
            if val.strip().lower() == original_value.strip().lower():
                existing_placeholder = ph
                break
        
        if existing_placeholder:
            actual_placeholder = existing_placeholder
        else:
            if entity_type not in type_counters:
                type_counters[entity_type] = 1
            else:
                type_counters[entity_type] += 1
            
            actual_placeholder = f"[{entity_type}_{type_counters[entity_type]}]"
            pii_mapping[actual_placeholder] = original_value
        
        # Replace with a space on each side to prevent words merging
        # This fixes the "emailf you" bug you saw
        start = detection["start"]
        end = detection["end"]
        
        # Check if character before start is a letter (not a space)
        prefix = " " if start > 0 and transcript[start-1].isalpha() else ""
        # Check if character after end is a letter
        suffix = " " if end < len(transcript) and transcript[end].isalpha() else ""
        
        anonymous_text = (
            anonymous_text[:start] +
            prefix + actual_placeholder + suffix +
            anonymous_text[end:]
        )
    
    # Clean up any double spaces created by our prefix/suffix
    import re
    anonymous_text = re.sub(r' +', ' ', anonymous_text)
    
    return {
        "anonymous_transcript": anonymous_text,
        "pii_mapping": pii_mapping,
        "pii_found": True
    }


def reidentify(anonymous_soap, pii_mapping):
    """
    Restores real patient info into SOAP note.
    Works with both string and dict input.
    """
    
    if not pii_mapping:
        return anonymous_soap
    
    if isinstance(anonymous_soap, dict):
        reidentified = {}
        for section, content in anonymous_soap.items():
            text = content
            for placeholder, real_value in pii_mapping.items():
                text = text.replace(placeholder, real_value)
            reidentified[section] = text
        return reidentified
    
    elif isinstance(anonymous_soap, str):
        text = anonymous_soap
        for placeholder, real_value in pii_mapping.items():
            text = text.replace(placeholder, real_value)
        return text
    
    else:
        raise ValueError(f"Input must be str or dict, got {type(anonymous_soap)}")


def process_transcript(transcript, analyzer=None, anonymizer=None):
    """
    MAIN FUNCTION — called by Module 4.
    """
    
    try:
        if analyzer is None or anonymizer is None:
            analyzer, anonymizer = create_engines()
        
        result = anonymize(transcript, analyzer, anonymizer)
        
        return {
            "anonymous_transcript": result["anonymous_transcript"],
            "pii_mapping": result["pii_mapping"],
            "pii_found": result["pii_found"],
            "original_transcript": transcript,
            "status": "success"
        }
    
    except Exception as e:
        return {
            "anonymous_transcript": transcript,
            "pii_mapping": {},
            "pii_found": False,
            "original_transcript": transcript,
            "status": "error",
            "error": str(e)
        }


if __name__ == "__main__":
    
    test_transcript = """Doctor: Good morning Mr. Rajesh Kumar, what brings you in today?
Patient: Doctor, I am Rajesh Kumar, 45 years old from Chennai. I have been having chest pain since Monday the 12th. My phone number is 9876543210.
Doctor: Okay Rajesh, let me note that down. You were seen at Apollo Hospital last year correct?
Patient: Yes, in 2023. My email is rajesh.kumar@gmail.com if you need to reach me."""

    print("ORIGINAL TRANSCRIPT:")
    print("="*50)
    print(test_transcript)
    print()

    analyzer, anonymizer_engine = create_engines()
    result = process_transcript(test_transcript, analyzer, anonymizer_engine)

    print("ANONYMOUS TRANSCRIPT:")
    print("="*50)
    print(result["anonymous_transcript"])
    print()

    print("PII MAPPING:")
    print("="*50)
    for placeholder, real_value in result["pii_mapping"].items():
        print(f"  {placeholder:25s} → {real_value}")
    print()

    # This time the fake SOAP only uses placeholders
    # that we KNOW exist from the mapping
    first_person = next(
        (k for k in result["pii_mapping"] if "PERSON" in k), None
    )
    first_date = None

    for placeholder, value in result["pii_mapping"].items():

        if "DATE_TIME" not in placeholder:
            continue

        value_lower = value.lower()

        if any(day in value_lower for day in [
            "monday", "tuesday", "wednesday",
            "thursday", "friday", "saturday", "sunday"
        ]):
            first_date = placeholder
            break

    if first_date is None:
        first_date = next(
            (k for k in result["pii_mapping"] if "DATE_TIME" in k),
            None
        )
    first_location = next(
        (k for k in result["pii_mapping"] if "LOCATION" in k), None
    )
    first_email = next(
        (k for k in result["pii_mapping"] if "EMAIL" in k), None
    )
    first_age = next(
        (k for k in result["pii_mapping"] if "AGE" in k), None
    )

    # Build fake SOAP using only placeholders that actually exist
    subjective_parts = []
    if first_person:
        subjective_parts.append(f"{first_person} presents with chest pain")
    if first_age:
        subjective_parts.append(f"aged {first_age}")
    if first_date:
        subjective_parts.append(f"since {first_date}")

    fake_soap = {
        "subjective": ". ".join(subjective_parts) + ".",
        "objective": f"Patient previously seen at {first_location}." if first_location else "Vitals normal.",
        "assessment": "Chest pain — further evaluation needed.",
        "plan": f"Follow up via {first_email}." if first_email else "Schedule follow-up."
    }

    print("ANONYMOUS SOAP (simulating GPT-4o output):")
    print("="*50)
    for section, content in fake_soap.items():
        print(f"{section.upper()}: {content}")
    print()

    reidentified = reidentify(fake_soap, result["pii_mapping"])

    print("REIDENTIFIED SOAP (final for doctor):")
    print("="*50)
    for section, content in reidentified.items():
        print(f"{section.upper()}: {content}")
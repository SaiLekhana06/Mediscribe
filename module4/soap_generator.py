"""
Module 3 - AI SOAP Generator with RAG and Confidence Scoring
MediScribe Project

Input:  Anonymous transcript from Module 2
Output: Structured SOAP note + confidence scores per section
"""

import json
import os

import chromadb
import google.generativeai as genai 
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer, util

# Load API key from .env file
load_dotenv()

# Configuration
CHROMA_DB_PATH = "./medical_knowledge_db"
COLLECTION_NAME = "medical_knowledge"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
LLM_MODEL = "models/gemini-2.5-flash"
RAG_RESULTS_COUNT = 5

# Confidence thresholds
HIGH_CONFIDENCE = 0.75
MEDIUM_CONFIDENCE = 0.50
# below 0.50 = red badge

REQUIRED_SOAP_SECTIONS = ["subjective", "objective", "assessment", "plan"]
DEFAULT_SECTION_TEXT = "Not documented in transcript"
DEFAULT_ASSESSMENT_TEXT = "Diagnosis not documented in transcript"


def load_components():
    """
    Loads all AI components once at startup.
    Returns them so they can be reused across multiple calls.

    Loading these is slow - do it once, reuse many times.
    """

    print("Loading AI components...")

    # Gemini client/model
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found. "
            "Check your .env file in the module3 folder."
        )

    genai.configure(api_key=api_key)
    gemini_model = genai.GenerativeModel(LLM_MODEL)

    # ChromaDB connection
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )

    try:
        collection = chroma_client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_func
        )
    except Exception:
        raise RuntimeError(
            "Medical knowledge database not found. "
            "Please run build_knowledge_base.py first."
        )

    # Sentence transformer for confidence scoring
    # Same model as embeddings for consistency
    similarity_model = SentenceTransformer(EMBEDDING_MODEL)

    print("All components loaded.")

    return {
        "gemini": gemini_model,
        "collection": collection,
        "similarity_model": similarity_model
    }


def retrieve_medical_context(transcript, collection, n_results=RAG_RESULTS_COUNT):
    """
    Searches the medical knowledge base for entries
    relevant to the content of this transcript.

    This is the R in RAG - Retrieval.

    transcript: anonymous transcript string
    collection: ChromaDB collection
    n_results:  how many relevant entries to retrieve

    Returns a string of relevant medical context to
    inject into the Gemini prompt.
    """

    results = collection.query(
        query_texts=[transcript],
        n_results=n_results
    )

    if not results["documents"][0]:
        return "No specific medical context retrieved."

    context_parts = []
    for i, doc in enumerate(results["documents"][0]):
        context_parts.append(f"Medical Reference {i + 1}:\n{doc}")

    context = "\n\n".join(context_parts)
    return context


def build_soap_prompt(anonymous_transcript, medical_context):
    """
    Builds the prompt that will be sent to Gemini 1.5 Flash.

    The prompt explicitly prevents the model from inferring diagnoses
    or adding clinical details that were not stated in the transcript.
    """

    system_prompt = """You are an expert medical scribe AI assistant.
Your task is to convert a doctor-patient conversation transcript into a structured SOAP clinical note.

You are not diagnosing the patient. You are only documenting what was explicitly stated in the transcript.

CRITICAL RULES:
1. ONLY include information explicitly mentioned in the transcript.
2. Do NOT add diagnoses, medications, findings, symptoms, treatments, investigations, or recommendations that were not discussed.
3. Do NOT make assumptions or inferences beyond what was said.
4. If the physician does not explicitly state a diagnosis, do NOT generate one.
5. Do NOT infer diseases from symptoms.
6. If no diagnosis is documented, write exactly:
   "Diagnosis not documented in transcript"
7. Assessment section must only contain:
   a) diagnoses explicitly stated by the physician
   b) differential diagnoses explicitly stated by the physician
   c) clinical impressions explicitly stated by the physician
   d) otherwise "Diagnosis not documented in transcript"
8. Use proper medical terminology only when it reflects what was said.
9. Keep placeholder tokens like [PERSON_1], [DATE_TIME_1], [AGE_1], and [LOCATION_1] exactly as they appear.

SOAP FORMAT GUIDE:
- Subjective (S): Patient's chief complaint, symptoms as described by patient, and relevant history mentioned in the transcript.
- Objective (O): Measurable findings explicitly mentioned, such as vitals, physical exam findings, test results, or observations stated by the physician.
- Assessment (A): Only diagnoses, differential diagnoses, or clinical impressions explicitly stated by the physician in the transcript. Do not infer diagnoses from symptoms.
- Plan (P): Only investigations, treatments, medications, referrals, patient education, or follow-up instructions explicitly stated by the physician.

ASSESSMENT EXAMPLES:

EXAMPLE 1
Transcript:
Patient: I have fever and cough.
Doctor: I will order some tests.

Assessment:
Diagnosis not documented in transcript.

EXAMPLE 2
Transcript:
Patient: I have fever and cough.
Doctor: This appears to be a viral upper respiratory tract infection.

Assessment:
Viral upper respiratory tract infection.

RESPONSE FORMAT:
Return ONLY a valid JSON object with exactly these 4 keys.
Do not include any text before or after the JSON.
Do not include markdown code blocks.

{
    "subjective": "...",
    "objective": "...",
    "assessment": "...",
    "plan": "..."
}

If subjective, objective, or plan cannot be filled from the transcript,
write "Not documented in transcript" for that section.

If assessment cannot be filled from an explicit physician diagnosis,
differential diagnosis, or clinical impression, write
"Diagnosis not documented in transcript" for assessment."""

    user_prompt = f"""MEDICAL REFERENCE CONTEXT:
{medical_context}

Important: The medical reference context is only background terminology support.
Do not copy diagnoses, treatments, investigations, or recommendations from the
medical reference context unless they were explicitly discussed in the transcript.

DOCTOR-PATIENT TRANSCRIPT:
{anonymous_transcript}

Generate the SOAP note now. Remember: only document information explicitly
mentioned in the transcript above."""

    return system_prompt, user_prompt


def extract_response_text(response):
    """
    Safely extracts text from a Gemini response object.
    """

    try:
        if response.text:
            return response.text
    except Exception:
        pass

    try:
        parts = response.candidates[0].content.parts
        return "".join(part.text for part in parts if hasattr(part, "text"))
    except Exception:
        return ""


def clean_json_response(response_text):
    """
    Removes common formatting around model output while preserving JSON content.
    """

    cleaned = response_text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise json.JSONDecodeError("No JSON object found in Gemini response", cleaned, 0)

    return cleaned[start:end + 1]


def parse_soap_json(response_text):
    """
    Parses and validates Gemini's SOAP JSON response.
    """

    json_text = clean_json_response(response_text)
    soap = json.loads(json_text)

    if not isinstance(soap, dict):
        raise ValueError("Gemini response JSON must be an object.")

    validated_soap = {}
    for section in REQUIRED_SOAP_SECTIONS:
        value = soap.get(section)

        if value is None:
            if section == "assessment":
                validated_soap[section] = DEFAULT_ASSESSMENT_TEXT
            else:
                validated_soap[section] = DEFAULT_SECTION_TEXT
            continue

        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False)
        else:
            value = str(value).strip()

        if not value:
            if section == "assessment":
                value = DEFAULT_ASSESSMENT_TEXT
            else:
                value = DEFAULT_SECTION_TEXT

        validated_soap[section] = value

    return validated_soap
def generate_soap(anonymous_transcript, gemini_model, collection):
    """
    Calls Gemini to generate the SOAP note.
    Has retry logic in case of empty response.
    """

    medical_context = retrieve_medical_context(
        anonymous_transcript, collection
    )

    system_prompt, user_prompt = build_soap_prompt(
        anonymous_transcript, medical_context
    )

    prompt = f"{system_prompt}\n\n{user_prompt}"

    # Try up to 3 times in case Gemini returns empty
    last_error = None
    for attempt in range(3):
        try:
            print(f"Gemini attempt {attempt + 1}/3...")

            response = gemini_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=1000
                    # response_mime_type REMOVED — causes empty responses
                )
            )

            response_text = extract_response_text(response)

            if not response_text or response_text.strip() == "":
                print(f"Attempt {attempt + 1}: Empty response from Gemini, retrying...")
                last_error = "Gemini returned empty response"
                continue

            print(f"Attempt {attempt + 1}: Got response, parsing JSON...")
            soap = parse_soap_json(response_text)

            return {
                "soap": soap,
                "medical_context_used": medical_context,
                "status": "success"
            }

        except json.JSONDecodeError as e:
            print(f"Attempt {attempt + 1}: JSON error — {str(e)}")
            last_error = f"JSON parse error: {str(e)}"
            continue

        except Exception as e:
            print(f"Attempt {attempt + 1}: Exception — {str(e)}")
            last_error = str(e)
            break

    # All attempts failed
    return {
        "soap": {
            "subjective": "Error generating SOAP note",
            "objective":  "Error generating SOAP note",
            "assessment": "Error generating SOAP note",
            "plan":       "Error generating SOAP note"
        },
        "medical_context_used": medical_context,
        "status": "error",
        "error": last_error
    }


def calculate_confidence_scores(soap, original_transcript, similarity_model):
    """
    Measures how much of each SOAP section can be
    traced back to the original transcript.
    """

    confidence_scores = {}
    sections = ["subjective", "objective", "assessment", "plan"]

    for section in sections:
        section_text = soap.get(section, "")

        if not section_text or section_text == "Not documented in transcript" or section_text == "Diagnosis not documented in transcript":
            confidence_scores[section] = -1
            continue

        if "Error" in section_text:
            confidence_scores[section] = 0.0
            continue

        try:
            soap_embedding = similarity_model.encode(
                section_text, convert_to_tensor=True
            )
            transcript_embedding = similarity_model.encode(
                original_transcript, convert_to_tensor=True
            )

            similarity = util.cos_sim(
                soap_embedding, transcript_embedding
            ).item()

            confidence_scores[section] = round(similarity, 2)

        except Exception:
            confidence_scores[section] = 0.5

    return confidence_scores


def get_confidence_labels(confidence_scores):
    """
    Converts numeric scores to human-readable labels
    for the frontend to display as colored badges.
    """

    labels = {}
    for section, score in confidence_scores.items():
        if score == -1:
            labels[section] = "NOT_DOCUMENTED"
        elif score >= HIGH_CONFIDENCE:
            labels[section] = "HIGH"
        elif score >= MEDIUM_CONFIDENCE:
            labels[section] = "MEDIUM"
        else:
            labels[section] = "LOW"
    return labels


def process_transcript(anonymous_transcript, components=None):
    """
    MAIN FUNCTION - called by Module 4.
    """

    try:
        if components is None:
            components = load_components()

        soap_result = generate_soap(
            anonymous_transcript,
            components["gemini"],
            components["collection"]
        )

        if soap_result["status"] == "error":
            return {
                "soap": {},
                "confidence_scores": {},
                "confidence_labels": {},
                "status": "error",
                "error": soap_result.get("error", "Unknown error")
            }

        confidence_scores = calculate_confidence_scores(
            soap_result["soap"],
            anonymous_transcript,
            components["similarity_model"]
        )

        confidence_labels = get_confidence_labels(confidence_scores)

        return {
            "soap": soap_result["soap"],
            "confidence_scores": confidence_scores,
            "confidence_labels": confidence_labels,
            "status": "success"
        }

    except Exception as e:
        return {
            "soap": {},
            "confidence_scores": {},
            "confidence_labels": {},
            "status": "error",
            "error": str(e)
        }


if __name__ == "__main__":

    test_transcript = """Doctor: Good morning [PERSON_2], what brings you in today?
Patient: Doctor, I am [PERSON_2], [AGE_1] from [LOCATION_2]. I have been having chest pain since [DATE_TIME_3]. The pain is on the left side and feels like pressure.
Doctor: Okay. Does the pain radiate anywhere? Any shortness of breath?
Patient: Yes, it goes to my left arm sometimes. I do feel short of breath when climbing stairs.
Doctor: I see. Your BP today is 145 over 90. Heart rate is 88. I am going to order an ECG and troponin levels. You are on Amlodipine 5mg daily correct?
Patient: Yes doctor, for my blood pressure.
Doctor: Alright. I will also check your troponin. Come back in 24 hours or go to emergency immediately if pain worsens."""

    print("Loading components...")
    components = load_components()

    print("\nGenerating SOAP note...")
    result = process_transcript(test_transcript, components)

    if result["status"] == "success":
        print("\n" + "=" * 50)
        print("GENERATED SOAP NOTE")
        print("=" * 50)

        for section in ["subjective", "objective", "assessment", "plan"]:
            score = result["confidence_scores"][section]
            label = result["confidence_labels"][section]
            print(f"\n{section.upper()} [{label} - {score}]:")
            print(f"{result['soap'][section]}")

        print("\n" + "=" * 50)
        print("CONFIDENCE SUMMARY")
        print("=" * 50)
        for section, label in result["confidence_labels"].items():
            score = result["confidence_scores"][section]
            bar = "#" * int(score * 10) + "-" * (10 - int(score * 10))
            print(f"  {section:12s}: {bar} {score:.2f} [{label}]")

    else:
        print(f"\nError: {result['error']}")
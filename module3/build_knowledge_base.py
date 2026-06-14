"""
Builds the ChromaDB medical knowledge base.
Run this ONCE before using soap_generator.py.

This script loads ICD-10 medical knowledge into ChromaDB
so the RAG system can retrieve relevant context during
SOAP generation.
"""

import chromadb
from chromadb.utils import embedding_functions

# We use sentence-transformers for embeddings
# This runs completely locally — no API calls needed
# all-MiniLM-L6-v2 is small, fast, and good enough for medical text
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHROMA_DB_PATH = "./medical_knowledge_db"
COLLECTION_NAME = "medical_knowledge"

# Medical knowledge entries
# Format: each entry has an id, the medical text, and metadata
# In a production system you would load thousands of entries
# from a real ICD-10 database or medical textbook
# For the hackathon, 50-100 well-chosen entries is sufficient
MEDICAL_KNOWLEDGE = [
    # Chest Pain entries
    {
        "id": "chest_pain_001",
        "text": "Chest pain is a common presenting complaint. Key features to assess: location, radiation, quality (sharp/dull/pressure), severity (1-10), onset, duration, associated symptoms. Red flags: crushing chest pain radiating to left arm or jaw, associated diaphoresis, shortness of breath, nausea — these suggest acute coronary syndrome (ACS) requiring urgent evaluation.",
        "metadata": {"category": "symptom", "icd10": "R07", "condition": "chest_pain"}
    },
    {
        "id": "chest_pain_002",
        "text": "Acute Coronary Syndrome (ACS) includes unstable angina, NSTEMI, and STEMI. Diagnostic workup: 12-lead ECG, serum troponin levels, chest X-ray. Management: aspirin, oxygen if SpO2 < 94%, nitrates for pain, anticoagulation, cardiology consultation.",
        "metadata": {"category": "condition", "icd10": "I24", "condition": "ACS"}
    },
    {
        "id": "chest_pain_003",
        "text": "Hypertensive chest pain: blood pressure above 140/90 mmHg is classified as hypertension. Stage 1: 140-159/90-99. Stage 2: 160+/100+. Hypertensive urgency when BP > 180/120 without end-organ damage. Common medications: Amlodipine, Lisinopril, Atenolol, Losartan.",
        "metadata": {"category": "condition", "icd10": "I10", "condition": "hypertension"}
    },

    # Respiratory entries
    {
        "id": "respiratory_001",
        "text": "Shortness of breath (dyspnea) assessment: onset (sudden vs gradual), exertional vs rest, orthopnea, PND. Common causes: asthma, COPD, heart failure, pneumonia, pulmonary embolism, anemia. Key examination findings: respiratory rate, oxygen saturation, auscultation findings.",
        "metadata": {"category": "symptom", "icd10": "R06", "condition": "dyspnea"}
    },
    {
        "id": "respiratory_002",
        "text": "Asthma: reversible airway obstruction. Symptoms: wheeze, cough (worse at night), chest tightness, shortness of breath. Triggers: allergens, cold air, exercise, infection. Management: short-acting beta agonist (salbutamol) for acute relief, inhaled corticosteroids for maintenance.",
        "metadata": {"category": "condition", "icd10": "J45", "condition": "asthma"}
    },
    {
        "id": "respiratory_003",
        "text": "Pneumonia: infection of lung parenchyma. Features: fever, productive cough, pleuritic chest pain, consolidation on examination. Investigations: chest X-ray (consolidation), CBC (raised WBC), sputum culture. Management: antibiotics based on severity — amoxicillin for mild, co-amoxiclav for moderate.",
        "metadata": {"category": "condition", "icd10": "J18", "condition": "pneumonia"}
    },

    # Fever and infection
    {
        "id": "fever_001",
        "text": "Fever: core body temperature above 38.0 degrees Celsius. Assessment: duration, pattern, associated symptoms, recent travel, sick contacts, vaccination history. Common causes: viral URTI, UTI, pneumonia, malaria in endemic areas. Investigations guided by clinical findings.",
        "metadata": {"category": "symptom", "icd10": "R50", "condition": "fever"}
    },
    {
        "id": "fever_002",
        "text": "Upper respiratory tract infection (URTI): most commonly viral. Symptoms: runny nose, sore throat, mild fever, cough, malaise. Management: symptomatic — rest, hydration, paracetamol/ibuprofen for fever and pain. Antibiotics NOT indicated for viral URTI. Duration typically 7-10 days.",
        "metadata": {"category": "condition", "icd10": "J06", "condition": "URTI"}
    },

    # Diabetes
    {
        "id": "diabetes_001",
        "text": "Type 2 Diabetes Mellitus: chronic metabolic disorder. Symptoms: polyuria, polydipsia, polyphagia, weight loss, fatigue, blurred vision. Diagnostic criteria: fasting glucose >= 126 mg/dL, HbA1c >= 6.5%, random glucose >= 200 with symptoms. First line management: metformin, lifestyle modification.",
        "metadata": {"category": "condition", "icd10": "E11", "condition": "type2_diabetes"}
    },
    {
        "id": "diabetes_002",
        "text": "Diabetic complications: microvascular (nephropathy, retinopathy, neuropathy) and macrovascular (cardiovascular disease, peripheral artery disease). Monitoring: HbA1c every 3 months, annual eye exam, annual foot exam, urine microalbumin, lipid profile. Target HbA1c < 7% for most patients.",
        "metadata": {"category": "complication", "icd10": "E11.9", "condition": "diabetes_complications"}
    },

    # Hypertension
    {
        "id": "hypertension_001",
        "text": "Hypertension management: lifestyle modifications first — DASH diet, reduce sodium, regular exercise, limit alcohol, smoking cessation. Pharmacotherapy: ACE inhibitors (ramipril, lisinopril), ARBs (losartan, telmisartan), calcium channel blockers (amlodipine), thiazide diuretics. Target BP < 130/80 for most patients.",
        "metadata": {"category": "management", "icd10": "I10", "condition": "hypertension_management"}
    },

    # Abdominal pain
    {
        "id": "abdominal_001",
        "text": "Abdominal pain assessment: location (RUQ, RLQ, LUQ, LLQ, periumbilical, diffuse), character, radiation, severity, associated symptoms (nausea, vomiting, diarrhea, constipation, fever, jaundice). RLQ pain with rebound tenderness suggests appendicitis. RUQ pain after fatty meals suggests cholelithiasis.",
        "metadata": {"category": "symptom", "icd10": "R10", "condition": "abdominal_pain"}
    },
    {
        "id": "abdominal_002",
        "text": "Gastroesophageal reflux disease (GERD): burning chest/epigastric pain, worse after meals and lying down, regurgitation, sour taste. Management: lifestyle — avoid trigger foods, elevate head of bed, lose weight. Medications: antacids, H2 blockers (ranitidine), proton pump inhibitors (omeprazole, pantoprazole).",
        "metadata": {"category": "condition", "icd10": "K21", "condition": "GERD"}
    },

    # Headache
    {
        "id": "headache_001",
        "text": "Headache assessment: SOCRATES — site, onset, character, radiation, associated symptoms, timing, exacerbating/relieving factors, severity. Red flags (SNOOP): Systemic symptoms, Neurological symptoms, Onset sudden, Older age first headache, Pattern change. Tension headache: bilateral pressing quality. Migraine: unilateral, pulsating, with nausea/photophobia.",
        "metadata": {"category": "symptom", "icd10": "R51", "condition": "headache"}
    },
    {
        "id": "headache_002",
        "text": "Migraine management: acute — triptans (sumatriptan), NSAIDs, antiemetics. Prophylaxis if > 4 episodes/month: propranolol, topiramate, amitriptyline, sodium valproate. Trigger avoidance: stress, lack of sleep, caffeine, certain foods. Menstrual migraine: consider hormonal triggers.",
        "metadata": {"category": "management", "icd10": "G43", "condition": "migraine"}
    },

    # Vital signs interpretation
    {
        "id": "vitals_001",
        "text": "Normal vital signs in adults: Blood pressure 90-120/60-80 mmHg. Heart rate 60-100 bpm. Respiratory rate 12-20 breaths/min. Temperature 36.1-37.2 degrees Celsius. Oxygen saturation SpO2 > 95%. Random blood glucose 70-140 mg/dL. BMI 18.5-24.9 normal range.",
        "metadata": {"category": "reference", "icd10": "Z00", "condition": "normal_vitals"}
    },
    {
        "id": "vitals_002",
        "text": "Tachycardia: heart rate > 100 bpm. Causes: fever, pain, anxiety, dehydration, anemia, hyperthyroidism, cardiac arrhythmia, medications. Bradycardia: heart rate < 60 bpm. Causes: athletic training, hypothyroidism, medications (beta blockers), heart block. Hypertension: systolic > 140 or diastolic > 90.",
        "metadata": {"category": "reference", "icd10": "R00", "condition": "vital_abnormalities"}
    },

    # Common medications
    {
        "id": "medications_001",
        "text": "Amlodipine: calcium channel blocker for hypertension and angina. Usual dose 5-10 mg once daily. Side effects: peripheral edema, flushing, headache. Lisinopril: ACE inhibitor for hypertension and heart failure. Usual dose 5-40 mg once daily. Contraindicated in pregnancy. Side effect: dry cough.",
        "metadata": {"category": "medication", "icd10": "Z79", "condition": "antihypertensives"}
    },
    {
        "id": "medications_002",
        "text": "Metformin: first line for type 2 diabetes. Dose 500-2000 mg daily with meals. Side effects: GI upset, lactic acidosis (rare). Contraindicated: eGFR < 30. Paracetamol (acetaminophen): analgesic and antipyretic. Dose 500-1000 mg every 4-6 hours, max 4g/day. Avoid in liver disease.",
        "metadata": {"category": "medication", "icd10": "Z79", "condition": "common_medications"}
    },

    # SOAP note guidance
    {
        "id": "soap_001",
        "text": "SOAP note Subjective section: document patient's chief complaint in their own words, history of present illness (onset, duration, character, severity, associated symptoms), past medical history, current medications, allergies, family history, social history.",
        "metadata": {"category": "documentation", "icd10": "Z00", "condition": "soap_subjective"}
    },
    {
        "id": "soap_002",
        "text": "SOAP note Objective section: document measurable findings — vital signs (BP, HR, RR, Temp, SpO2, weight), physical examination findings, laboratory results, imaging results, ECG findings. Only include findings that were actually measured or observed.",
        "metadata": {"category": "documentation", "icd10": "Z00", "condition": "soap_objective"}
    },
    {
        "id": "soap_003",
        "text": "SOAP note Assessment section: document clinical diagnosis or differential diagnoses ranked by likelihood. Use proper medical terminology and ICD-10 compatible descriptions. Include any active chronic conditions being managed.",
        "metadata": {"category": "documentation", "icd10": "Z00", "condition": "soap_assessment"}
    },
    {
        "id": "soap_004",
        "text": "SOAP note Plan section: document management plan for each problem — investigations ordered, medications prescribed (name, dose, frequency, duration), referrals, patient education, follow-up instructions. Each plan item should correspond to an assessment item.",
        "metadata": {"category": "documentation", "icd10": "Z00", "condition": "soap_plan"}
    },

    # Musculoskeletal
    {
        "id": "msk_001",
        "text": "Back pain assessment: location (cervical, thoracic, lumbar, sacral), radiation (sciatica if radiates below knee), red flags (TUNA FISH — Trauma, systemic Upset, Neurological deficit, Age > 50, IVDU, Steroids, Hx cancer). Mechanical back pain: worse with movement, better with rest. Inflammatory: worse with rest, morning stiffness.",
        "metadata": {"category": "symptom", "icd10": "M54", "condition": "back_pain"}
    },

    # Mental health
    {
        "id": "mental_001",
        "text": "Depression screening: PHQ-2 — depressed mood and anhedonia. If positive, PHQ-9 for severity. Key features: low mood, anhedonia, sleep disturbance, appetite change, fatigue, poor concentration, worthlessness, suicidal ideation. Management: psychotherapy, SSRIs (sertraline, fluoxetine), lifestyle measures.",
        "metadata": {"category": "condition", "icd10": "F32", "condition": "depression"}
    },

    # Urinary
    {
        "id": "uti_001",
        "text": "Urinary tract infection (UTI): dysuria, frequency, urgency, suprapubic pain, cloudy or foul-smelling urine. Investigations: urine dipstick (nitrites, leukocytes), urine culture. Management: trimethoprim or nitrofurantoin for uncomplicated lower UTI. Upper UTI (pyelonephritis): flank pain, fever, nausea — requires broader spectrum antibiotics.",
        "metadata": {"category": "condition", "icd10": "N39", "condition": "UTI"}
    },
]


def build_knowledge_base():
    """
    Creates ChromaDB collection and loads all medical knowledge into it.
    Run this once — after that the database persists on disk.
    """
    
    print("Setting up ChromaDB...")
    
    # Create ChromaDB client that saves to disk
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    
    # Set up the embedding function
    # This converts text to numbers for similarity search
    # Runs locally — no API calls
    print("Loading embedding model (first run downloads ~90MB)...")
    embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )
    
    # Delete existing collection if rebuilding
    try:
        client.delete_collection(COLLECTION_NAME)
        print("Deleted existing collection — rebuilding...")
    except Exception:
        pass
    
    # Create fresh collection
    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_func,
        metadata={"description": "Medical knowledge for MediScribe RAG"}
    )
    
    # Prepare data for insertion
    ids = [entry["id"] for entry in MEDICAL_KNOWLEDGE]
    texts = [entry["text"] for entry in MEDICAL_KNOWLEDGE]
    metadatas = [entry["metadata"] for entry in MEDICAL_KNOWLEDGE]
    
    # Insert in batches
    batch_size = 10
    total = len(MEDICAL_KNOWLEDGE)
    
    for i in range(0, total, batch_size):
        batch_ids = ids[i:i+batch_size]
        batch_texts = texts[i:i+batch_size]
        batch_metadata = metadatas[i:i+batch_size]
        
        collection.add(
            ids=batch_ids,
            documents=batch_texts,
            metadatas=batch_metadata
        )
        
        print(f"Loaded {min(i+batch_size, total)}/{total} entries...")
    
    print(f"\nKnowledge base built successfully!")
    print(f"Location: {CHROMA_DB_PATH}")
    print(f"Total entries: {total}")
    
    # Quick verification
    results = collection.query(
        query_texts=["chest pain blood pressure"],
        n_results=2
    )
    print(f"\nVerification query — 'chest pain blood pressure':")
    for doc in results["documents"][0]:
        print(f"  Found: {doc[:100]}...")
    
    return collection


if __name__ == "__main__":
    build_knowledge_base()
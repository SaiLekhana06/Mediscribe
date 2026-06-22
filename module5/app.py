"""
Module 5 — MediScribe Frontend (Improved)
All 6 UI/UX improvements implemented:
1. Dynamic doctor history using authenticated user ID
2. Auto-refresh after save with visual feedback
3. Sticky confidence panel
4. Approval confirmation modal
5. Enhanced history with search, filter, sort, pagination
6. Dynamic dashboard metrics from real data
"""

import streamlit as st
import requests
from datetime import datetime, timezone

LOCAL_API  = "http://localhost:8000"   # audio processing
CLOUD_API  = "https://mediscribe-api-production-ebed.up.railway.app"
API_BASE   = CLOUD_API  # default for auth, history, notes

# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title="MediScribe",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --green-950:#10231F;
    --green-900:#16352E;
    --green-800:#1F4A40;
    --green-700:#2D7A63;
    --green-600:#34A77E;
    --green-100:#E9F7F1;
    --green-50:#F5FBF8;
    --ink:#172622;
    --muted:#6C817A;
    --line:#DCEBE5;
    --shadow:0 12px 30px rgba(16,35,31,.08);
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at top left, rgba(52,167,126,.10), transparent 34rem),
        linear-gradient(180deg, #F8FCFA 0%, #FFFFFF 42%);
    color: var(--ink);
}

.main .block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1180px;
}

h1, h2, h3, .page-title { letter-spacing: 0; }

.page-title {
    font-size: 1.9rem;
    font-weight: 800;
    color: var(--ink);
    margin-bottom: .25rem;
    line-height: 1.15;
}

.page-sub {
    font-size: .95rem;
    color: var(--muted);
    margin-bottom: 1.6rem;
}

.metric-card,
.history-card,
.empty-state,
.privacy-box,
.modal-box,
.confidence-shell {
    background: rgba(255,255,255,.92);
    border: 1px solid var(--line);
    border-radius: 14px;
    box-shadow: var(--shadow);
}

.metric-card {
    position: relative;
    overflow: hidden;
    padding: 1.25rem 1.25rem 1.15rem;
    min-height: 132px;
    background: rgba(255,255,255,.75);
    border: 1px solid rgba(207,227,219,.72);
    border-radius: 18px;
    box-shadow: 0 16px 38px rgba(16,35,31,.09), inset 0 1px 0 rgba(255,255,255,.72);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    transition: transform .24s ease, box-shadow .24s ease, border-color .24s ease, background .24s ease;
}

.metric-card::before {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(255,255,255,.42), rgba(255,255,255,0) 42%);
    pointer-events: none;
}

.metric-card:hover {
    transform: translateY(-4px);
    background: rgba(255,255,255,.86);
    border-color: rgba(52,167,126,.46);
    box-shadow: 0 22px 48px rgba(16,35,31,.14), inset 0 1px 0 rgba(255,255,255,.82);
}

.metric-accent {
    position: absolute;
    top: 1rem;
    right: 1rem;
    width: 34px;
    height: 34px;
    border-radius: 999px;
    background: linear-gradient(135deg, rgba(69,192,139,.95), rgba(45,122,99,.95));
    box-shadow: 0 10px 24px rgba(45,122,99,.20);
}

.metric-accent::after {
    content: "";
    position: absolute;
    inset: 9px;
    border-radius: inherit;
    background: rgba(255,255,255,.72);
}

.metric-label {
    position: relative;
    z-index: 1;
    max-width: calc(100% - 48px);
    font-size: .74rem;
    font-weight: 800;
    color: #3E5F55;
    text-transform: uppercase;
    letter-spacing: .075em;
    margin-bottom: .62rem;
}

.metric-value {
    position: relative;
    z-index: 1;
    font-size: 2.35rem;
    font-weight: 850;
    color: #10231F;
    line-height: .95;
}

.metric-delta {
    position: relative;
    z-index: 1;
    font-size: .82rem;
    font-weight: 650;
    color: #245E50;
    margin-top: .7rem;
    line-height: 1.35;
}

.s-approved,
.s-pending {
    display: inline-flex;
    align-items: center;
    gap: .35rem;
    padding: .25rem .65rem;
    border-radius: 999px;
    font-size: .72rem;
    font-weight: 700;
    letter-spacing: .03em;
}

.s-approved { background:#DDF8EA; color:#166534; }
.s-pending { background:#FFF4D8; color:#92400E; }

.badge-high,
.badge-medium,
.badge-low,
.badge-nd {
    font-weight: 700;
    font-size: .78rem;
}

.badge-high { color:#166534; }
.badge-medium { color:#A16207; }
.badge-low { color:#B42318; }
.badge-nd { color:#667085; }

.confidence-shell { padding: 1rem; }
.confidence-item { margin-bottom: .95rem; }

.confidence-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: .75rem;
    margin-bottom: .35rem;
}

.confidence-title {
    font-size: .82rem;
    font-weight: 700;
    color: var(--ink);
}

.confidence-track {
    height: 7px;
    width: 100%;
    background: #EEF4F1;
    border-radius: 999px;
    overflow: hidden;
}

.confidence-fill {
    height: 100%;
    border-radius: 999px;
}

.conf-high { background: linear-gradient(90deg,#2D7A63,#45C08B); }
.conf-medium { background: linear-gradient(90deg,#D99A2B,#F2C14E); }
.conf-low { background: linear-gradient(90deg,#D9534F,#F08A80); }
.conf-nd { background: #A8B5B0; }

.soap-label {
    font-size: .82rem;
    font-weight: 800;
    color: var(--ink);
    text-transform: uppercase;
    letter-spacing: .06em;
    margin-bottom: .35rem;
    display: flex;
    align-items: center;
    gap: .55rem;
}

.sticky-confidence {
    position: sticky;
    top: 2rem;
}

.privacy-box {
    padding: 1.05rem 1.15rem;
    margin-bottom: 1.25rem;
    background: linear-gradient(135deg, rgba(233,247,241,.95), rgba(255,255,255,.95));
}

.privacy-box p {
    margin: .28rem 0;
    font-size: .86rem;
    color: var(--ink);
}

.history-card {
    padding: 1rem 1.1rem;
    margin-bottom: .85rem;
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}

.history-card:hover {
    transform: translateY(-2px);
    border-color: rgba(52,167,126,.45);
    box-shadow: 0 18px 38px rgba(16,35,31,.12);
}

.history-title {
    font-size: .98rem;
    font-weight: 800;
    color: var(--ink);
}

.history-meta {
    font-size: .8rem;
    color: var(--muted);
    margin-top: .15rem;
}

.empty-state {
    text-align: center;
    padding: 2.25rem 1.25rem;
    background: linear-gradient(135deg, rgba(233,247,241,.72), rgba(255,255,255,.98));
}

.empty-icon {
    width: 54px;
    height: 54px;
    margin: 0 auto .8rem;
    border-radius: 16px;
    display:flex;
    align-items:center;
    justify-content:center;
    background: var(--green-100);
    color: var(--green-700);
    font-size: 1.55rem;
}

.empty-title {
    font-size: 1rem;
    font-weight: 800;
    color: var(--ink);
    margin-bottom: .2rem;
}

.empty-copy {
    color: var(--muted);
    font-size: .9rem;
}

.modal-box {
    border-color: rgba(52,167,126,.55);
    padding: 1.5rem;
    margin: 1rem 0;
}

.modal-title {
    font-size: 1.05rem;
    font-weight: 800;
    color: var(--ink);
    margin-bottom: .45rem;
}

.modal-body {
    font-size: .9rem;
    color: var(--muted);
    line-height: 1.6;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #10231F 0%, #173B33 100%);
}

section[data-testid="stSidebar"] * { color: #DDEDE7 !important; }

.sidebar-brand { padding: .55rem .25rem 1rem; }
.brand-row { display:flex; align-items:center; gap:.7rem; }

.brand-mark {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    display:flex;
    align-items:center;
    justify-content:center;
    background: linear-gradient(135deg,#45C08B,#2D7A63);
    color:white !important;
    font-weight: 900;
    box-shadow: 0 10px 28px rgba(52,167,126,.28);
}

.brand-name {
    font-size: 1.15rem;
    font-weight: 850;
    color:white !important;
}

.brand-sub { font-size: .74rem; color:#9FC8BB !important; }

.doctor-card {
    margin: .8rem 0 1.15rem;
    padding: .85rem;
    border-radius: 14px;
    background: rgba(255,255,255,.08);
    border: 1px solid rgba(255,255,255,.16);
    display:flex;
    align-items:center;
    gap:.9rem;
}

.doctor-avatar {
    width: 48px;
    height: 48px;
    min-width: 48px;
    border-radius: 50%;
    display:flex;
    align-items:center;
    justify-content:center;
    background:#FFFFFF;
    color:#12362E !important;
    font-size: .98rem;
    font-weight: 900;
    letter-spacing: .03em;
    box-shadow: 0 8px 22px rgba(0,0,0,.18);
}

.doctor-name {
    font-size:.92rem;
    line-height:1.25;
    font-weight:800;
    color:white !important;
}
.doctor-role {
    margin-top:.12rem;
    font-size:.75rem;
    line-height:1.25;
    color:#B9DCD1 !important;
}

section[data-testid="stSidebar"] .stButton button {
    background: transparent !important;
    border: 1px solid rgba(255,255,255,.12) !important;
    color: #DDEDE7 !important;
    border-radius: 10px !important;
    text-align: left !important;
    width: 100% !important;
    min-height: 42px;
    transition: all .18s ease !important;
}

section[data-testid="stSidebar"] .stButton button:hover {
    background: rgba(255,255,255,.10) !important;
    border-color: rgba(69,192,139,.65) !important;
    transform: translateX(3px);
}

.stButton button,
.stDownloadButton button {
    border-radius: 10px !important;
    font-weight: 700 !important;
    transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease, background .16s ease !important;
}

.stButton button[kind="primary"],
.stButton button[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #2D7A63, #34A77E) !important;
    border-color: #2D7A63 !important;
    color: #FFFFFF !important;
}

.stButton button[kind="primary"] *,
.stButton button[data-testid="baseButton-primary"] * {
    color: #FFFFFF !important;
}

.stButton button:not([kind="primary"]):not([data-testid="baseButton-primary"]),
.stDownloadButton button {
    background: #FFFFFF !important;
    border: 1px solid #CFE3DB !important;
    color: #173B33 !important;
}

.stButton button:not([kind="primary"]):not([data-testid="baseButton-primary"]):hover,
.stDownloadButton button:hover {
    background: #F1FAF6 !important;
    border-color: #34A77E !important;
    color: #10231F !important;
}

.stButton button:hover,
.stDownloadButton button:hover { transform: translateY(-1px); }

.stButton button:disabled,
.stButton button:disabled *,
.stDownloadButton button:disabled,
.stDownloadButton button:disabled * {
    color: #7C8F88 !important;
}

div[data-testid="stTextInput"] label,
div[data-testid="stTextArea"] label,
div[data-testid="stFileUploader"] label,
div[data-testid="stSelectbox"] label {
    color: #172622 !important;
    font-weight: 700 !important;
}

div[data-testid="stTextInput"] input,
textarea,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    border-radius: 10px !important;
    background: #FFFFFF !important;
    color: #172622 !important;
    border-color: #CFE3DB !important;
}

div[data-testid="stTextInput"] input::placeholder,
textarea::placeholder {
    color: #758B83 !important;
    opacity: 1 !important;
}

div[data-testid="stFileUploader"] section {
    background: #FFFFFF !important;
    border-color: #CFE3DB !important;
    color: #172622 !important;
}

div[data-testid="stFileUploader"] section *,
div[data-testid="stFileUploader"] small,
div[data-testid="stFileUploader"] p {
    color: #314D44 !important;
}

.stTabs [data-baseweb="tab"] {
    color: #314D44 !important;
    font-weight: 700;
}

.stTabs [aria-selected="true"] {
    color: #1F6F5B !important;
}

.patient-helper {
    margin: .35rem 0 1rem;
    padding: .72rem .85rem;
    border-radius: 10px;
    background: #F1FAF6;
    border: 1px solid #DCEBE5;
    color: #314D44;
    font-size: .85rem;
    line-height: 1.45;
}

.patient-helper strong {
    color: #172622;
}


/* Final contrast/accessibility overrides */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
textarea,
input {
    caret-color: #061B16 !important;
}

section[data-testid="stSidebar"] .doctor-avatar,
section[data-testid="stSidebar"] .doctor-avatar * {
    background: #FFFFFF !important;
    color: #061B16 !important;
    font-weight: 950 !important;
    text-shadow: none !important;
}

section[data-testid="stSidebar"] .stButton button,
section[data-testid="stSidebar"] .stButton button * {
    background: #F7FFFB !important;
    color: #061B16 !important;
    border-color: rgba(185,220,209,.70) !important;
    font-weight: 850 !important;
}

section[data-testid="stSidebar"] .stButton button:hover,
section[data-testid="stSidebar"] .stButton button:hover * {
    background: #DFF7EC !important;
    color: #061B16 !important;
    border-color: #45C08B !important;
}

section[data-testid="stSidebar"] .stButton button:focus,
section[data-testid="stSidebar"] .stButton button:active,
section[data-testid="stSidebar"] .stButton button:focus *,
section[data-testid="stSidebar"] .stButton button:active * {
    color: #061B16 !important;
}

/* Streamlit uploader file rows can inherit dark theme colors; force readable chips. */
div[data-testid="stFileUploader"] section {
    background: #FFFFFF !important;
    border-color: #BFD9D0 !important;
    color: #172622 !important;
}

div[data-testid="stFileUploader"] section * {
    color: #172622 !important;
}

div[data-testid="stFileUploaderFile"],
div[data-testid="stFileUploaderFile"] > div,
div[data-testid="stFileUploaderFile"] span,
div[data-testid="stFileUploaderFile"] small,
div[data-testid="stFileUploaderFileName"],
div[data-testid="stFileUploaderFileSize"] {
    background: #173B33 !important;
    color: #FFFFFF !important;
    border-color: #2D7A63 !important;
}

div[data-testid="stFileUploaderFile"] button,
div[data-testid="stFileUploaderFile"] button * {
    color: #FFFFFF !important;
}

[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stCaptionContainer"],
.stCaptionContainer {
    color: #314D44;
}

hr { margin: 1.25rem 0; }
</style>
""", unsafe_allow_html=True)

# ── Session state init ────────────────────────────────────────
DEFAULTS = {
    "token": None, "user_id": None, "user_name": None,
    "page": "login", "current_conv_id": None, "current_note_id": None,
    "confirm_approve": False, "save_feedback": None, "quality_warnings": []
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── API helpers ───────────────────────────────────────────────
def _hdrs():
    return {"Authorization": f"Bearer {st.session_state.token}"}

def _post(ep, data=None, files=None):
    try:
        kw = dict(headers=_hdrs(), timeout=300)
        if files:
            kw["data"] = data
            kw["files"] = files
        else:
            kw["json"] = data
        r = requests.post(f"{API_BASE}{ep}", **kw)
        return r.json(), r.status_code
    except Exception as e:
        return {"detail": str(e)}, 500

def _get(ep):
    try:
        r = requests.get(f"{API_BASE}{ep}", headers=_hdrs(), timeout=30)
        return r.json(), r.status_code
    except Exception as e:
        return {"detail": str(e)}, 500

def _put(ep, data):
    try:
        r = requests.put(f"{API_BASE}{ep}", headers=_hdrs(), json=data, timeout=30)
        return r.json(), r.status_code
    except Exception as e:
        return {"detail": str(e)}, 500

def goto(page):
    st.session_state.page = page
    st.session_state.confirm_approve = False
    st.session_state.save_feedback   = None
    st.rerun()

# ── Confidence badge ──────────────────────────────────────────
def doctor_initials(name):
    parts = [p for p in str(name or "Doctor").strip().split() if p]
    if not parts:
        return "DR"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def cbadge(label, score):
    cls = {
        "HIGH": "badge-high",
        "MEDIUM": "badge-medium",
        "LOW": "badge-low",
        "NOT_DOCUMENTED": "badge-nd",
        "UNKNOWN": "badge-nd",
    }.get(label, "badge-nd")

    score_str = f" {score:.2f}" if isinstance(score, float) and score >= 0 else ""
    label_text = str(label or "UNKNOWN").replace("_", " ")
    return f'<span class="{cls}">{label_text}{score_str}</span>'


def confidence_meter(title, label, score):
    try:
        pct = max(0, min(100, int(float(score) * 100)))
    except Exception:
        pct = 0

    if label == "HIGH":
        fill_cls = "conf-high"
    elif label == "MEDIUM":
        fill_cls = "conf-medium"
    elif label == "LOW":
        fill_cls = "conf-low"
    else:
        fill_cls = "conf-nd"

    return f"""
    <div class="confidence-item">
        <div class="confidence-top">
            <div class="confidence-title">{title}</div>
            {cbadge(label, score)}
        </div>
        <div class="confidence-track">
            <div class="confidence-fill {fill_cls}" style="width:{pct}%"></div>
        </div>
    </div>
    """


def empty_state(icon, title, copy):
    return f"""
    <div class="empty-state">
        <div class="empty-icon">{icon}</div>
        <div class="empty-title">{title}</div>
        <div class="empty-copy">{copy}</div>
    </div>
    """
def sidebar():
    with st.sidebar:
        initials = doctor_initials(st.session_state.user_name)

        st.markdown(f"""
        <div class="sidebar-brand">
            <div class="brand-row">
                <div class="brand-mark">M</div>
                <div>
                    <div class="brand-name">MediScribe</div>
                    <div class="brand-sub">Clinical documentation</div>
                </div>
            </div>
        </div>

        <div class="doctor-card">
            <div class="doctor-avatar">{initials}</div>
            <div>
                <div class="doctor-name">Dr. {st.session_state.user_name}</div>
                <div class="doctor-role">Review workspace</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Dashboard", use_container_width=True): goto("dashboard")
        if st.button("New Consultation", use_container_width=True): goto("upload")
        if st.button("History", use_container_width=True): goto("history")
        st.divider()
        if st.button("Logout", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()


# PAGE: LOGIN / REGISTER
# ════════════════════════════════════════════════════════════════
def page_login():
    c1, c2, c3 = st.columns([1, 1.8, 1])
    with c2:
        st.markdown("<div class='page-title' style='text-align:center;margin-top:2rem'>🏥 MediScribe</div>", unsafe_allow_html=True)
        st.markdown("<div class='page-sub' style='text-align:center'>Privacy-first AI clinical documentation</div>", unsafe_allow_html=True)

        t1, t2 = st.tabs(["Login", "Register"])

        with t1:
            email = st.text_input("Email", placeholder="doctor@hospital.org", key="li_email")
            pw    = st.text_input("Password", type="password", placeholder="Enter your password", key="li_pw")
            if st.button("Login", use_container_width=True, type="primary", key="li_btn"):
                if email and pw:
                    resp, code = _post("/api/auth/login", {"email": email, "password": pw})
                    if code == 200:
                        st.session_state.token     = resp["access_token"]
                        st.session_state.user_id   = resp["user_id"]
                        st.session_state.user_name = resp["full_name"]
                        st.session_state.page      = "dashboard"
                        st.rerun()
                    else:
                        st.error(resp.get("detail", "Login failed"))
                else:
                    st.warning("Enter email and password")

        with t2:
            name  = st.text_input("Full Name", placeholder="Dr. Ananya Rao", key="rg_name")
            remail= st.text_input("Email", placeholder="doctor@hospital.org", key="rg_email")
            rpw   = st.text_input("Password", type="password", placeholder="Create a secure password", key="rg_pw")
            if st.button("Create Account", use_container_width=True, type="primary", key="rg_btn"):
                if name and remail and rpw:
                    resp, code = _post("/api/auth/register",
                                       {"email": remail, "password": rpw, "full_name": name})
                    if code == 200:
                        st.session_state.token     = resp["access_token"]
                        st.session_state.user_id   = resp["user_id"]
                        st.session_state.user_name = resp["full_name"]
                        st.session_state.page      = "dashboard"
                        st.rerun()
                    else:
                        st.error(resp.get("detail", "Registration failed"))
                else:
                    st.warning("Fill all fields")


# ════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD — dynamic metrics
# ════════════════════════════════════════════════════════════════
def page_dashboard():
    sidebar()

    st.markdown("<div class='page-title'>Dashboard</div>", unsafe_allow_html=True)
    st.markdown("<div class='page-sub'>Your consultation overview</div>", unsafe_allow_html=True)

    # Fetch real data using authenticated user's ID
    uid = st.session_state.user_id
    resp, code = _get(f"/api/notes/history/{uid}")

    history = resp.get("history", []) if code == 200 else []

    # Compute real metrics
    total          = len(history)
    approved_list  = [h for h in history if h.get("status") == "approved"]
    pending_list   = [h for h in history if h.get("status") != "approved"]
    total_approved = len(approved_list)
    total_pending  = len(pending_list)

    # Unique patients
    unique_patients = len(set(h.get("patient_code", "") for h in history))

    # Notes this week
    now = datetime.now(timezone.utc)
    week_notes = 0
    for h in history:
        try:
            created_str = h.get("created_at", "")
            if created_str:
                # Handle both with and without timezone info
                if created_str.endswith("Z"):
                    created_str = created_str.replace("Z", "+00:00")
                created = datetime.fromisoformat(created_str)
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if (now - created).days <= 7:
                    week_notes += 1
        except Exception:
            pass

    # Average review time — if approved_at and created_at both exist
    review_times = []
    for h in approved_list:
        try:
            c = h.get("created_at", "")
            a = h.get("approved_at", "")
            if c and a:
                if c.endswith("Z"): c = c.replace("Z", "+00:00")
                if a.endswith("Z"): a = a.replace("Z", "+00:00")
                cd = datetime.fromisoformat(c)
                ad = datetime.fromisoformat(a)
                if cd.tzinfo is None: cd = cd.replace(tzinfo=timezone.utc)
                if ad.tzinfo is None: ad = ad.replace(tzinfo=timezone.utc)
                mins = (ad - cd).total_seconds() / 60
                if 0 < mins < 1440:  # ignore > 24hr outliers
                    review_times.append(mins)
        except Exception:
            pass
    avg_review = f"{sum(review_times)/len(review_times):.0f} min" if review_times else "—"

    # Render metric cards
    def metric_card(label, value, delta=""):
        delta_html = f"<div class='metric-delta'>{delta}</div>" if delta else ""
        return f"""
        <div class='metric-card'>
            <div class='metric-accent'></div>
            <div class='metric-label'>{label}</div>
            <div class='metric-value'>{value}</div>
            {delta_html}
        </div>"""

    row1 = st.columns(3)
    row2 = st.columns(3)

    with row1[0]:
        st.markdown(metric_card("Total SOAP Notes", total, "All time"), unsafe_allow_html=True)
    with row1[1]:
        st.markdown(metric_card("Pending Review", total_pending,
                                "Awaiting approval" if total_pending else "All caught up ✓"),
                    unsafe_allow_html=True)
    with row1[2]:
        st.markdown(metric_card("Approved Notes", total_approved,
                                f"{(total_approved/total*100):.0f}% approval rate" if total else "—"),
                    unsafe_allow_html=True)
    with row2[0]:
        st.markdown(metric_card("Total Patients", unique_patients, "Unique patient codes"),
                    unsafe_allow_html=True)
    with row2[1]:
        st.markdown(metric_card("This Week", week_notes, "Notes generated"),
                    unsafe_allow_html=True)
    with row2[2]:
        st.markdown(metric_card("Avg Review Time", avg_review, "From generate → approve"),
                    unsafe_allow_html=True)

    st.divider()

    # Recent 5 notes
    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.subheader("Recent Consultations")
    with col_btn:
        if st.button("View All →", use_container_width=True):
            goto("history")

    if not history:
        st.markdown(empty_state("+", "No consultations yet", "Start a new recording to generate your first SOAP note."), unsafe_allow_html=True)
    else:
        for item in history[:5]:
            status = item.get("status", "unknown")
            badge = "approved" if status == "approved" else "pending"
            created = str(item.get("created_at", ""))[:10]
            conv_id = item["conversation_id"]

            st.markdown(f"""
            <div class="history-card">
                <div class="history-title">{item.get('patient_code', '—')}</div>
                <div class="history-meta">Created {created}</div>
                <div style="margin-top:.65rem;">
                    <span class="s-{badge}">{status.upper()}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("Open", key=f"dash_open_{conv_id}", use_container_width=True):
                st.session_state.current_conv_id = conv_id
                goto("view_note")
    st.markdown("")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button("🎙️ Start New Consultation", use_container_width=True, type="primary"):
            goto("upload")


# ════════════════════════════════════════════════════════════════
# PAGE: UPLOAD
# ════════════════════════════════════════════════════════════════
def page_upload():
    sidebar()
    st.markdown("<div class='page-title'>🎙️ New Consultation</div>", unsafe_allow_html=True)
    st.markdown("<div class='page-sub'>Upload audio to generate a SOAP note</div>", unsafe_allow_html=True)

    col_main, col_guide = st.columns([2.5, 1])

    with col_main:
        st.markdown("""
        <div class='privacy-box'>
        <p><strong>🔒 Privacy Architecture Active</strong></p>
        <p>✅ Audio transcribed on-device by Whisper — never uploaded to cloud</p>
        <p>✅ Patient identity stripped by Microsoft Presidio before AI sees any text</p>
        <p>✅ Only anonymous medical facts sent to Gemini for SOAP generation</p>
        <p>✅ Patient identity restored locally after note is generated</p>
        </div>
        """, unsafe_allow_html=True)

        patient_code = st.text_input(
            "Patient Code",
            placeholder="PT-2024-001, HOSP12345, or P001",
            help="Enter the hospital's unique patient identifier. Do not use the patient's real name."
        )
        st.markdown(
            """
            <div class="patient-helper">
                <strong>What should I enter?</strong><br>
                Enter your hospital's unique patient identifier. Examples: PT-2024-001, HOSP12345, P001.
            </div>
            """,
            unsafe_allow_html=True
        )
        audio_file = st.file_uploader(
            "Upload Consultation Audio",
            type=["wav", "mp3", "ogg", "m4a", "mp4"],
        )
        if audio_file:
            st.audio(audio_file)
            st.caption(f"{audio_file.name} · {audio_file.size/1024:.1f} KB")

    with col_guide:
        st.markdown("**How it works**")
        steps = [
            ("🎙️", "Step 1", "Whisper transcribes audio locally"),
            ("🔒", "Step 2", "Presidio strips patient identity"),
            ("🧠", "Step 3", "Gemini generates SOAP from anonymous text"),
            ("👨‍⚕️", "Step 4", "You review, edit, and approve"),
        ]
        for icon, label, desc in steps:
            st.markdown(f"**{icon} {label}**")
            st.caption(desc)
            st.markdown("")

    st.divider()

    can_submit = bool(audio_file and patient_code and patient_code.strip())

    if st.button("Generate SOAP Note", disabled=not can_submit,
                 use_container_width=True, type="primary"):
        prog = st.progress(0)
        status_el = st.empty()

        status_el.info("Step 1/4 — Transcribing audio locally with Whisper...")
        prog.progress(15)

        files = {
            "file": (
                audio_file.name,
                audio_file.getvalue(),
                audio_file.type
            )
        }

    

        r = requests.post(
            f"{LOCAL_API}/api/upload-audio",
            headers={
                "Authorization": f"Bearer {st.session_state.token}"
            },
            data={
                "patient_code": patient_code
            },
            files=files,
            timeout=300
        )

        resp = r.json()
        code = r.status_code

        prog.progress(90)

        if code == 200:
            prog.progress(100)
            status_el.success("SOAP note generated successfully. Opening review page...")

            st.session_state.current_conv_id = resp["conversation_id"]
            st.session_state.quality_warnings = resp.get("quality_warnings") or []
            st.session_state.page = "view_note"
            st.rerun()
        else:
            prog.progress(0)
            status_el.error(f"❌ {resp.get('detail', 'Processing failed')}")
            if "quality" in str(resp.get("detail", "")).lower():
                st.info("Try re-recording with clear pauses between speakers and minimal background noise.")


# ════════════════════════════════════════════════════════════════
# PAGE: VIEW / EDIT SOAP — sticky panel + pre-fill + modal + auto-refresh
# ════════════════════════════════════════════════════════════════
def page_view_note():
    sidebar()

    conv_id = st.session_state.current_conv_id
    if not conv_id:
        st.error("No consultation selected.")
        if st.button("← Back to Dashboard"):
            goto("dashboard")
        return

    # ── Fetch note ────────────────────────────────────────────
    with st.spinner("Loading note..."):
        resp, code = _get(f"/api/notes/{conv_id}")

    if code != 200:
        st.error(f"Could not load note: {resp.get('detail','Unknown')}")
        return

    note_id     = resp["note_id"]
    soap        = resp["soap"]
    conf_scores = resp.get("confidence_scores", {})
    conf_labels = resp.get("confidence_labels", {})
    note_status = resp.get("status", "pending_review")

    st.session_state.current_note_id = note_id

    st.markdown("<div class='page-title'>📋 SOAP Note Review</div>", unsafe_allow_html=True)
    st.markdown("<div class='page-sub'>Review the AI-generated note. Edit any section. Approve when complete.</div>", unsafe_allow_html=True)

    if note_status == "approved":
        st.success("✅ This note has been approved and saved permanently.")
    else:
        st.info("⏳ Pending your review. Edit any section, then approve.")

    for warning in st.session_state.get("quality_warnings", []):
        st.warning(f"⚠️ {warning}")
    st.session_state.quality_warnings = []

    # ── Save feedback banner ──────────────────────────────────
    if st.session_state.save_feedback == "success":
        st.success("💾 Changes saved successfully. Note refreshed.")
        st.session_state.save_feedback = None
    elif st.session_state.save_feedback == "error":
        st.error("Save failed. Please try again.")
        st.session_state.save_feedback = None

    # ── Approval confirmation modal ───────────────────────────
    if st.session_state.confirm_approve:
        st.markdown("""
        <div class='modal-box'>
        <div class='modal-title'>Confirm Approval</div>
        <div class='modal-body'>
        Are you sure you want to approve this note?<br>
        This action marks the clinical review as complete and saves the note permanently.
        It cannot be undone.
        </div>
        </div>
        """, unsafe_allow_html=True)

        mc1, mc2, mc3 = st.columns([2, 1, 1])
        with mc2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.confirm_approve = False
                st.rerun()
        with mc3:
            if st.button("✅ Approve", use_container_width=True, type="primary"):
                ar, ac = _post(f"/api/notes/{note_id}/approve",
                               {"doctor_name": st.session_state.user_name})
                st.session_state.confirm_approve = False
                if ac == 200:
                    st.balloons()
                    st.rerun()
                else:
                    st.error(f"Approval failed: {ar.get('detail','Unknown')}")
        st.divider()

    # ── Main layout: editor left, sticky confidence right ─────
    col_edit, col_conf = st.columns([3, 1])

    # ── Right: sticky confidence panel ───────────────────────
    with col_conf:
        st.markdown("<div class='sticky-confidence'>", unsafe_allow_html=True)
        st.markdown("<div class='confidence-shell'>", unsafe_allow_html=True)
        st.markdown("**Confidence Scores**")
        st.caption("Transcript alignment by SOAP section")
        st.divider()

        section_meta = {
            "subjective": "Subjective",
            "objective": "Objective",
            "assessment": "Assessment",
            "plan": "Plan",
        }
        for sec, title in section_meta.items():
            label = conf_labels.get(sec, "UNKNOWN")
            score = conf_scores.get(sec, 0)
            st.markdown(confidence_meter(title, label, score), unsafe_allow_html=True)
            if label == "LOW":
                st.caption("Verify this section against the transcript.")
            elif label == "NOT_DOCUMENTED":
                st.caption("Complete this section manually.")

        st.divider()
        st.caption("High >= 0.75 · Medium >= 0.50 · Low < 0.50")
        st.markdown("</div></div>", unsafe_allow_html=True)

    # ── Left: SOAP editor, pre-filled from DB ─────────────────
    with col_edit:
        st.markdown("**SOAP Note Editor**")
        st.caption("All sections are pre-filled with AI-generated content. Edit only what needs changing.")

        fields = {}
        soap_defs = [
            ("subjective", "S — Subjective", 160),
            ("objective",  "O — Objective",  130),
            ("assessment", "A — Assessment", 110),
            ("plan",       "P — Plan",       130),
        ]
        for key, label, h in soap_defs:
            l_val  = conf_labels.get(key, "UNKNOWN")
            s_val  = conf_scores.get(key, 0)
            st.markdown(
                f"<div class='soap-label'>{label} &nbsp; {cbadge(l_val, s_val)}</div>",
                unsafe_allow_html=True
            )
            # value= pre-fills the textarea with existing DB content
            fields[key] = st.text_area(
                label=f"_{key}",
                value=soap.get(key, ""),
                height=h,
                label_visibility="collapsed",
                key=f"field_{key}_{note_id}"
            )

        st.divider()

        btn1, btn2 = st.columns(2)

        # Save Changes — auto-refresh after save
        with btn1:
            if st.button("💾 Save Changes", use_container_width=True):
                r, c = _put(f"/api/notes/{note_id}", {
                    "subjective": fields["subjective"],
                    "objective":  fields["objective"],
                    "assessment": fields["assessment"],
                    "plan":       fields["plan"],
                })
                if c == 200:
                    st.session_state.save_feedback = "success"
                    # Auto-refresh: rerun so page re-fetches updated content from DB
                    st.rerun()
                else:
                    st.session_state.save_feedback = "error"
                    st.rerun()

        # Approve — shows confirmation modal first
        with btn2:
            if note_status != "approved":
                if st.button("✅ Approve Note", use_container_width=True, type="primary"):
                    # Save first, then open modal
                    _put(f"/api/notes/{note_id}", {
                        "subjective": fields["subjective"],
                        "objective":  fields["objective"],
                        "assessment": fields["assessment"],
                        "plan":       fields["plan"],
                    })
                    st.session_state.confirm_approve = True
                    st.rerun()
            else:
                st.button("✅ Already Approved", disabled=True, use_container_width=True)


# ════════════════════════════════════════════════════════════════
# PAGE: HISTORY — search, filter, sort, pagination
# ════════════════════════════════════════════════════════════════
def page_history():
    sidebar()

    st.markdown("<div class='page-title'>📁 Consultation History</div>", unsafe_allow_html=True)
    st.markdown("<div class='page-sub'>All your consultations — search, filter, and export</div>", unsafe_allow_html=True)

    # Fetch using authenticated user's ID
    uid = st.session_state.user_id
    resp, code = _get(f"/api/notes/history/{uid}")
    history = resp.get("history", []) if code == 200 else []

    if code != 200:
        st.error("Could not load history.")
        return

    if not history:
        st.markdown(empty_state("⌁", "No consultation history", "Completed and pending SOAP notes will appear here."), unsafe_allow_html=True)
        if st.button("🎙️ Start First Recording", type="primary"):
            goto("upload")
        return

    # ── Controls row ─────────────────────────────────────────
    fc1, fc2, fc3, fc4 = st.columns([3, 2, 2, 2])

    with fc1:
        search = st.text_input("🔍 Search by patient code", placeholder="e.g. PT-2024")
    with fc2:
        status_filter = st.selectbox("Status", ["All", "Approved", "Pending Review"])
    with fc3:
        sort_by = st.selectbox("Sort", ["Newest First", "Oldest First"])
    with fc4:
        page_size = st.selectbox("Per page", [5, 10, 20], index=0)

    # ── Apply filters ─────────────────────────────────────────
    filtered = history

    if search.strip():
        q = search.strip().lower()
        filtered = [h for h in filtered if q in h.get("patient_code", "").lower()]

    if status_filter == "Approved":
        filtered = [h for h in filtered if h.get("status") == "approved"]
    elif status_filter == "Pending Review":
        filtered = [h for h in filtered if h.get("status") != "approved"]

    if sort_by == "Oldest First":
        filtered = list(reversed(filtered))

    # ── Pagination ────────────────────────────────────────────
    total_filtered = len(filtered)
    total_pages    = max(1, (total_filtered + page_size - 1) // page_size)

    if "hist_page" not in st.session_state:
        st.session_state.hist_page = 1
    if st.session_state.hist_page > total_pages:
        st.session_state.hist_page = 1

    start = (st.session_state.hist_page - 1) * page_size
    end   = start + page_size
    page_items = filtered[start:end]

    st.caption(f"Showing {start+1}–{min(end, total_filtered)} of {total_filtered} consultations")
    st.divider()

    # ── Render rows ───────────────────────────────────────────
    if not page_items:
        st.markdown(empty_state("⌕", "No matching consultations", "Try adjusting the patient code search or status filter."), unsafe_allow_html=True)
    else:
        for item in page_items:
            status = item.get("status", "unknown")
            badge_cls = "s-approved" if status == "approved" else "s-pending"
            created = str(item.get("created_at", ""))[:10]
            conv_id = item["conversation_id"]

            st.markdown(f"""
            <div class="history-card">
                <div style="display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;">
                    <div>
                        <div class="history-title">{item.get('patient_code', '—')}</div>
                        <div class="history-meta">Created {created}</div>
                    </div>
                    <span class="{badge_cls}">{status.upper()}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            hc1, hc2, hc3 = st.columns([1, 1, 4])

            with hc1:
                if st.button("Open", key=f"h_open_{conv_id}", use_container_width=True):
                    st.session_state.current_conv_id = conv_id
                    goto("view_note")

            with hc2:
                # Download note as plain text
                note_resp, note_code = _get(f"/api/notes/{conv_id}")
                if note_code == 200:
                    s = note_resp.get("soap", {})
                    txt = f"""MEDISCRIBE — CLINICAL NOTE
Patient Code : {item.get('patient_code','—')}
Date         : {created}
Status       : {status.upper()}

SUBJECTIVE:
{s.get('subjective','')}

OBJECTIVE:
{s.get('objective','')}

ASSESSMENT:
{s.get('assessment','')}

PLAN:
{s.get('plan','')}

---
Generated by MediScribe | Privacy: on-device STT, PII anonymization, HIPAA Safe Harbor
"""
                    st.download_button(
                        "Download", data=txt,
                        file_name=f"SOAP_{item.get('patient_code','note')}_{created}.txt",
                        mime="text/plain",
                        key=f"dl_{conv_id}",
                        use_container_width=True
                    )
    # ── Pagination controls ───────────────────────────────────
    if total_pages > 1:
        pg1, pg2, pg3 = st.columns([1, 2, 1])
        with pg1:
            if st.button("← Previous", disabled=st.session_state.hist_page <= 1,
                         use_container_width=True):
                st.session_state.hist_page -= 1
                st.rerun()
        with pg2:
            st.markdown(
                f"<div style='text-align:center;padding-top:0.5rem;color:#7A9B90;font-size:0.85rem'>"
                f"Page {st.session_state.hist_page} of {total_pages}</div>",
                unsafe_allow_html=True
            )
        with pg3:
            if st.button("Next →", disabled=st.session_state.hist_page >= total_pages,
                         use_container_width=True):
                st.session_state.hist_page += 1
                st.rerun()


# ════════════════════════════════════════════════════════════════
# ROUTER
# ════════════════════════════════════════════════════════════════
def main():
    if not st.session_state.token:
        page_login()
        return
    p = st.session_state.page
    if   p == "dashboard":  page_dashboard()
    elif p == "upload":     page_upload()
    elif p == "view_note":  page_view_note()
    elif p == "history":    page_history()
    else:                   page_dashboard()

if __name__ == "__main__":
    main()




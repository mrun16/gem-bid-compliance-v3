import base64
import os
import re
from datetime import datetime

import streamlit as st

from api_client import SendaAPI, APIError

# ---------------------------------------------------------------------------
# BACKEND URL — resolution order:
#   1. Streamlit Cloud secrets  (st.secrets["BACKEND_URL"])
#   2. Environment variable     (BACKEND_URL=https://...)
#   3. Local dev fallback       (http://127.0.0.1:8000)
# ---------------------------------------------------------------------------
def _resolve_backend_url() -> str:
    try:
        url = st.secrets.get("BACKEND_URL", "")
        if url:
            return url.rstrip("/")
    except Exception:
        pass
    return os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")

BACKEND_URL = _resolve_backend_url()
MAX_MB = 50
MAX_BYTES = MAX_MB * 1024 * 1024

if "theme" not in st.session_state:
    st.session_state["theme"] = "light"



if "nav_page" not in st.session_state:
    st.session_state["nav_page"] = "Overview"

st.set_page_config(
    page_title="SendaTender — Procurement Verification Workspace",
    page_icon="ST",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Theme marker used by the CSS to follow the in-app Light/Dark toggle
if st.session_state.get("theme") == "dark":
    st.markdown(
        '<div class="theme-dark-marker" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="theme-light-marker" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )

# -----------------------------------------------------------------------------
# DESIGN SYSTEM & STYLES (Light & Dark Themes)
# -----------------------------------------------------------------------------
st.markdown("""
<style>

.india-accent {
    width: 100%;
    height: 4px;
    display: flex;
    overflow: hidden;
    border-radius: 0 0 3px 3px;
    margin-bottom: 10px;
}

.india-accent .saffron {
    flex: 1;
    background: #F6D8C2;
}

.india-accent .white {
    flex: 1;
    background: #F7F8F9;
}

.india-accent .green {
    flex: 1;
    background: #D7E9DC;
}

/* ===== DESIGN TOKENS ===== */
:root {
  --navy: #17324D;
  --blue: #2F6FED;
  --blue-hover: #245BC7;
  --teal: #168F83;

  --bg: #F3F6FA;
  --card: #FFFFFF;

  --border: #E1E7EF;
  --muted: #6C7C8E;
  --subtext: #5D6E80;
}

html, body, [class*="css"] {
  font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

/* ===== LIGHT MODE BASE (explicit — guarantees readable text on Streamlit Cloud) ===== */
.stApp {
  background: #F3F6FA !important;
  color: #17324D !important;
}
.block-container { max-width: 1420px; padding-top: 1.8rem; padding-bottom: 3rem; color: #17324D !important; }

/* Headings & body text */
h1, h2, h3, h4, h5, h6 { color: #17324D !important; }
p, span, div, li { color: inherit; }

/* Streamlit-generated labels, captions, markdown */
.stMarkdown, .stMarkdown p, .stMarkdown span, .stMarkdown li,
.stText, label, .stCaption, [data-testid="stCaptionContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span {
  color: #17324D !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
  background: #FFFFFF !important;
  border-right: 1px solid #DCE5EE !important;
}
[data-testid="stSidebar"] .block-container { padding: 1.2rem 1rem; }
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] p {
  color: #17324D !important;
}

/* Inputs */
.stTextInput input, .stTextArea textarea {
  background: #FFFFFF !important;
  color: #17324D !important;
  border-color: #DCE5EE !important;
}
.stTextInput input::placeholder, .stTextArea textarea::placeholder {
  color: #9BAFC0 !important;
}

/* Selectbox / Radio / Toggle */
.stSelectbox div[data-baseweb="select"] > div {
  background: #FFFFFF !important;
  color: #17324D !important;
  border-color: #DCE5EE !important;
}
.stRadio label, .stCheckbox label, .stToggle label {
  color: #17324D !important;
}

/* Metrics */
[data-testid="stMetric"] { color: #17324D !important; }
[data-testid="stMetricLabel"] { color: #738294 !important; }
[data-testid="stMetricValue"] { color: #17324D !important; }

/* Alerts / Info boxes */
.stAlert, .stInfo, .stWarning, .stError, .stSuccess {
  color: #17324D !important;
}

/* Tables */
[data-testid="stDataFrame"] { color: #17324D !important; }

/* File uploader */
div[data-testid="stFileUploader"] {
  background: #FFFFFF;
  border: 1px dashed #CBD5E1;
  border-radius: 16px;
  padding: 10px;
  color: #17324D !important;
}

/* Brand Logo */
.brand { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }
.brand-mark {
  width: 40px; height: 40px; border-radius: 12px;
  background: linear-gradient(135deg, #0F9D8A 0%, #2563EB 100%);
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; color: #FFFFFF; font-size: 1.15rem;
  box-shadow: 0 4px 12px rgba(37,99,235,0.22);
}
.brand-name { font-size: 1.32rem; font-weight: 800; color: var(--navy); letter-spacing: -0.5px; }
.brand-name span { color: var(--teal); }
.subbrand { color: #8494A5; font-size: 0.76rem; font-weight: 700; margin: 0 0 20px 52px; letter-spacing: 0.4px; }

/* Hero Section */
.hero {
  background: linear-gradient(135deg, #F0F8FC 0%, #EAF5F6 100%);
  border: 1px solid #DCEBED;
  border-radius: 24px;
  padding: 36px 42px;
  margin-bottom: 24px;
  position: relative;
  overflow: hidden;
}
.eyebrow {
  display: inline-block;
  background: #E5EEFF;
  color: #1E5AD7;
  border-radius: 999px;
  padding: 6px 14px;
  font-weight: 750;
  font-size: 0.78rem;
  letter-spacing: 0.3px;
}
.hero h1 {
  color: var(--navy);
  font-size: 2.7rem;
  line-height: 1.12;
  margin: 18px 0 12px;
  font-weight: 800;
  letter-spacing: -1.2px;
}
.hero p {
  color: var(--subtext);
  font-size: 1.05rem;
  line-height: 1.6;
  max-width: 680px;
  margin-bottom: 22px;
}

/* Metric Cards */
.metric-card {
  background: #FFFFFF;
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 22px 24px;
  min-height: 124px;
  box-shadow: 0 4px 18px rgba(31, 55, 82, 0.06);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 22px rgba(31, 55, 82, 0.09);
}
.metric-label {
  color: #738294;
  font-size: 0.75rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.7px;
}
.metric-value {
  color: var(--navy);
  font-size: 2.2rem;
  font-weight: 800;
  margin-top: 8px;
  line-height: 1.1;
}
.metric-help {
  color: #2BA88F;
  font-size: 0.82rem;
  font-weight: 600;
  margin-top: 6px;
}

/* Section Titles */
.section-title {
  color: var(--navy);
  font-size: 1.38rem;
  font-weight: 800;
  margin: 28px 0 14px;
  letter-spacing: -0.4px;
}

/* 3-Step Workflow Cards */
.workflow {
  background: #FFFFFF;
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 24px;
  min-height: 165px;
  box-shadow: 0 4px 18px rgba(31, 55, 82, 0.06);
  transition: transform 0.15s ease;
}
.workflow:hover { transform: translateY(-2px); }
.step {
  display: inline-flex;
  width: 36px; height: 36px;
  align-items: center; justify-content: center;
  border-radius: 10px;
  font-weight: 800;
  font-size: 1rem;
  margin-bottom: 14px;
}
.step-1 { background: #E9F0FF; color: #2563EB; }
.step-2 { background: #E5F7F0; color: #087A5E; }
.step-3 { background: #FFF4E5; color: #D97706; }
.workflow h4 {
  color: var(--navy);
  margin: 0 0 8px;
  font-size: 1.08rem;
  font-weight: 750;
}
.workflow p {
  color: #6A7B8D;
  font-size: 0.91rem;
  line-height: 1.55;
  margin: 0;
}

/* Status Pills */
.status-pill {
  display: inline-block;
  border-radius: 999px;
  padding: 4px 11px;
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0.3px;
  text-transform: uppercase;
}
.status-pass { background: #E5F7F0; color: #087A5E; }
.status-fail { background: #FDEBEC; color: #B4232F; }
.status-review { background: #FFF3DB; color: #A76400; }
.status-neutral { background: #EDF1F5; color: #617183; }

/* Findings Cards */
.finding {
  background: #FFFFFF;
  border: 1px solid var(--border);
  border-left: 6px solid #C8D4E0;
  border-radius: 14px;
  padding: 18px 20px;
  margin: 12px 0;
  box-shadow: 0 2px 6px rgba(0,0,0,0.02);
}
.finding.pass { border-left-color: #10B981; }
.finding.fail { border-left-color: #EF4444; }
.finding.review { border-left-color: #F59E0B; }
.finding.unverifiable { border-left-color: #94A3B8; }

.queue-card {
  background: #FFFFFF;
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 16px 20px;
  margin: 10px 0;
}

.small-muted { color: #748496; font-size: 0.84rem; }

/* Login Page */
.login-wrap { max-width: 480px; margin: 6vh auto; }
.login-card {
  background: #FFFFFF;
  border: 1px solid var(--border);
  border-radius: 24px;
  padding: 36px 38px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.04);
}

/* Buttons and Inputs */
button[kind="primary"] {
  border-radius: 10px !important;
  font-weight: 750 !important;
  letter-spacing: 0.2px !important;

  background: linear-gradient(
    135deg,
    #2F6FED,
    #245BC7
  ) !important;

  color: #FFFFFF !important;
  border: none !important;

  box-shadow:
    0 6px 16px rgba(47, 111, 237, 0.22),
    0 0 12px rgba(47, 111, 237, 0.08) !important;

  transition: all 0.2s ease !important;
}

button[kind="primary"]:hover {
  transform: translateY(-1px);

  box-shadow:
    0 8px 22px rgba(47, 111, 237, 0.28),
    0 0 20px rgba(47, 111, 237, 0.12) !important;
}

button[kind="secondary"] {
  border-radius: 10px !important;
  font-weight: 700 !important;

  background: #FFFFFF !important;
  color: #23405F !important;
  border: 1px solid #D7E0EA !important;

  transition: all 0.2s ease !important;
}

button[kind="secondary"]:hover {
  background: #F7FAFE !important;
  border-color: #9BB6DD !important;
  transform: translateY(-1px);
}
div[data-testid="stFileUploader"] {
  background: #FFFFFF;
  border: 1px dashed #CBD5E1;
  border-radius: 16px;
  padding: 10px;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# DARK THEME OVERRIDE
# -----------------------------------------------------------------------------
if st.session_state.get("theme") == "dark":
 st.markdown("""
<style>

/* =========================================================
   SendaTender V3 — Theme System
   Clean Light + Professional Dark
   ========================================================= */

/* ---------- DESIGN TOKENS ---------- */

:root {
    --navy: #172B4D;
    --blue: #2563EB;
    --blue-hover: #1D4ED8;
    --teal: #0F8F82;

    --bg: #F7F9FC;
    --card: #FFFFFF;
    --card-soft: #F8FAFC;

    --border: #D9E2EC;
    --border-strong: #C5D2E0;

    --text: #172B4D;
    --text-secondary: #526581;
    --muted: #718096;

    --success-bg: #E8F7F1;
    --success-text: #087A5E;

    --danger-bg: #FDECEC;
    --danger-text: #B4232F;

    --warning-bg: #FFF4DD;
    --warning-text: #A76400;

    --neutral-bg: #EEF2F6;
    --neutral-text: #617183;
}


/* =========================================================
   GLOBAL APP
   ========================================================= */

.stApp {
    background: var(--bg) !important;
    color: var(--text) !important;
}

.block-container {
    max-width: 1420px;
    padding-top: 1.8rem;
    padding-bottom: 3rem;
}


/* ---------- GLOBAL TEXT ---------- */

h1, h2, h3, h4, h5, h6 {
    color: var(--text) !important;
}

p, li {
    color: var(--text-secondary);
}

label {
    color: var(--text) !important;
}

[data-testid="stCaptionContainer"] {
    color: var(--muted) !important;
}

[data-testid="stMarkdownContainer"] {
    color: var(--text-secondary);
}


/* =========================================================
   SIDEBAR
   ========================================================= */

[data-testid="stSidebar"] {
    background: #FFFFFF !important;
    border-right: 1px solid var(--border) !important;
}

[data-testid="stSidebar"] * {
    color: var(--text) !important;
}

[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] small {
    color: var(--muted) !important;
}


/* ---------- BRAND ---------- */

.brand {
    display: flex;
    align-items: center;
    gap: 11px;
    margin-top: 4px;
    margin-bottom: 5px;
}

.brand-mark {
    width: 38px;
    height: 38px;
    border-radius: 11px;

    display: flex;
    align-items: center;
    justify-content: center;

    background: linear-gradient(
        135deg,
        #0F8F82 0%,
        #2563EB 100%
    );

    color: #FFFFFF !important;
    font-weight: 850;
    font-size: 15px;

    box-shadow:
        0 5px 14px rgba(37, 99, 235, 0.20);
}

.brand-name {
    color: var(--text) !important;
    font-size: 20px;
    font-weight: 850;
    letter-spacing: -0.4px;
}

.brand-name span {
    color: var(--blue) !important;
}

.subbrand {
    color: var(--muted) !important;
    font-size: 11px;
    font-weight: 650;
    letter-spacing: 0.4px;
    margin-bottom: 18px;
}


/* =========================================================
   HERO
   ========================================================= */

.hero {
    background: linear-gradient(
        135deg,
        #F0F7FF 0%,
        #EDF9F7 100%
    );

    border: 1px solid #D9E8F2;
    border-radius: 24px;

    padding: 36px 42px;
    margin-bottom: 24px;

    box-shadow:
        0 5px 20px rgba(31, 55, 82, 0.05);
}

.eyebrow {
    color: var(--teal) !important;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    margin-bottom: 8px;
}

.hero h1 {
    color: var(--text) !important;
    font-size: 38px;
    line-height: 1.12;
    letter-spacing: -1.2px;
    margin: 0 0 12px 0;
}

.hero p {
    color: var(--text-secondary) !important;
    font-size: 15px;
    line-height: 1.65;
    max-width: 780px;
    margin: 0;
}


/* =========================================================
   SECTION TITLES
   ========================================================= */

.section-title {
    color: var(--text) !important;
    font-size: 18px;
    font-weight: 800;
    margin: 26px 0 12px 0;
}

.section-subtitle {
    color: var(--muted) !important;
    font-size: 13px;
}


/* =========================================================
   METRIC CARDS
   ========================================================= */

.metric-card {
    background: var(--card);

    border: 1px solid var(--border);
    border-radius: 18px;

    padding: 22px 24px;
    min-height: 124px;

    box-shadow:
        0 4px 18px rgba(31, 55, 82, 0.06);

    transition:
        transform 0.2s ease,
        box-shadow 0.2s ease;
}

.metric-card:hover {
    transform: translateY(-2px);

    box-shadow:
        0 8px 22px rgba(31, 55, 82, 0.10);
}

.metric-label {
    color: var(--muted) !important;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.7px;
}

.metric-value {
    color: var(--text) !important;
    font-size: 29px;
    font-weight: 850;
    margin-top: 7px;
}

.metric-help {
    color: var(--muted) !important;
    font-size: 12px;
    margin-top: 4px;
}


/* =========================================================
   WORKFLOW CARDS
   ========================================================= */

.workflow {
    background: var(--card);

    border: 1px solid var(--border);
    border-radius: 18px;

    padding: 24px;
    min-height: 165px;

    box-shadow:
        0 4px 18px rgba(31, 55, 82, 0.06);

    transition:
        transform 0.2s ease,
        box-shadow 0.2s ease;
}

.workflow:hover {
    transform: translateY(-2px);

    box-shadow:
        0 8px 22px rgba(31, 55, 82, 0.10);
}

.workflow-number {
    color: var(--blue) !important;
    font-size: 12px;
    font-weight: 850;
    letter-spacing: 0.8px;
}

.workflow h3 {
    color: var(--text) !important;
    font-size: 17px;
    margin: 9px 0 7px 0;
}

.workflow p {
    color: var(--text-secondary) !important;
    font-size: 13px;
    line-height: 1.55;
}


/* =========================================================
   QUEUE / RECENT VERIFICATION CARDS
   ========================================================= */

.queue-card {
    background: var(--card);

    border: 1px solid var(--border);
    border-radius: 16px;

    padding: 17px 19px;
    margin-bottom: 10px;

    box-shadow:
        0 3px 12px rgba(31, 55, 82, 0.045);
}

.queue-card strong {
    color: var(--text) !important;
}

.small-muted {
    color: var(--muted) !important;
    font-size: 12px;
}


/* =========================================================
   STATUS PILLS
   ========================================================= */

.status-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;

    padding: 4px 10px;
    border-radius: 999px;

    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.2px;
}

.status-pass {
    background: var(--success-bg);
    color: var(--success-text) !important;
}

.status-fail {
    background: var(--danger-bg);
    color: var(--danger-text) !important;
}

.status-review {
    background: var(--warning-bg);
    color: var(--warning-text) !important;
}

.status-neutral {
    background: var(--neutral-bg);
    color: var(--neutral-text) !important;
}


/* =========================================================
   FINDINGS
   ========================================================= */

.finding {
    background: var(--card);

    border: 1px solid var(--border);
    border-radius: 14px;

    padding: 16px 18px;
    margin-bottom: 10px;
}

.finding-title {
    color: var(--text) !important;
    font-weight: 800;
    margin-bottom: 5px;
}

.finding-text {
    color: var(--text-secondary) !important;
    font-size: 13px;
    line-height: 1.55;
}


/* =========================================================
   STREAMLIT INPUTS
   ========================================================= */

div[data-baseweb="input"],
div[data-baseweb="textarea"],
div[data-baseweb="select"] {
    background: var(--card) !important;
}

div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div,
div[data-baseweb="select"] > div {
    background: var(--card) !important;
    border-color: var(--border-strong) !important;
}

input,
textarea {
    color: var(--text) !important;
    background: var(--card) !important;
}

input::placeholder,
textarea::placeholder {
    color: #8A99AA !important;
}


/* ---------- SELECTBOX ---------- */

[data-baseweb="select"] * {
    color: var(--text) !important;
}

[data-baseweb="popover"] {
    background: var(--card) !important;
}

[data-baseweb="menu"] {
    background: var(--card) !important;
}

[data-baseweb="menu"] li {
    color: var(--text) !important;
}


/* ---------- RADIO ---------- */

[data-testid="stRadio"] label {
    color: var(--text) !important;
}


/* =========================================================
   FILE UPLOADER
   ========================================================= */

div[data-testid="stFileUploader"] {
    background: var(--card) !important;

    border: 1px dashed var(--border-strong) !important;
    border-radius: 14px !important;

    padding: 8px !important;
}

div[data-testid="stFileUploader"] * {
    color: var(--text-secondary) !important;
}

div[data-testid="stFileUploader"] small {
    color: var(--muted) !important;
}


/* =========================================================
   BUTTONS
   ========================================================= */

button[kind="primary"] {
    border-radius: 10px !important;

    font-weight: 750 !important;
    letter-spacing: 0.2px !important;

    background: linear-gradient(
        135deg,
        #2F6FED,
        #245BC7
    ) !important;

    color: #FFFFFF !important;

    border: none !important;

    box-shadow:
        0 6px 16px rgba(47, 111, 237, 0.22),
        0 0 12px rgba(47, 111, 237, 0.08) !important;

    transition:
        transform 0.2s ease,
        box-shadow 0.2s ease !important;
}

button[kind="primary"]:hover {
    transform: translateY(-1px);

    box-shadow:
        0 8px 22px rgba(47, 111, 237, 0.30),
        0 0 20px rgba(47, 111, 237, 0.13) !important;
}

button[kind="secondary"] {
    border-radius: 10px !important;

    font-weight: 700 !important;

    background: var(--card) !important;
    color: var(--text) !important;

    border: 1px solid var(--border-strong) !important;

    transition:
        transform 0.2s ease,
        background 0.2s ease,
        border-color 0.2s ease !important;
}

button[kind="secondary"]:hover {
    background: var(--card-soft) !important;
    border-color: #9BB6DD !important;

    transform: translateY(-1px);
}


/* =========================================================
   ALERTS
   ========================================================= */

div[data-testid="stAlert"] {
    border-radius: 12px !important;
}


/* =========================================================
   DATAFRAMES / TABLES
   ========================================================= */

[data-testid="stDataFrame"] {
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    overflow: hidden;
}


/* =========================================================
   DIVIDERS
   ========================================================= */

hr {
    border-color: var(--border) !important;
}


/* =========================================================
   LOGIN
   ========================================================= */

.login-wrap {
    max-width: 480px;
    margin: 60px auto 0 auto;
}

.login-card {
    background: var(--card);

    border: 1px solid var(--border);
    border-radius: 22px;

    padding: 32px;

    box-shadow:
        0 10px 30px rgba(31, 55, 82, 0.08);
}

.login-card h1 {
    color: var(--text) !important;
}

.login-card p {
    color: var(--text-secondary) !important;
}


/* =========================================================
   DARK MODE
   ========================================================= */

@media (prefers-color-scheme: dark) {

    /* =========================================================
   IN-APP DARK MODE
   Controlled by st.session_state["theme"]
   ========================================================= */

.stApp:has(.theme-dark-marker) {
    background: #0F172A !important;
    color: #F8FAFC !important;
}

.stApp:has(.theme-dark-marker) .block-container {
    color: #F8FAFC !important;
}


/* ---------- GLOBAL TEXT ---------- */

.stApp:has(.theme-dark-marker) h1,
.stApp:has(.theme-dark-marker) h2,
.stApp:has(.theme-dark-marker) h3,
.stApp:has(.theme-dark-marker) h4,
.stApp:has(.theme-dark-marker) h5,
.stApp:has(.theme-dark-marker) h6 {
    color: #F8FAFC !important;
}

.stApp:has(.theme-dark-marker) p,
.stApp:has(.theme-dark-marker) li {
    color: #CBD5E1 !important;
}

.stApp:has(.theme-dark-marker) label {
    color: #F8FAFC !important;
}

.stApp:has(.theme-dark-marker) [data-testid="stCaptionContainer"] {
    color: #94A3B8 !important;
}

.stApp:has(.theme-dark-marker) [data-testid="stMarkdownContainer"] {
    color: #CBD5E1 !important;
}


/* =========================================================
   DARK SIDEBAR
   ========================================================= */

.stApp:has(.theme-dark-marker) [data-testid="stSidebar"] {
    background: #111827 !important;
    border-right: 1px solid #334155 !important;
}

.stApp:has(.theme-dark-marker) [data-testid="stSidebar"] * {
    color: #F8FAFC !important;
}

.stApp:has(.theme-dark-marker) [data-testid="stSidebar"] .small-muted,
.stApp:has(.theme-dark-marker) [data-testid="stSidebar"] .stCaption {
    color: #94A3B8 !important;
}


/* =========================================================
   DARK BRAND
   ========================================================= */

.stApp:has(.theme-dark-marker) .brand-name {
    color: #F8FAFC !important;
}

.stApp:has(.theme-dark-marker) .brand-name span {
    color: #60A5FA !important;
}

.stApp:has(.theme-dark-marker) .subbrand {
    color: #94A3B8 !important;
}


/* =========================================================
   DARK HERO
   ========================================================= */

.stApp:has(.theme-dark-marker) .hero {
    background: linear-gradient(
        135deg,
        #172B46 0%,
        #123332 100%
    ) !important;

    border-color: #334155 !important;

    box-shadow:
        0 8px 26px rgba(0, 0, 0, 0.22);
}

.stApp:has(.theme-dark-marker) .eyebrow {
    color: #2DD4BF !important;
}

.stApp:has(.theme-dark-marker) .hero h1 {
    color: #F8FAFC !important;
}

.stApp:has(.theme-dark-marker) .hero p {
    color: #CBD5E1 !important;
}


/* =========================================================
   DARK SECTION TITLES
   ========================================================= */

.stApp:has(.theme-dark-marker) .section-title {
    color: #F8FAFC !important;
}

.stApp:has(.theme-dark-marker) .section-subtitle {
    color: #94A3B8 !important;
}


/* =========================================================
   DARK CARDS
   ========================================================= */

.stApp:has(.theme-dark-marker) .metric-card,
.stApp:has(.theme-dark-marker) .workflow,
.stApp:has(.theme-dark-marker) .queue-card,
.stApp:has(.theme-dark-marker) .finding,
.stApp:has(.theme-dark-marker) .login-card {
    background: #172033 !important;
    border-color: #334155 !important;

    box-shadow:
        0 5px 18px rgba(0, 0, 0, 0.20);
}

.stApp:has(.theme-dark-marker) .metric-card:hover,
.stApp:has(.theme-dark-marker) .workflow:hover {
    box-shadow:
        0 9px 25px rgba(0, 0, 0, 0.28);
}

.stApp:has(.theme-dark-marker) .metric-label {
    color: #94A3B8 !important;
}

.stApp:has(.theme-dark-marker) .metric-value {
    color: #F8FAFC !important;
}

.stApp:has(.theme-dark-marker) .metric-help {
    color: #94A3B8 !important;
}

.stApp:has(.theme-dark-marker) .workflow-number {
    color: #60A5FA !important;
}

.stApp:has(.theme-dark-marker) .workflow h3 {
    color: #F8FAFC !important;
}

.stApp:has(.theme-dark-marker) .workflow p {
    color: #CBD5E1 !important;
}

.stApp:has(.theme-dark-marker) .queue-card strong {
    color: #F8FAFC !important;
}

.stApp:has(.theme-dark-marker) .small-muted {
    color: #94A3B8 !important;
}

.stApp:has(.theme-dark-marker) .finding-title {
    color: #F8FAFC !important;
}

.stApp:has(.theme-dark-marker) .finding-text {
    color: #CBD5E1 !important;
}


/* =========================================================
   DARK INPUTS
   ========================================================= */

.stApp:has(.theme-dark-marker) div[data-baseweb="input"],
.stApp:has(.theme-dark-marker) div[data-baseweb="textarea"],
.stApp:has(.theme-dark-marker) div[data-baseweb="select"] {
    background: #172033 !important;
}

.stApp:has(.theme-dark-marker) div[data-baseweb="input"] > div,
.stApp:has(.theme-dark-marker) div[data-baseweb="textarea"] > div,
.stApp:has(.theme-dark-marker) div[data-baseweb="select"] > div {
    background: #172033 !important;
    border-color: #475569 !important;
}

.stApp:has(.theme-dark-marker) input,
.stApp:has(.theme-dark-marker) textarea {
    color: #F8FAFC !important;
    background: #172033 !important;
    caret-color: #F8FAFC !important;
}

.stApp:has(.theme-dark-marker) input::placeholder,
.stApp:has(.theme-dark-marker) textarea::placeholder {
    color: #94A3B8 !important;
}


/* =========================================================
   DARK SELECTBOX
   ========================================================= */

.stApp:has(.theme-dark-marker) [data-baseweb="select"] * {
    color: #F8FAFC !important;
}

.stApp:has(.theme-dark-marker) [data-baseweb="popover"],
.stApp:has(.theme-dark-marker) [data-baseweb="menu"] {
    background: #172033 !important;
}

.stApp:has(.theme-dark-marker) [data-baseweb="menu"] li {
    color: #F8FAFC !important;
}


/* =========================================================
   DARK RADIO / TOGGLE
   ========================================================= */

.stApp:has(.theme-dark-marker) [data-testid="stRadio"] label {
    color: #F8FAFC !important;
}

.stApp:has(.theme-dark-marker) [data-testid="stToggle"] label {
    color: #F8FAFC !important;
}


/* =========================================================
   DARK FILE UPLOADER
   ========================================================= */

.stApp:has(.theme-dark-marker) div[data-testid="stFileUploader"] {
    background: #172033 !important;
    border-color: #475569 !important;
}

.stApp:has(.theme-dark-marker) div[data-testid="stFileUploader"] * {
    color: #CBD5E1 !important;
}

.stApp:has(.theme-dark-marker) div[data-testid="stFileUploader"] small {
    color: #94A3B8 !important;
}


/* =========================================================
   DARK SECONDARY BUTTON
   ========================================================= */

.stApp:has(.theme-dark-marker) button[kind="secondary"] {
    background: #172033 !important;
    color: #F8FAFC !important;
    border-color: #475569 !important;
}

.stApp:has(.theme-dark-marker) button[kind="secondary"]:hover {
    background: #1E293B !important;
    border-color: #64748B !important;
}


/* =========================================================
   DARK TABLE
   ========================================================= */

.stApp:has(.theme-dark-marker) [data-testid="stDataFrame"] {
    border-color: #334155 !important;
}


/* =========================================================
   DARK DIVIDERS
   ========================================================= */

.stApp:has(.theme-dark-marker) hr {
    border-color: #334155 !important;
}


/* =========================================================
   DARK LOGIN
   ========================================================= */

.stApp:has(.theme-dark-marker) .login-card h1,
.stApp:has(.theme-dark-marker) .login-card h2 {
    color: #F8FAFC !important;
}

.stApp:has(.theme-dark-marker) .login-card p {
    color: #CBD5E1 !important;
}


/* =========================================================
   DARK INLINE TEXT USING OLD VAR
   ========================================================= */

.stApp:has(.theme-dark-marker) [style*="color:var(--navy)"] {
    color: #F8FAFC !important;
}


/* =========================================================
   DARK DIVIDER / BORDERS
   ========================================================= */

.stApp:has(.theme-dark-marker) [style*="#DCE5EE"] {
    border-color: #334155 !important;
}


/* =========================================================
   ACCESSIBILITY / FOCUS
   ========================================================= */

button:focus,
input:focus,
textarea:focus {
    outline: none !important;
}

button:focus-visible,
input:focus-visible,
textarea:focus-visible {
    box-shadow:
        0 0 0 3px rgba(37, 99, 235, 0.18) !important;
}


/* =========================================================
   MOBILE
   ========================================================= */

@media (max-width: 768px) {

    .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
    }

    .hero {
        padding: 26px 24px;
        border-radius: 18px;
    }

    .hero h1 {
        font-size: 30px;
    }

    .metric-card,
    .workflow {
        padding: 18px;
    }
}

</style>
""", unsafe_allow_html=True)

def api():
    return SendaAPI(BACKEND_URL, st.session_state.get("token"))


def pill(status):
    s = str(status or "UNKNOWN").upper()

    if s in {"PASS", "LOW"}:
        cls = "status-pass"
    elif s in {"FAIL", "HIGH"}:
        cls = "status-fail"
    elif s in {"REVIEW", "INCONSISTENT", "BLOCKED", "MEDIUM"}:
        cls = "status-review"
    else:
        cls = "status-neutral"

    return f'<span class="status-pill {cls}">{s}</span>'

def score_text(score):
    return "—" if score is None else f"{score}/100"


def render_pdf(pdf_bytes, height=600):
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    st.components.v1.html(
        f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="{height}" type="application/pdf" style="border:1px solid #DCE5EE;border-radius:12px;"></iframe>',
        height=height + 10,
    )


# -----------------------------------------------------------------------------
# LOGIN VIEW
# -----------------------------------------------------------------------------
def login_page():
    st.markdown('<div class="login-wrap">', unsafe_allow_html=True)

    st.markdown("""
    <div class="login-card">
      <div class="brand">
        <div class="brand-mark">ST</div>
        <div class="brand-name">Senda<span>Tender</span></div>
      </div>

      <div class="subbrand">SIH 2026 • PS 26100</div>

      <h2 style="color:var(--navy);margin-top:20px;font-size:1.45rem;font-weight:800;">
        Officer Portal
      </h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    officer_id = st.text_input(
    "Official ID",
    placeholder="e.g. PO-001",
)
    password = st.text_input(
        "Access Password",
        type="password",
        placeholder="Enter your officer password"
    )
    submit = st.button("Sign In →", type="primary", use_container_width=True)

    if submit:
        if not password:
            st.warning("Please enter your password.")
        else:
            try:
                result = SendaAPI(BACKEND_URL).login(officer_id.strip(), password.strip())
                st.session_state["token"] = result["token"]
                st.session_state["officer_id"] = result["officer_id"]
                st.rerun()
            except Exception as e:
                st.error(f"Authentication failed. Please check your credentials and try again.")

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
    theme_choice = st.radio(
        "Appearance",
        ["Light", "Dark"],
        horizontal=True,
        index=1 if st.session_state.get("theme") == "dark" else 0
    )
    if (theme_choice == "Dark") != (st.session_state.get("theme") == "dark"):
        st.session_state["theme"] = "dark" if theme_choice == "Dark" else "light"
        st.rerun()

    st.caption("Restricted access. Authorized procurement officers only.")
    st.markdown("</div>", unsafe_allow_html=True)


if "token" not in st.session_state:
    login_page()
    st.stop()

# -----------------------------------------------------------------------------
# SIDEBAR NAVIGATION & CONTROLS
# -----------------------------------------------------------------------------
NAV_OPTIONS = [
    "Overview",
    "New Verification",
    "Verification History",
    "Bidder Directory",
    "Audit Trail",
    "Officer Account",
]

# Synchronize navigation override if requested by in-page action
if "pending_nav" in st.session_state:
    target = st.session_state.pop("pending_nav")
    if target in NAV_OPTIONS:
        st.session_state["workspace_nav"] = target
    st.session_state["nav_page"] = target

with st.sidebar:
    st.markdown('<div class="brand"><div class="brand-mark">ST</div><div class="brand-name">Senda<span>Tender</span></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="subbrand">SIH 2026 • PS 26100</div>', unsafe_allow_html=True)

    # Initialize radio state cleanly
    if "workspace_nav" not in st.session_state:
        st.session_state["workspace_nav"] = "Overview"

    selected_page = st.radio(
        "Workspace",
        NAV_OPTIONS,
        key="workspace_nav",
        label_visibility="collapsed",
    )
    # If user selected a sidebar item, clear any deep review state
    if st.session_state.get("nav_page") == "Verification Review" and selected_page != "Verification History":
        st.session_state.pop("selected_verification", None)
        st.session_state["nav_page"] = selected_page
    elif st.session_state.get("nav_page") != "Verification Review":
        st.session_state["nav_page"] = selected_page

    st.divider()
    st.markdown("<div class='small-muted' style='margin-bottom:6px;font-weight:700;'>APPEARANCE</div>", unsafe_allow_html=True)
    dark_mode = st.toggle("Dark mode", value=st.session_state.get("theme") == "dark", key="dark_mode_toggle")
    desired_theme = "dark" if dark_mode else "light"
    if desired_theme != st.session_state.get("theme"):
        st.session_state["theme"] = desired_theme
        st.rerun()

    st.divider()
    st.markdown(
        '<div style="background:#FFF6E6;border:1px solid #F4E1B9;border-radius:14px;padding:12px 14px;font-size:0.79rem;color:#7A5B1A;line-height:1.45;">'
        '<b>PROTOTYPE MODE</b><br>Government portal checks and AI outputs are simulated for demonstration.</div>',
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    current_officer = st.session_state.get("officer_id")

if current_officer:
    st.caption(f"Signed in as: **{current_officer}**")
    if st.button("Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()


try:
    client = api()
except Exception:
    st.error("Could not initialize backend API client. Please ensure FastAPI is running.")
    st.stop()


# -----------------------------------------------------------------------------
# OVERVIEW (DASHBOARD) - MATCHES UI_REFERENCE.PNG
# -----------------------------------------------------------------------------
def dashboard():
    try:
        data = client.dashboard()
    except Exception as e:
        st.error(f"Backend unavailable: {e}")
        st.stop()

    stats = data["stats"]

    # Hero Banner (directly matching UI_REFERENCE.png)
    h_col1, h_col2 = st.columns([1.5, 0.9], gap="large")
    with h_col1:
        st.markdown("""
        <div class="hero">
          <span class="eyebrow">SIH 2026 • Problem Statement 26100</span>
          <h1>Review tender documents<br>in one workspace.</h1>
          <p>SendaTender helps a vendor upload tender and eligibility documents together. The system classifies files, runs prototype checks, creates a compliance report, and sends the package to an officer for review.</p>
        </div>
        """, unsafe_allow_html=True)
        btn_col1, btn_col2 = st.columns([1, 1])
        with btn_col1:
            if st.button("Upload package →", type="primary", use_container_width=True):
                st.session_state["pending_nav"] = "New Verification"
                st.rerun()
        with btn_col2:
            if st.button("Open officer desk", use_container_width=True):
                st.session_state["pending_nav"] = "Verification History"
                st.rerun()

    with h_col2:
        # Illustration matching UI_REFERENCE.png right card with dynamic counts
        st.markdown(f"""
        <div class="metric-card" style="height:100%;min-height:260px;padding:26px;background:linear-gradient(145deg,#F8FBFF,#EEF7F6);display:flex;flex-direction:column;justify-content:center;">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
            <span class="metric-label">PROCUREMENT DESK</span>
            <span class="status-pill status-pass">Active</span>
          </div>
          <div style="font-size:1.2rem;font-weight:800;color:var(--navy);margin-bottom:12px;">Officer Evaluation Unit</div>
          <div style="display:flex;justify-content:space-between;padding:10px 0;border-top:1px solid #DCE5EE;">
            <span class="small-muted">Active vendor bids</span>
            <b style="color:var(--navy);">{stats['active_bidders']:02d}</b>
          </div>
          <div style="display:flex;justify-content:space-between;padding:10px 0;border-top:1px solid #DCE5EE;">
            <span class="small-muted">Awaiting review</span>
            <b style="color:var(--navy);">{stats['pending']:02d}</b>
          </div>
          <div style="display:flex;justify-content:space-between;padding:10px 0;border-top:1px solid #DCE5EE;">
            <span class="small-muted">Decisions recorded</span>
            <b style="color:var(--teal);">{stats['verified']:02d}</b>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # Metric Cards Grid (backed by dynamic SQLite data)
    cols = st.columns(4)
    active_bidders_val = stats["active_bidders"]
    avg_compliance_val = f'{stats["average_compliance"]}%'
    ready_to_review_val = stats["pending"]
    high_risk_val = stats["high_risk"]

    bidders_subtext = f"+{active_bidders_val} this week" if active_bidders_val > 0 else "No active bidders"
    compliance_subtext = "Across submitted packages" if active_bidders_val > 0 else "No packages submitted"
    ready_subtext = "Awaiting officer decision" if ready_to_review_val > 0 else "0 awaiting review"
    risk_subtext = "Requires officer attention" if high_risk_val > 0 else "0 flagged high risk"

    cards = [
        ("ACTIVE BIDDERS", active_bidders_val, bidders_subtext, "Across active procurement runs"),
        ("AVG. COMPLIANCE", avg_compliance_val, compliance_subtext, "Average checklist compliance score"),
        ("READY TO REVIEW", ready_to_review_val, ready_subtext, "Packages ready for final ruling"),
        ("HIGH RISK", high_risk_val, risk_subtext, "Bidders with flagged discrepancies"),
    ]

    for col, (label, val, helptext, tooltip) in zip(cols, cards):
        with col:
            st.markdown(f"""
            <div class="metric-card" title="{tooltip}">
              <div class="metric-label">{label}</div>
              <div class="metric-value">{val}</div>
              <div class="metric-help">{helptext}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # 3-Step Workflow Cards (directly matching UI_REFERENCE.png)
    st.markdown('<div class="section-title">End-to-End Procurement Workflow</div>', unsafe_allow_html=True)
    w_cols = st.columns(3)
    workflows = [
        ("1", "step-1", "Vendor submission", "Upload NIT/RFP, BOQ, GST, PAN, Udyam, ITR, bank proof, and technical documents in one package."),
        ("2", "step-2", "Automated screening", "The prototype identifies documents, checks required items, calculates compliance, and explains failed checks."),
        ("3", "step-3", "Officer decision", "Officers view the report, bidder history, and audit trail before approving, requesting review, or flagging a bidder."),
    ]
    for col, (num, cls, title, body) in zip(w_cols, workflows):
        with col:
            st.markdown(f"""
            <div class="workflow">
              <div class="step {cls}">{num}</div>
              <h4>{title}</h4>
              <p>{body}</p>
            </div>
            """, unsafe_allow_html=True)

    # Recent Verifications Section
    st.markdown('<div class="section-title">Recent Verifications</div>', unsafe_allow_html=True)
    recent = data.get("recent", [])
    if not recent:
        st.info("No verification records in database yet. Click 'Upload package →' above to start your first verification.")
    else:
        for item in recent:
            c1, c2, c3, c4, c5, c6 = st.columns([2.2, 1.4, 0.8, 0.9, 1.3, 0.9])
            c1.markdown(f"**{item['bidder_name']}**<br><span class='small-muted'>PAN: {item['bidder_pan']} · {item['tender_filename']}</span>", unsafe_allow_html=True)
            c2.write(item["timestamp"][:16].replace("T", " "))
            c3.write(score_text(item["score"]))
            c4.markdown(pill(item["risk"]), unsafe_allow_html=True)
            c5.write(item["decision"])
            if c6.button("Review", key=f"dash_{item['id']}", use_container_width=True):
                st.session_state["selected_verification"] = item["id"]
                st.session_state["nav_page"] = "Verification Review"
                st.rerun()


# -----------------------------------------------------------------------------
# NEW VERIFICATION (ONE TENDER + MULTIPLE VENDOR BIDS)
# -----------------------------------------------------------------------------
def new_verification():
    st.markdown('<div class="section-title" style="font-size:1.85rem;margin-top:0;">New Verification</div>', unsafe_allow_html=True)
    st.caption("Upload one tender once, then analyse multiple vendor bids against the same procurement context. 50 MB max per PDF.")

    tender = st.file_uploader(
        "Tender / RFP Document (PDF)",
        type=["pdf"],
        key="uploader_tender",
        help="The official tender or RFP containing mandatory eligibility and technical requirements.",
    )
    tender_oversized = False
    if tender:
        size_mb = len(tender.getvalue()) / (1024 * 1024)
        if size_mb > MAX_MB:
            st.error(f"❌ {tender.name} exceeds the 50 MB per-file limit ({size_mb:.1f} MB).")
            tender_oversized = True
        else:
            st.success(f"✓ Tender: {tender.name} ({size_mb:.2f} MB)")

    vendors = st.file_uploader(
        "Vendor Bid Submissions — upload one or more (PDF)",
        type=["pdf"],
        accept_multiple_files=True,
        key="uploader_vendors",
        help="The bid documents submitted by competing vendors. Each bidder must have a PAN.",
    )

    if not vendors:
        st.info("💡 Add at least one vendor bid PDF above to configure bidder details and run verifications.")
        return

    st.markdown('<div class="section-title">Bidder Information</div>', unsafe_allow_html=True)
    st.caption("Enter each bidder's details. The PAN is used for cross-checking against simulated government databases.")

    pans = []
    names = []
    oversized_files = []

    for i, f in enumerate(vendors):
        f_size_mb = len(f.getvalue()) / (1024 * 1024)
        if f_size_mb > MAX_MB:
            oversized_files.append(f"{f.name} ({f_size_mb:.1f} MB)")

        st.markdown(f"""
        <div class="queue-card">
          <b>Vendor Bid #{i+1}</b>: {f.name} &nbsp;·&nbsp; <span class="small-muted">{f_size_mb:.2f} MB</span>
        </div>
        """, unsafe_allow_html=True)

        col_name, col_pan, col_helper = st.columns([1.2, 1.2, 0.8])
        with col_name:
            default_name = st.session_state.get(f"name_val_{i}", "")
            v_name = st.text_input(
                f"Bidder Name #{i+1}",
                value=default_name,
                key=f"input_name_{i}",
                placeholder="e.g. Sample Vendor Pvt Ltd",
            )
            names.append(v_name)

        with col_pan:
            default_pan = st.session_state.get(f"pan_val_{i}", "")
            v_pan = st.text_input(
                f"Bidder PAN #{i+1}",
                value=default_pan,
                key=f"input_pan_{i}",
                placeholder="e.g. AABCU1234C",
            ).upper().strip()
            pans.append(v_pan)

        with col_helper:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("Use Demo PAN", key=f"demo_pan_btn_{i}", help="Fill with verified demo vendor AABCU1234C"):
                st.session_state[f"pan_val_{i}"] = "AABCU1234C"
                st.session_state[f"name_val_{i}"] = "Sample Vendor Pvt Ltd"
                st.rerun()

    missing_pans = [i + 1 for i, p in enumerate(pans) if not p]
    if missing_pans:
        st.warning(f"⚠️ Please enter PAN for Vendor Bid #{', #'.join(map(str, missing_pans))}.")

    if oversized_files:
        st.error(f"❌ Files exceeding 50 MB limit: {', '.join(oversized_files)}")

    can_submit = bool(tender and not tender_oversized and vendors and not oversized_files and not missing_pans)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    if st.button("Analyse All Bids →", type="primary", use_container_width=True, disabled=not can_submit):
        try:
            with st.status("Running SendaTender Verification Pipeline…", expanded=True) as status:
                st.write("1. Reading tender document and extracting mandatory eligibility requirements…")
                st.write("2. Checking tender-bid document alignment gate…")
                st.write("3. Cross-referencing bidder PAN against simulated government registries (Udyam, GSTN, EPFO)…")
                st.write("4. Scanning for prompt injection guardrails and evaluating evidence…")
                batch_res = client.batch_verify(tender, vendors, pans, names)
                status.update(label=f"✓ Verification complete! Processed {len(batch_res['results'])} bidder(s).", state="complete")

            st.session_state["last_batch"] = batch_res
            st.session_state["pending_nav"] = "Verification History"
            st.rerun()
        except APIError as err:
            st.error(f"Verification Pipeline Error: {err}")
        except Exception as e:
            st.error(f"Failed to process verification batch: {e}")


# -----------------------------------------------------------------------------
# VERIFICATION HISTORY
# -----------------------------------------------------------------------------
def verification_history():
    st.markdown('<div class="section-title" style="font-size:1.85rem;margin-top:0;">Verification History</div>', unsafe_allow_html=True)
    try:
        rows = client.history()
    except Exception as e:
        st.error(f"Could not load verification records: {e}")
        return

    if "last_batch" in st.session_state:
        b = st.session_state["last_batch"]
        st.success(f"✓ Verification Batch **{b.get('batch_id')}** completed with {b.get('count')} bidder(s). Click 'View Finding' below to inspect evidence.")

    if not rows:
        st.info("No stored verifications found. Start a verification from the New Verification tab.")
        return

    st.caption(f"Showing {len(rows)} verification record(s). All records are persisted in the SQLite backend.")

    for item in rows:
        r = item["result"]
        score = r.get("compliance_score")
        risk = r.get("risk_level")
        blocked = r.get("blocked", False)

        cols = st.columns([2.3, 1.2, 0.8, 0.9, 1.3, 0.9])
        cols[0].markdown(
            f"**{item['bidder_name']}**<br>"
            f"<span class='small-muted'>PAN: {item['bidder_pan']} · Bid: {item['vendor_filename']}</span>",
            unsafe_allow_html=True,
        )
        cols[1].write(item["timestamp"][:16].replace("T", " "))
        cols[2].write(score_text(score) if not blocked else "—")
        cols[3].markdown(pill("BLOCKED" if blocked else risk), unsafe_allow_html=True)
        cols[4].write(item["officer_decision"])

        if cols[5].button("View", key=f"hist_{item['id']}", use_container_width=True):
            st.session_state["selected_verification"] = item["id"]
            st.session_state["nav_page"] = "Verification Review"
            st.rerun()


# -----------------------------------------------------------------------------
# VERIFICATION REVIEW (EVIDENCE-FIRST FINDINGS + PDF VIEWER)
# -----------------------------------------------------------------------------
def verification_review():
    vid = st.session_state.get("selected_verification")
    if not vid:
        st.info("Select a verification from the History tab to review evidence.")
        return

    try:
        item = client.verification(vid)
    except Exception as e:
        st.error(f"Failed to fetch verification #{vid}: {e}")
        return

    r = item["result"]

    col_back, _ = st.columns([1, 4])
    with col_back:
        if st.button("← Back to History"):
            st.session_state["nav_page"] = "Verification History"
            st.session_state.pop("selected_verification", None)
            st.rerun()

    st.markdown(f'<div class="section-title" style="font-size:2rem;margin-top:8px;">{item["bidder_name"]}</div>', unsafe_allow_html=True)
    st.caption(f"PAN: {item['bidder_pan']}  ·  Tender: {item['tender_filename']}  ·  Bid: {item['vendor_filename']}  ·  Run ID: #{item['id']}")

    # Handle Blocked Submissions (e.g. Mismatched Documents)
    if r.get("blocked"):
        st.error("🚨 VERIFICATION BLOCKED BY ALIGNMENT GATE")
        st.markdown(f"**Reason:** {r.get('block_reason') or r.get('error') or 'Document alignment or verification failed.'}")
        st.info("The uploaded bid does not appear to correspond to this tender document. Please verify the files and resubmit.")
        return

    # Metrics Summary
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Compliance Score", score_text(r.get("compliance_score")))
    m2.metric("Risk Level", r.get("risk_level", "Unknown"))
    m3.metric("Requirements Checked", len(r.get("requirement_results", [])))
    m4.metric("Officer Decision", item["officer_decision"])

    # Warnings / Guardrails
    if r.get("alignment_warning"):
        st.warning(f"⚠️ {r['alignment_warning']}")
    if r.get("injection_hits"):
        st.error(f"🛡️ Prompt Injection Guardrail Triggered: Discovered {len(r['injection_hits'])} suspicious phrase(s): " + ", ".join(r["injection_hits"]))

    if r.get("flags"):
        st.markdown("#### 🚩 Flags Identified")
        for flag in r["flags"]:
            st.markdown(f"• **{flag}**")

    # AI Advisory Recommendation
    st.markdown('<div class="section-title">AI Recommendation (Advisory Only)</div>', unsafe_allow_html=True)
    rec = r.get("recommendation", "No recommendation provided.")
    st.info(f"📋 {rec}")

    # Tabs for Findings and Document Viewer
    tab_findings, tab_evidence_doc = st.tabs(["📋 Requirement Findings", "📄 Document & Evidence Viewer"])

    with tab_findings:
        reqs = r.get("requirement_results", [])
        if not reqs:
            st.info("No requirement findings were returned for this submission.")
        else:
            for i, req in enumerate(reqs):
                status = str(req.get("status", "UNVERIFIABLE")).upper()
                cls = "pass" if status == "PASS" else "fail" if status == "FAIL" else "review"
                category = req.get("category", "Other")
                cat_help = req.get("category_help", "")

                st.markdown(f"""
                <div class="finding {cls}">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                    <b style="font-size:1.05rem;">{req.get('requirement', 'Requirement')}</b>
                    {pill(status)}
                  </div>
                  <span class="small-muted" title="{cat_help}">Category: <b>{category}</b></span>
                  <p style="margin:10px 0 6px;line-height:1.5;">{req.get('evidence', 'No evidence description available.')}</p>
                </div>
                """, unsafe_allow_html=True)

    with tab_evidence_doc:
        st.markdown("#### Embedded Document Viewer")
        st.caption("Inspect the original vendor bid and tender PDF directly within the workspace.")

        doc_kind = st.radio("Select Document to View", ["Vendor Bid Document", "Tender RFP Document"], horizontal=True)
        kind_key = "vendor" if doc_kind == "Vendor Bid Document" else "tender"
        curr_filename = item["vendor_filename"] if kind_key == "vendor" else item["tender_filename"]

        try:
            pdf_data = client.document(vid, kind_key)
            col_dl, _ = st.columns([1, 2])
            with col_dl:
                st.download_button(
                    label=f"⬇️ Download {doc_kind} ({len(pdf_data)/1024/1024:.2f} MB)",
                    data=pdf_data,
                    file_name=curr_filename,
                    mime="application/pdf",
                    use_container_width=True,
                )
            render_pdf(pdf_data, height=620)
        except Exception as e:
            st.warning(f"Could not load PDF document preview: {e}")

    # Officer Review & Decision (Core Acceptance Criteria)
    st.markdown('<div class="section-title">Officer Decision & Review</div>', unsafe_allow_html=True)
    st.caption("The authorized procurement officer makes the final qualification ruling. AI recommendations are strictly advisory.")

    if item["officer_decision"] != "Not yet decided":
        st.success(f"✓ Current Decision Recorded: **{item['officer_decision']}**")
        if item.get("officer_notes"):
            st.markdown(f"**Officer Notes:** {item['officer_notes']}")
        st.caption(f"Recorded by Officer: {item.get('officer_id') or 'PO-001'}")

    st.markdown("##### Record / Update Decision")
    decision_options = ["Qualify bidder", "Disqualify bidder", "Hold for further review"]
    default_idx = decision_options.index(item["officer_decision"]) if item["officer_decision"] in decision_options else 0

    decision = st.radio("Final Officer Decision", decision_options, index=default_idx, horizontal=True)
    notes = st.text_area(
        "Officer Remarks & Decision Rationale",
        value=item.get("officer_notes", ""),
        placeholder="Enter formal justification, conditions for qualification, or reasons for disqualification...",
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Save Officer Decision", type="primary", use_container_width=True):
            try:
                client.decision(vid, decision, notes)
                st.success("Decision recorded to the immutable SQLite audit trail.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to record decision: {e}")

    with c2:
        try:
            report_pdf = client.report(vid)
            st.download_button(
                "📄 Download Compliance PDF Report",
                report_pdf,
                file_name=f"SendaTender_Report_{item['bidder_pan']}_{vid}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.caption(f"Report generation unavailable: {e}")


# -----------------------------------------------------------------------------
# BIDDER DIRECTORY
# -----------------------------------------------------------------------------
def bidder_directory():
    st.markdown('<div class="section-title" style="font-size:1.85rem;margin-top:0;">Bidder Directory</div>', unsafe_allow_html=True)
    st.caption("Track historic vendor evaluations, compliance performance, and recurring flags across multiple procurement cycles.")

    try:
        rows = client.bidders()
    except Exception as e:
        st.error(f"Failed to load bidder directory: {e}")
        return

    search = st.text_input("Search Bidders by Name or PAN", placeholder="Search by name, company, or PAN...").strip()
    filtered = [
        x for x in rows
        if not search or search.lower() in (x["bidder_name"] + " " + x["bidder_pan"]).lower()
    ]

    if not filtered:
        st.info("No bidders found matching your search query.")
        return

    for row in filtered:
        with st.expander(f"🏢 {row['bidder_name']}  ·  PAN: {row['bidder_pan']}  ·  {row['verifications']} Verification(s)"):
            try:
                history_data = client.bidder(row["bidder_pan"])["history"]
                st.markdown("##### Historic Verification Runs")
                for hist_item in history_data:
                    hr = hist_item["result"]
                    c1, c2, c3, c4 = st.columns([2.2, 1.1, 1, 1.2])
                    c1.markdown(f"**{hist_item['tender_filename']}**<br><span class='small-muted'>{hist_item['timestamp'][:10]}</span>", unsafe_allow_html=True)
                    c2.write(score_text(hr.get("compliance_score")))
                    c3.markdown(pill(hr.get("risk_level")), unsafe_allow_html=True)
                    c4.write(hist_item["officer_decision"])

                # Aggregated discrepancies / flags
                all_flags = []
                for hist_item in history_data:
                    for f in hist_item["result"].get("flags", []):
                        if f not in all_flags:
                            all_flags.append(f)

                if all_flags:
                    st.markdown("##### Historic Discrepancies & Red Flags")
                    for flg in all_flags:
                        st.markdown(f"• {flg}")
            except Exception as e:
                st.error(f"Failed to fetch bidder history: {e}")


# -----------------------------------------------------------------------------
# AUDIT TRAIL
# -----------------------------------------------------------------------------
def audit_trail():
    st.markdown('<div class="section-title" style="font-size:1.85rem;margin-top:0;">Protected Audit Trail 🔒</div>', unsafe_allow_html=True)
    st.caption("Immutable record of all officer decisions, timestamps, risk scores, and AI recommendations.")

    try:
        rows = client.audit()
    except Exception as e:
        st.error(f"Could not load audit trail: {e}")
        return

    if not rows:
        st.info("No officer decisions have been committed to the audit trail yet.")
        return

    for entry in rows:
        with st.expander(f"📅 {entry['timestamp'][:19].replace('T', ' ')} · {entry['bidder_name']} · {entry['officer_decision']}"):
            st.markdown(f"**Authorized Officer:** `{entry.get('officer_id') or 'PO-001'}`")
            st.markdown(f"**Compliance Score:** {entry['compliance_score']}/100  ·  **Risk Level:** {pill(entry['risk_level'])}", unsafe_allow_html=True)
            st.markdown(f"**AI Recommendation:** {entry.get('ai_recommendation', '—')}")
            if entry.get("officer_notes"):
                st.markdown(f"**Officer Justification:** {entry['officer_notes']}")

            if entry.get("verification_id"):
                try:
                    pdf_bytes = client.report(entry["verification_id"])
                    st.download_button(
                        "⬇️ Download Certified Compliance Report",
                        pdf_bytes,
                        file_name=f"SendaTender_Audit_{entry['id']}.pdf",
                        mime="application/pdf",
                        key=f"audit_pdf_{entry['id']}",
                    )
                except Exception:
                    pass


# -----------------------------------------------------------------------------
# OFFICER ACCOUNT
# -----------------------------------------------------------------------------
def officer_account():
    st.markdown('<div class="section-title" style="font-size:1.85rem;margin-top:0;">Officer Account & Settings</div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">AUTHORIZED PROCUREMENT OFFICER</div>
      <div class="metric-value" style="font-size:1.6rem;margin:6px 0;">{st.session_state.get("officer_id","")}</div>
      <div class="metric-help">Role: Evaluation Committee Officer (GeM Decision Support)</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
    st.markdown("#### Security & Access Model")
    st.write("This workspace uses provisioned officer credentials. Public officer registration is disabled by design to enforce government procurement integrity.")
    st.info("Production deployments integrate with government single sign-on (SSO) and HSM-backed audit trails.")

    st.markdown("#### Appearance Settings")
    st.write(f"Active Theme: **{st.session_state.get('theme', 'light').title()} Mode**")
    st.caption("Use the Dark mode toggle in the sidebar to seamlessly switch themes.")


# -----------------------------------------------------------------------------
# MAIN ROUTER
# -----------------------------------------------------------------------------
active_view = st.session_state.get("nav_page", "Overview")

if active_view == "Overview":
    dashboard()
elif active_view == "New Verification":
    new_verification()
elif active_view == "Verification History":
    verification_history()
elif active_view == "Verification Review":
    verification_review()
elif active_view == "Bidder Directory":
    bidder_directory()
elif active_view == "Audit Trail":
    audit_trail()
elif active_view == "Officer Account":
    officer_account()
else:
    dashboard()

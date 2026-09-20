import base64
import os
import re
from html import escape

import streamlit as st

from api_client import SendaAPI, APIError


# =============================================================================
# BACKEND CONFIGURATION
# =============================================================================

def _resolve_backend_url() -> str:
    """
    Backend URL resolution order:
    1. Streamlit Cloud secrets
    2. Environment variable
    3. Local development fallback
    """
    try:
        url = st.secrets.get("BACKEND_URL", "")
        if url:
            return url.rstrip("/")
    except Exception:
        pass

    return os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


BACKEND_URL = _resolve_backend_url()

MAX_MB = 50
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


# =============================================================================
# PAGE CONFIG  (must run before any other st.* call that renders)
# =============================================================================

st.set_page_config(
    page_title="SendaTender — Procurement verification workspace",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# SESSION STATE
# =============================================================================

st.session_state.setdefault("theme", "light")
st.session_state.setdefault("nav_page", "Overview")


# =============================================================================
# HTML HELPER
# =============================================================================
# This is the fix for the raw markup that was showing up on screen.
#
# st.markdown() runs the string through a Markdown parser before the HTML is
# allowed through. Two things inside a triple-quoted block break that:
#   1. a blank line ENDS the raw-HTML block, so everything after it is parsed
#      as ordinary Markdown text and printed literally;
#   2. a line indented by 4+ spaces starts an indented code block.
# The original login card had both, which is why the markup after the first
# blank line was rendered as text.
#
# ui() strips every line and drops blank lines, so neither can happen again.
# =============================================================================

def ui(markup: str) -> None:
    lines = [ln.strip() for ln in markup.strip().splitlines()]
    st.markdown("".join(ln for ln in lines if ln), unsafe_allow_html=True)


def rule() -> None:
    """Tricolour hairline used at the top of each signed-in view."""
    ui(
        """
        <div class="tricolour" aria-hidden="true">
        <i class="t-saffron"></i><i class="t-white"></i><i class="t-green"></i>
        </div>
        """
    )


# =============================================================================
# DESIGN SYSTEM
# =============================================================================

BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
    --paper:        #FFFFFF;
    --canvas:       #F1F4F7;
    --panel:        #FFFFFF;
    --panel-sunk:   #F7F9FB;

    --ink:          #12202E;
    --ink-2:        #47596C;
    --ink-3:        #77899A;

    --rule:         #DBE2E9;
    --rule-strong:  #BFCCD8;

    --seal:         #1C3D5A;
    --seal-soft:    #E7EEF5;

    --saffron:      #C9761D;
    --green:        #1F6F4A;

    --cleared-bg:   #E6F1EA;
    --cleared-ink:  #1B6340;

    --failed-bg:    #F8E8E7;
    --failed-ink:   #98241E;

    --held-bg:      #F7EEDC;
    --held-ink:     #7E5410;

    --quiet-bg:     #EBEFF3;
    --quiet-ink:    #5C6E7F;

    --radius:       6px;
    --radius-lg:    10px;
}

html, body, [class*="css"], .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-feature-settings: 'tnum' 1, 'cv05' 1;
}

.stApp { background: var(--canvas) !important; color: var(--ink) !important; }

.block-container {
    max-width: 1320px;
    padding-top: 1rem;
    padding-bottom: 4rem;
}

h1, h2, h3, h4, h5, h6 { color: var(--ink) !important; letter-spacing: -0.015em; }
p, li { color: var(--ink-2); }
.stMarkdown, [data-testid="stMarkdownContainer"] { color: var(--ink); }
[data-testid="stCaptionContainer"] { color: var(--ink-3) !important; }

code, .mono { font-family: 'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace; }

/* --- tricolour hairline ------------------------------------------------- */
.tricolour { display: flex; height: 3px; width: 100%; margin: 0 0 18px; border-radius: 2px; overflow: hidden; }
.tricolour i { flex: 1; display: block; }
.t-saffron { background: var(--saffron); }
.t-white   { background: var(--rule-strong); }
.t-green   { background: var(--green); }

/* --- sidebar ------------------------------------------------------------ */
[data-testid="stSidebar"] {
    background: var(--paper) !important;
    border-right: 1px solid var(--rule) !important;
}
[data-testid="stSidebar"] .block-container { padding: 1.1rem 0.9rem 1.5rem; }
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p { color: var(--ink) !important; }

[data-testid="stSidebar"] [data-testid="stRadio"] > div { gap: 2px; }
[data-testid="stSidebar"] [data-testid="stRadio"] label {
    border-radius: var(--radius);
    padding: 7px 9px;
    border-left: 2px solid transparent;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
    background: var(--panel-sunk);
    border-left-color: var(--rule-strong);
}

/* --- masthead ----------------------------------------------------------- */
.mast { display: flex; align-items: center; gap: 11px; }
.seal {
    width: 40px; height: 40px;
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    background: var(--seal);
    color: #FFFFFF !important;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.86rem; font-weight: 500; letter-spacing: 0.5px;
    border: 1px solid rgba(255,255,255,0.14);
}
.mast-name { font-size: 1.2rem; font-weight: 700; letter-spacing: -0.02em; color: var(--ink) !important; line-height: 1.1; }
.mast-name em { font-style: normal; color: var(--seal) !important; }
.mast-ref {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem; color: var(--ink-3) !important;
    margin-top: 2px;
}

/* --- docket (hero) ------------------------------------------------------ */
.docket {
    background: var(--panel);
    border: 1px solid var(--rule);
    border-top: 3px solid var(--seal);
    border-radius: var(--radius-lg);
    padding: 30px 32px 26px;
}
.docket h1 {
    font-size: 2.05rem; line-height: 1.16; font-weight: 700;
    letter-spacing: -0.03em; margin: 0 0 12px; max-width: 18ch;
}
.docket p { font-size: 0.95rem; line-height: 1.6; max-width: 62ch; margin: 0; color: var(--ink-2) !important; }

/* --- standing panel (right of docket) ----------------------------------- */
.standing {
    background: var(--panel);
    border: 1px solid var(--rule);
    border-radius: var(--radius-lg);
    padding: 22px 22px 14px;
    height: 100%;
}
.standing-head {
    display: flex; justify-content: space-between; align-items: baseline;
    padding-bottom: 12px; border-bottom: 1px solid var(--rule);
}
.standing-title { font-size: 0.95rem; font-weight: 600; color: var(--ink) !important; }
.standing-row {
    display: flex; justify-content: space-between; align-items: baseline;
    padding: 11px 0; border-bottom: 1px solid var(--rule);
    font-size: 0.86rem; color: var(--ink-2);
}
.standing-row:last-child { border-bottom: 0; }
.standing-row b { font-family: 'IBM Plex Mono', monospace; font-size: 0.95rem; color: var(--ink) !important; font-weight: 500; }

/* --- tiles -------------------------------------------------------------- */
.tile {
    background: var(--panel);
    border: 1px solid var(--rule);
    border-radius: var(--radius-lg);
    padding: 18px 20px 16px;
    min-height: 116px;
}
.tile-label { font-size: 0.79rem; font-weight: 500; color: var(--ink-3) !important; }
.tile-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.95rem; font-weight: 500; line-height: 1.1;
    color: var(--ink) !important; margin: 10px 0 6px;
}
.tile-note { font-size: 0.78rem; color: var(--ink-2) !important; }
.tile.attention { border-left: 3px solid var(--saffron); }

/* --- stage cards -------------------------------------------------------- */
.stage {
    background: var(--panel);
    border: 1px solid var(--rule);
    border-radius: var(--radius-lg);
    padding: 20px;
    min-height: 162px;
}
.stage-no {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.74rem; color: var(--ink-3) !important;
    padding-bottom: 9px; margin-bottom: 11px;
    border-bottom: 1px solid var(--rule); display: block;
}
.stage h4 { margin: 0 0 6px; font-size: 1rem; font-weight: 600; }
.stage p { margin: 0; font-size: 0.86rem; line-height: 1.55; }

/* --- record rows -------------------------------------------------------- */
.record {
    background: var(--panel);
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    padding: 12px 15px;
    margin: 7px 0;
}
.record b { color: var(--ink) !important; font-weight: 600; }
.meta { color: var(--ink-3) !important; font-size: 0.79rem; }
.meta .mono { color: var(--ink-2) !important; }

/* --- verdict pills ------------------------------------------------------ */
.pill {
    display: inline-block;
    border-radius: 3px;
    padding: 3px 8px;
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.01em;
    border: 1px solid transparent;
}
.pill-cleared { background: var(--cleared-bg); color: var(--cleared-ink) !important; border-color: #C8E0D2; }
.pill-failed  { background: var(--failed-bg);  color: var(--failed-ink)  !important; border-color: #EBC9C6; }
.pill-held    { background: var(--held-bg);    color: var(--held-ink)    !important; border-color: #E6D2AC; }
.pill-quiet   { background: var(--quiet-bg);   color: var(--quiet-ink)   !important; border-color: var(--rule); }

/* --- findings ----------------------------------------------------------- */
.finding {
    background: var(--panel);
    border: 1px solid var(--rule);
    border-left: 3px solid var(--rule-strong);
    border-radius: var(--radius);
    padding: 15px 17px;
    margin: 9px 0;
}
.finding.pass { border-left-color: var(--green); }
.finding.fail { border-left-color: #A32720; }
.finding.review { border-left-color: var(--saffron); }
.finding-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.finding-head b { font-size: 0.97rem; font-weight: 600; }
.finding p { margin: 9px 0 0; font-size: 0.88rem; line-height: 1.55; }

/* --- notice ------------------------------------------------------------- */
.notice {
    background: var(--panel-sunk);
    border: 1px solid var(--rule);
    border-left: 3px solid var(--saffron);
    border-radius: var(--radius);
    padding: 12px 14px;
    font-size: 0.8rem; line-height: 1.5; color: var(--ink-2) !important;
}
.notice b { color: var(--ink) !important; }

/* --- sign-in ------------------------------------------------------------ */
.signin {
    background: var(--panel);
    border: 1px solid var(--rule);
    border-top: 3px solid var(--seal);
    border-radius: var(--radius-lg);
    padding: 30px 30px 24px;
}
.signin h2 { font-size: 1.35rem; font-weight: 700; margin: 22px 0 6px; }
.signin p { font-size: 0.88rem; line-height: 1.55; margin: 0; color: var(--ink-2) !important; }

/* --- form controls ------------------------------------------------------ */
.stTextInput input, .stTextArea textarea {
    background: var(--paper) !important;
    color: var(--ink) !important;
    border: 1px solid var(--rule-strong) !important;
    border-radius: var(--radius) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: var(--seal) !important;
    box-shadow: 0 0 0 3px rgba(28, 61, 90, 0.10) !important;
}
.stTextInput input::placeholder, .stTextArea textarea::placeholder { color: var(--ink-3) !important; }

.stSelectbox div[data-baseweb="select"] > div {
    background: var(--paper) !important;
    color: var(--ink) !important;
    border-color: var(--rule-strong) !important;
    border-radius: var(--radius) !important;
}
[data-baseweb="select"] * { color: var(--ink) !important; }

.stRadio label, .stCheckbox label, .stToggle label { color: var(--ink) !important; }

div[data-testid="stFileUploader"] {
    background: var(--panel-sunk) !important;
    border: 1px dashed var(--rule-strong) !important;
    border-radius: var(--radius-lg) !important;
    padding: 10px !important;
}
div[data-testid="stFileUploader"]:hover { border-color: var(--seal) !important; }
div[data-testid="stFileUploader"] * { color: var(--ink-2) !important; }

button[kind="primary"] {
    border-radius: var(--radius) !important;
    font-weight: 600 !important;
    background: var(--seal) !important;
    color: #FFFFFF !important;
    border: 1px solid var(--seal) !important;
    box-shadow: none !important;
}
button[kind="primary"]:hover { background: #16324A !important; }

button[kind="secondary"] {
    border-radius: var(--radius) !important;
    font-weight: 500 !important;
    background: var(--paper) !important;
    color: var(--ink) !important;
    border: 1px solid var(--rule-strong) !important;
}
button[kind="secondary"]:hover { background: var(--panel-sunk) !important; border-color: var(--seal) !important; }

div[data-testid="stAlert"] { border-radius: var(--radius) !important; }

[data-testid="stMetric"] { color: var(--ink) !important; }
[data-testid="stMetricLabel"] { color: var(--ink-3) !important; }
[data-testid="stMetricValue"] {
    color: var(--ink) !important;
    font-family: 'IBM Plex Mono', monospace !important;
}

[data-testid="stDataFrame"] { border: 1px solid var(--rule) !important; border-radius: var(--radius) !important; overflow: hidden; }
hr { border-color: var(--rule) !important; }

button:focus-visible, input:focus-visible, textarea:focus-visible {
    outline: 2px solid var(--seal) !important;
    outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
    * { transition: none !important; animation: none !important; }
}

@media (max-width: 768px) {
    .block-container { padding-left: 0.85rem; padding-right: 0.85rem; }
    .docket { padding: 22px 20px; }
    .docket h1 { font-size: 1.55rem; max-width: none; }
    .tile, .stage, .standing, .signin { padding: 16px; }
}
</style>
"""

DARK_CSS = """
<style>
:root {
    --paper:        #101822;
    --canvas:       #0B1119;
    --panel:        #131C27;
    --panel-sunk:   #172231;

    --ink:          #EEF3F8;
    --ink-2:        #B3C2D0;
    --ink-3:        #8395A6;

    --rule:         #253344;
    --rule-strong:  #36485C;

    --seal:         #6FA8DC;
    --seal-soft:    #1A2C3E;

    --saffron:      #D9903F;
    --green:        #4FAE7E;

    --cleared-bg:   #16302A;
    --cleared-ink:  #6FD3A5;

    --failed-bg:    #34201F;
    --failed-ink:   #EC8E88;

    --held-bg:      #33281440;
    --held-ink:     #E0B36A;

    --quiet-bg:     #1C2735;
    --quiet-ink:    #9AAABA;
}

.stApp { background: var(--canvas) !important; color: var(--ink) !important; }

[data-testid="stSidebar"] { background: var(--paper) !important; border-right-color: var(--rule) !important; }
[data-testid="stSidebar"] * { color: var(--ink) !important; }

.seal { background: var(--seal-soft); color: var(--seal) !important; border-color: var(--rule-strong); }
.mast-name em { color: var(--seal) !important; }

.docket, .signin { border-top-color: var(--seal); }

.stTextInput input, .stTextArea textarea,
div[data-baseweb="input"] > div, div[data-baseweb="textarea"] > div,
div[data-baseweb="select"] > div {
    background: var(--panel) !important;
    color: var(--ink) !important;
    border-color: var(--rule-strong) !important;
}
input, textarea { color: var(--ink) !important; caret-color: var(--ink) !important; }
[data-baseweb="popover"], [data-baseweb="menu"] { background: var(--panel) !important; }
[data-baseweb="menu"] li { color: var(--ink) !important; }

div[data-testid="stFileUploader"] { background: var(--panel-sunk) !important; border-color: var(--rule-strong) !important; }

button[kind="primary"] { background: var(--seal) !important; border-color: var(--seal) !important; color: #0B1119 !important; }
button[kind="primary"]:hover { background: #8CBCE8 !important; }
button[kind="secondary"] { background: var(--panel) !important; color: var(--ink) !important; border-color: var(--rule-strong) !important; }
button[kind="secondary"]:hover { background: var(--panel-sunk) !important; }

.t-white { background: var(--rule-strong); }
</style>
"""

st.markdown(BASE_CSS, unsafe_allow_html=True)

# Dark rules are only injected when dark mode is on, so no `:has()` marker
# trick is needed — the variables above are simply redefined.
if st.session_state.get("theme") == "dark":
    st.markdown(DARK_CSS, unsafe_allow_html=True)


# =============================================================================
# HELPERS
# =============================================================================

def api():
    return SendaAPI(BACKEND_URL, st.session_state.get("token"))


def pill(status) -> str:
    s = str(status or "Unknown").strip()
    key = s.upper()

    if key in {"PASS", "LOW"}:
        cls, text = "pill-cleared", s.title()
    elif key in {"FAIL", "HIGH"}:
        cls, text = "pill-failed", s.title()
    elif key in {"REVIEW", "INCONSISTENT", "BLOCKED", "MEDIUM"}:
        cls, text = "pill-held", s.title()
    else:
        cls, text = "pill-quiet", s.title()

    return f'<span class="pill {cls}">{escape(text)}</span>'


def score_text(score) -> str:
    return "—" if score is None else f"{score}/100"


def stamp(ts: str) -> str:
    return (ts or "")[:16].replace("T", " ")


def render_pdf(pdf_bytes, height=620):
    """
    Chrome blocks PDFs served from a data: URI inside an iframe, so the
    download button above this is the reliable path. <object> keeps a text
    fallback for browsers that refuse to render inline.
    """
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    st.components.v1.html(
        f"""
        <object data="data:application/pdf;base64,{b64}"
                type="application/pdf"
                width="100%" height="{height}"
                style="border:1px solid #DBE2E9;border-radius:6px;background:#FFFFFF;">
          <p style="font-family:Inter,sans-serif;font-size:14px;color:#47596C;padding:12px;">
            Your browser blocked the inline preview. Use the download button above
            to open this document.
          </p>
        </object>
        """,
        height=height + 12,
    )


# =============================================================================
# SIGN IN
# =============================================================================

def login_page():
    rule()

    left, mid, right = st.columns([1, 1.6, 1])

    with mid:
        ui(
            """
            <div class="signin">
            <div class="mast">
            <div class="seal">ST</div>
            <div>
            <div class="mast-name">Senda<em>Tender</em></div>
            <div class="mast-ref">SIH 2026 / PS 26100</div>
            </div>
            </div>
            <h2>Officer portal</h2>
            <p>Sign in to review submitted procurement packages, inspect the
            supporting evidence, and record a qualification decision.</p>
            </div>
            """
        )

        st.write("")

        officer_id = st.text_input("Officer ID", placeholder="PO-001")
        password = st.text_input(
            "Password", type="password", placeholder="Your officer password"
        )

        if st.button("Sign in", type="primary", use_container_width=True):
            if not officer_id.strip():
                st.warning("Enter your officer ID to continue.")
            elif not password:
                st.warning("Enter your password to continue.")
            else:
                try:
                    result = SendaAPI(BACKEND_URL).login(
                        officer_id.strip(), password.strip()
                    )
                    st.session_state["token"] = result["token"]
                    st.session_state["officer_id"] = result["officer_id"]
                    st.rerun()
                except Exception:
                    st.error(
                        "Those credentials were not accepted. Check the officer "
                        "ID and password, then try again."
                    )

        st.write("")

        theme_choice = st.radio(
            "Appearance",
            ["Light", "Dark"],
            horizontal=True,
            index=1 if st.session_state.get("theme") == "dark" else 0,
        )

        wants_dark = theme_choice == "Dark"
        if wants_dark != (st.session_state.get("theme") == "dark"):
            st.session_state["theme"] = "dark" if wants_dark else "light"
            st.rerun()

        st.caption("Restricted access. Authorised procurement officers only.")


if "token" not in st.session_state:
    login_page()
    st.stop()


# =============================================================================
# NAVIGATION
# =============================================================================

NAV_OPTIONS = [
    "Overview",
    "New verification",
    "Verification history",
    "Bidder directory",
    "Audit trail",
    "Officer account",
]

if "pending_nav" in st.session_state:
    target = st.session_state.pop("pending_nav")
    if target in NAV_OPTIONS:
        st.session_state["workspace_nav"] = target
    st.session_state["nav_page"] = target

st.session_state.setdefault("workspace_nav", "Overview")


with st.sidebar:
    ui(
        """
        <div class="mast">
        <div class="seal">ST</div>
        <div>
        <div class="mast-name">Senda<em>Tender</em></div>
        <div class="mast-ref">SIH 2026 / PS 26100</div>
        </div>
        </div>
        """
    )

    st.write("")

    selected_page = st.radio(
        "Workspace",
        NAV_OPTIONS,
        key="workspace_nav",
        label_visibility="collapsed",
    )

    if (
        st.session_state.get("nav_page") == "Verification review"
        and selected_page != "Verification history"
    ):
        st.session_state.pop("selected_verification", None)
        st.session_state["nav_page"] = selected_page
    elif st.session_state.get("nav_page") != "Verification review":
        st.session_state["nav_page"] = selected_page

    st.divider()

    dark_mode = st.toggle(
        "Dark mode",
        value=(st.session_state.get("theme") == "dark"),
        key="dark_mode_toggle",
    )

    desired_theme = "dark" if dark_mode else "light"
    if desired_theme != st.session_state.get("theme"):
        st.session_state["theme"] = desired_theme
        st.rerun()

    st.divider()

    ui(
        """
        <div class="notice">
        <b>Prototype</b><br>
        Government portal lookups and AI findings on this build are simulated
        for demonstration.
        </div>
        """
    )

    current_officer = st.session_state.get("officer_id")


# =============================================================================
# OFFICER BAR
# =============================================================================

if current_officer:
    rule()

    bar_left, bar_right = st.columns([8, 1.3])
    with bar_left:
        st.caption(f"Signed in as {current_officer}")
    with bar_right:
        if st.button("Sign out", use_container_width=True):
            st.session_state.clear()
            st.rerun()


try:
    client = api()
except Exception:
    st.error(
        "The backend API client could not start. Check that the FastAPI "
        f"service is running at {BACKEND_URL}."
    )
    st.stop()


# =============================================================================
# OVERVIEW
# =============================================================================

def dashboard():
    try:
        data = client.dashboard()
    except Exception as e:
        st.error(f"The backend did not respond: {e}")
        st.stop()

    stats = data["stats"]

    main_col, side_col = st.columns([1.55, 0.85], gap="large")

    with main_col:
        ui(
            """
            <div class="docket">
            <h1>Review a tender package in one place.</h1>
            <p>A vendor submits the tender and its eligibility documents
            together. SendaTender sorts the files, runs the prototype checks,
            builds a compliance report, and hands the package to an officer
            for a decision.</p>
            </div>
            """
        )

        st.write("")

        act_left, act_right = st.columns(2)

        with act_left:
            if st.button(
                "Upload a package", type="primary", use_container_width=True
            ):
                st.session_state["pending_nav"] = "New verification"
                st.rerun()

        with act_right:
            if st.button("Open officer desk", use_container_width=True):
                st.session_state["pending_nav"] = "Verification history"
                st.rerun()

    with side_col:
        ui(
            f"""
            <div class="standing">
            <div class="standing-head">
            <span class="standing-title">Officer evaluation unit</span>
            {pill("Active")}
            </div>
            <div class="standing-row"><span>Active vendor bids</span>
            <b>{stats['active_bidders']:02d}</b></div>
            <div class="standing-row"><span>Awaiting review</span>
            <b>{stats['pending']:02d}</b></div>
            <div class="standing-row"><span>Decisions recorded</span>
            <b>{stats['verified']:02d}</b></div>
            </div>
            """
        )

    st.write("")

    active = stats["active_bidders"]
    pending = stats["pending"]
    high_risk = stats["high_risk"]

    tiles = [
        (
            "Active bidders",
            f"{active}",
            "Across open procurement runs" if active else "Nothing open yet",
            False,
        ),
        (
            "Average compliance",
            f'{stats["average_compliance"]}%',
            "Across submitted packages" if active else "No packages submitted",
            False,
        ),
        (
            "Ready to review",
            f"{pending}",
            "Awaiting an officer decision" if pending else "Nothing waiting",
            False,
        ),
        (
            "High risk",
            f"{high_risk}",
            "Flagged discrepancies" if high_risk else "None flagged",
            bool(high_risk),
        ),
    ]

    for col, (label, value, note, attention) in zip(st.columns(4), tiles):
        with col:
            ui(
                f"""
                <div class="tile{' attention' if attention else ''}">
                <div class="tile-label">{escape(label)}</div>
                <div class="tile-value">{escape(value)}</div>
                <div class="tile-note">{escape(note)}</div>
                </div>
                """
            )

    st.write("")
    st.subheader("How a package moves through the desk")

    stages = [
        (
            "Stage 1",
            "Vendor submits",
            "NIT or RFP, BOQ, GST, PAN, Udyam, ITR, bank proof and technical "
            "documents go up as a single package.",
        ),
        (
            "Stage 2",
            "System screens",
            "Files are identified, required items are checked off, a compliance "
            "score is calculated, and every failed check is explained.",
        ),
        (
            "Stage 3",
            "Officer decides",
            "The officer reads the report, the bidder's history and the audit "
            "trail, then qualifies, disqualifies or holds the bid.",
        ),
    ]

    for col, (no, title, body) in zip(st.columns(3), stages):
        with col:
            ui(
                f"""
                <div class="stage">
                <span class="stage-no">{no}</span>
                <h4>{escape(title)}</h4>
                <p>{escape(body)}</p>
                </div>
                """
            )

    st.write("")
    st.subheader("Recent verifications")

    recent = data.get("recent", [])

    if not recent:
        st.info(
            "No verifications yet. Upload a package to run the first one."
        )
        return

    for item in recent:
        c1, c2, c3, c4, c5, c6 = st.columns([2.2, 1.4, 0.8, 0.9, 1.3, 0.9])

        c1.markdown(
            f"**{escape(str(item['bidder_name']))}**  \n"
            f"<span class='meta'>PAN <span class='mono'>"
            f"{escape(str(item['bidder_pan']))}</span> &nbsp; "
            f"{escape(str(item['tender_filename']))}</span>",
            unsafe_allow_html=True,
        )
        c2.write(stamp(item["timestamp"]))
        c3.write(score_text(item["score"]))
        c4.markdown(pill(item["risk"]), unsafe_allow_html=True)
        c5.write(item["decision"])

        if c6.button("Review", key=f"dash_{item['id']}", use_container_width=True):
            st.session_state["selected_verification"] = item["id"]
            st.session_state["nav_page"] = "Verification review"
            st.rerun()


# =============================================================================
# NEW VERIFICATION
# =============================================================================

def new_verification():
    st.header("New verification")
    st.caption(
        "Upload the tender once, then run every competing bid against it. "
        f"Each PDF can be up to {MAX_MB} MB."
    )

    tender = st.file_uploader(
        "Tender or RFP document (PDF)",
        type=["pdf"],
        key="uploader_tender",
        help="The official tender containing the eligibility and technical requirements.",
    )

    tender_oversized = False

    if tender:
        size_mb = len(tender.getvalue()) / (1024 * 1024)
        if size_mb > MAX_MB:
            st.error(
                f"{tender.name} is {size_mb:.1f} MB, over the {MAX_MB} MB limit. "
                "Compress it or split it before uploading."
            )
            tender_oversized = True
        else:
            st.success(f"Tender loaded: {tender.name} ({size_mb:.2f} MB)")

    vendors = st.file_uploader(
        "Vendor bid submissions (PDF, one or more)",
        type=["pdf"],
        accept_multiple_files=True,
        key="uploader_vendors",
        help="The bids submitted by competing vendors. Each bidder needs a PAN.",
    )

    if not vendors:
        st.info("Add at least one vendor bid to enter bidder details and run the checks.")
        return

    st.subheader("Bidder details")
    st.caption(
        "The PAN is what the prototype uses to cross-check the simulated "
        "government registries."
    )

    pans, names, oversized_files, bad_pans = [], [], [], []

    for i, f in enumerate(vendors):
        f_size_mb = len(f.getvalue()) / (1024 * 1024)
        if f_size_mb > MAX_MB:
            oversized_files.append(f"{f.name} ({f_size_mb:.1f} MB)")

        ui(
            f"""
            <div class="record">
            <b>Bid {i + 1}</b> &nbsp; {escape(f.name)}
            <span class="meta">&nbsp; {f_size_mb:.2f} MB</span>
            </div>
            """
        )

        col_name, col_pan, col_demo = st.columns([1.2, 1.2, 0.8])

        with col_name:
            v_name = st.text_input(
                f"Bidder name {i + 1}",
                value=st.session_state.get(f"name_val_{i}", ""),
                key=f"input_name_{i}",
                placeholder="Sample Vendor Pvt Ltd",
            )
            names.append(v_name)

        with col_pan:
            v_pan = (
                st.text_input(
                    f"Bidder PAN {i + 1}",
                    value=st.session_state.get(f"pan_val_{i}", ""),
                    key=f"input_pan_{i}",
                    placeholder="AABCU1234C",
                )
                .upper()
                .strip()
            )
            pans.append(v_pan)

            if v_pan and not PAN_RE.match(v_pan):
                bad_pans.append(i + 1)

        with col_demo:
            st.write("")
            if st.button(
                "Use demo details",
                key=f"demo_pan_btn_{i}",
                help="Fills in the verified demo vendor AABCU1234C.",
            ):
                st.session_state[f"pan_val_{i}"] = "AABCU1234C"
                st.session_state[f"name_val_{i}"] = "Sample Vendor Pvt Ltd"
                st.rerun()

    missing_pans = [i + 1 for i, p in enumerate(pans) if not p]

    if missing_pans:
        st.warning(
            "Add a PAN for bid "
            + ", ".join(str(n) for n in missing_pans)
            + "."
        )

    if bad_pans:
        st.warning(
            "PAN format looks wrong for bid "
            + ", ".join(str(n) for n in bad_pans)
            + ". A PAN is five letters, four digits, then one letter."
        )

    if oversized_files:
        st.error(f"Over the {MAX_MB} MB limit: " + ", ".join(oversized_files))

    can_submit = bool(
        tender
        and not tender_oversized
        and vendors
        and not oversized_files
        and not missing_pans
        and not bad_pans
    )

    st.write("")

    if st.button(
        "Run the checks",
        type="primary",
        use_container_width=True,
        disabled=not can_submit,
    ):
        try:
            with st.status("Running the verification pipeline", expanded=True) as status:
                st.write("Reading the tender and pulling out mandatory requirements")
                st.write("Checking that each bid belongs to this tender")
                st.write("Cross-checking PANs against the simulated registries")
                st.write("Screening for prompt injection and weighing the evidence")

                batch_res = client.batch_verify(tender, vendors, pans, names)

                status.update(
                    label=f"Done. {len(batch_res['results'])} bid(s) processed.",
                    state="complete",
                )

            st.session_state["last_batch"] = batch_res
            st.session_state["pending_nav"] = "Verification history"
            st.rerun()

        except APIError as err:
            st.error(f"The pipeline stopped: {err}")
        except Exception as e:
            st.error(f"The batch could not be processed: {e}")


# =============================================================================
# VERIFICATION HISTORY
# =============================================================================

def verification_history():
    st.header("Verification history")

    try:
        rows = client.history()
    except Exception as e:
        st.error(f"Records could not be loaded: {e}")
        return

    if "last_batch" in st.session_state:
        b = st.session_state["last_batch"]
        st.success(
            f"Batch {b.get('batch_id')} finished with {b.get('count')} bid(s). "
            "Open any row below to inspect the evidence."
        )

    if not rows:
        st.info("No stored verifications. Start one from New verification.")
        return

    st.caption(f"{len(rows)} record(s), stored in the SQLite backend.")

    for item in rows:
        r = item["result"]
        blocked = r.get("blocked", False)

        cols = st.columns([2.3, 1.2, 0.8, 0.9, 1.3, 0.9])

        cols[0].markdown(
            f"**{escape(str(item['bidder_name']))}**  \n"
            f"<span class='meta'>PAN <span class='mono'>"
            f"{escape(str(item['bidder_pan']))}</span> &nbsp; "
            f"{escape(str(item['vendor_filename']))}</span>",
            unsafe_allow_html=True,
        )
        cols[1].write(stamp(item["timestamp"]))
        cols[2].write("—" if blocked else score_text(r.get("compliance_score")))
        cols[3].markdown(
            pill("Blocked" if blocked else r.get("risk_level")),
            unsafe_allow_html=True,
        )
        cols[4].write(item["officer_decision"])

        if cols[5].button("Open", key=f"hist_{item['id']}", use_container_width=True):
            st.session_state["selected_verification"] = item["id"]
            st.session_state["nav_page"] = "Verification review"
            st.rerun()


# =============================================================================
# VERIFICATION REVIEW
# =============================================================================

def verification_review():
    vid = st.session_state.get("selected_verification")

    if not vid:
        st.info("Pick a verification from the history to review its evidence.")
        return

    try:
        item = client.verification(vid)
    except Exception as e:
        st.error(f"Verification {vid} could not be loaded: {e}")
        return

    r = item["result"]

    back_col, _ = st.columns([1, 4])
    with back_col:
        if st.button("Back to history"):
            st.session_state["nav_page"] = "Verification history"
            st.session_state.pop("selected_verification", None)
            st.rerun()

    st.header(item["bidder_name"])

    ui(
        f"""
        <div class="record">
        <span class="meta">PAN</span> <span class="mono">{escape(str(item['bidder_pan']))}</span>
        &nbsp;&nbsp;&nbsp;
        <span class="meta">Tender</span> {escape(str(item['tender_filename']))}
        &nbsp;&nbsp;&nbsp;
        <span class="meta">Bid</span> {escape(str(item['vendor_filename']))}
        &nbsp;&nbsp;&nbsp;
        <span class="meta">Run</span> <span class="mono">#{escape(str(item['id']))}</span>
        </div>
        """
    )

    st.write("")

    if r.get("blocked"):
        st.error("Verification blocked at the alignment gate.")
        st.markdown(
            "**Reason:** "
            + str(
                r.get("block_reason")
                or r.get("error")
                or "The document alignment check did not pass."
            )
        )
        st.info(
            "This bid does not appear to belong to the tender it was filed "
            "against. Check the files and resubmit the package."
        )
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Compliance score", score_text(r.get("compliance_score")))
    m2.metric("Risk level", r.get("risk_level", "Unknown"))
    m3.metric("Requirements checked", len(r.get("requirement_results", [])))
    m4.metric("Officer decision", item["officer_decision"])

    if r.get("alignment_warning"):
        st.warning(r["alignment_warning"])

    if r.get("injection_hits"):
        st.error(
            "Prompt injection guard triggered on "
            f"{len(r['injection_hits'])} phrase(s): "
            + ", ".join(r["injection_hits"])
        )

    if r.get("flags"):
        st.subheader("Flags raised")
        for flag in r["flags"]:
            st.markdown(f"- {flag}")

    st.subheader("Recommendation")
    st.caption("Advisory only. The officer makes the ruling.")
    st.info(r.get("recommendation", "No recommendation was returned."))

    tab_findings, tab_docs = st.tabs(["Requirement findings", "Documents"])

    with tab_findings:
        reqs = r.get("requirement_results", [])

        if not reqs:
            st.info("No requirement findings were returned for this submission.")
        else:
            for req in reqs:
                status = str(req.get("status", "UNVERIFIABLE")).upper()
                cls = (
                    "pass"
                    if status == "PASS"
                    else "fail"
                    if status == "FAIL"
                    else "review"
                )

                ui(
                    f"""
                    <div class="finding {cls}">
                    <div class="finding-head">
                    <b>{escape(str(req.get('requirement', 'Requirement')))}</b>
                    {pill(status)}
                    </div>
                    <span class="meta" title="{escape(str(req.get('category_help', '')))}">
                    {escape(str(req.get('category', 'Other')))}</span>
                    <p>{escape(str(req.get('evidence', 'No evidence recorded.')))}</p>
                    </div>
                    """
                )

    with tab_docs:
        st.caption("Read the original bid and tender inside the workspace.")

        doc_kind = st.radio(
            "Document",
            ["Vendor bid", "Tender or RFP"],
            horizontal=True,
        )

        kind_key = "vendor" if doc_kind == "Vendor bid" else "tender"
        curr_filename = (
            item["vendor_filename"] if kind_key == "vendor" else item["tender_filename"]
        )

        try:
            pdf_data = client.document(vid, kind_key)

            dl_col, _ = st.columns([1, 2])
            with dl_col:
                st.download_button(
                    label=f"Download ({len(pdf_data) / 1024 / 1024:.2f} MB)",
                    data=pdf_data,
                    file_name=curr_filename,
                    mime="application/pdf",
                    use_container_width=True,
                )

            render_pdf(pdf_data, height=620)

        except Exception as e:
            st.warning(f"The preview could not be loaded: {e}")

    st.subheader("Officer decision")
    st.caption("The officer records the final qualification ruling.")

    if item["officer_decision"] != "Not yet decided":
        st.success(f"Recorded decision: {item['officer_decision']}")

        if item.get("officer_notes"):
            st.markdown(f"**Notes:** {item['officer_notes']}")

        st.caption(f"Recorded by {item.get('officer_id') or 'PO-001'}")

    decision_options = [
        "Qualify bidder",
        "Disqualify bidder",
        "Hold for further review",
    ]

    default_idx = (
        decision_options.index(item["officer_decision"])
        if item["officer_decision"] in decision_options
        else 0
    )

    decision = st.radio(
        "Ruling", decision_options, index=default_idx, horizontal=True
    )

    notes = st.text_area(
        "Rationale",
        value=item.get("officer_notes", "") or "",
        placeholder="Justification, conditions for qualification, or grounds for disqualification.",
    )

    save_col, report_col = st.columns(2)

    with save_col:
        if st.button("Save decision", type="primary", use_container_width=True):
            try:
                client.decision(vid, decision, notes)
                st.success("Decision saved to the audit trail.")
                st.rerun()
            except Exception as e:
                st.error(f"The decision was not saved: {e}")

    with report_col:
        try:
            report_pdf = client.report(vid)
            st.download_button(
                "Download compliance report",
                report_pdf,
                file_name=f"SendaTender_Report_{item['bidder_pan']}_{vid}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.caption(f"Report generation is unavailable: {e}")


# =============================================================================
# BIDDER DIRECTORY
# =============================================================================

def bidder_directory():
    st.header("Bidder directory")
    st.caption(
        "Past evaluations, compliance performance and repeat flags across "
        "procurement cycles."
    )

    try:
        rows = client.bidders()
    except Exception as e:
        st.error(f"The directory could not be loaded: {e}")
        return

    search = st.text_input(
        "Search", placeholder="Bidder name or PAN"
    ).strip()

    filtered = [
        x
        for x in rows
        if not search
        or search.lower() in f"{x['bidder_name']} {x['bidder_pan']}".lower()
    ]

    if not filtered:
        st.info("No bidders match that search.")
        return

    for row in filtered:
        with st.expander(
            f"{row['bidder_name']}  —  {row['bidder_pan']}  —  "
            f"{row['verifications']} verification(s)"
        ):
            try:
                history_data = client.bidder(row["bidder_pan"])["history"]

                for hist_item in history_data:
                    hr = hist_item["result"]
                    c1, c2, c3, c4 = st.columns([2.2, 1.1, 1, 1.2])

                    c1.markdown(
                        f"**{escape(str(hist_item['tender_filename']))}**  \n"
                        f"<span class='meta'>{escape(str(hist_item['timestamp'])[:10])}</span>",
                        unsafe_allow_html=True,
                    )
                    c2.write(score_text(hr.get("compliance_score")))
                    c3.markdown(pill(hr.get("risk_level")), unsafe_allow_html=True)
                    c4.write(hist_item["officer_decision"])

                all_flags = []
                for hist_item in history_data:
                    for f in hist_item["result"].get("flags", []):
                        if f not in all_flags:
                            all_flags.append(f)

                if all_flags:
                    st.markdown("**Repeat flags**")
                    for flg in all_flags:
                        st.markdown(f"- {flg}")

            except Exception as e:
                st.error(f"This bidder's history could not be loaded: {e}")


# =============================================================================
# AUDIT TRAIL
# =============================================================================

def audit_trail():
    st.header("Audit trail")
    st.caption(
        "Every officer decision, with its timestamp, score, risk level and the "
        "recommendation it was weighed against."
    )

    try:
        rows = client.audit()
    except Exception as e:
        st.error(f"The audit trail could not be loaded: {e}")
        return

    if not rows:
        st.info("No decisions have been committed yet.")
        return

    for entry in rows:
        with st.expander(
            f"{entry['timestamp'][:19].replace('T', ' ')}  —  "
            f"{entry['bidder_name']}  —  {entry['officer_decision']}"
        ):
            st.markdown(f"**Officer:** `{entry.get('officer_id') or 'PO-001'}`")

            st.markdown(
                f"**Compliance score:** {entry['compliance_score']}/100 &nbsp; "
                f"**Risk:** {pill(entry['risk_level'])}",
                unsafe_allow_html=True,
            )

            st.markdown(
                f"**Recommendation:** {entry.get('ai_recommendation', '—')}"
            )

            if entry.get("officer_notes"):
                st.markdown(f"**Rationale:** {entry['officer_notes']}")

            if entry.get("verification_id"):
                try:
                    pdf_bytes = client.report(entry["verification_id"])
                    st.download_button(
                        "Download compliance report",
                        pdf_bytes,
                        file_name=f"SendaTender_Audit_{entry['id']}.pdf",
                        mime="application/pdf",
                        key=f"audit_pdf_{entry['id']}",
                    )
                except Exception:
                    pass


# =============================================================================
# OFFICER ACCOUNT
# =============================================================================

def officer_account():
    st.header("Officer account")

    ui(
        f"""
        <div class="tile">
        <div class="tile-label">Signed-in officer</div>
        <div class="tile-value" style="font-size:1.45rem;">
        {escape(str(st.session_state.get("officer_id", "")))}</div>
        <div class="tile-note">Evaluation committee officer, GeM decision support</div>
        </div>
        """
    )

    st.write("")
    st.subheader("Access")
    st.write(
        "Officer credentials are provisioned centrally. Public registration is "
        "off by design."
    )
    st.info(
        "A production deployment would sign officers in through government SSO "
        "and write the audit trail to HSM-backed storage."
    )

    st.subheader("Appearance")
    st.write(f"Current theme: {st.session_state.get('theme', 'light').title()}")
    st.caption("Switch it with the dark mode toggle in the sidebar.")


# =============================================================================
# ROUTER
# =============================================================================

ROUTES = {
    "Overview": dashboard,
    "New verification": new_verification,
    "Verification history": verification_history,
    "Verification review": verification_review,
    "Bidder directory": bidder_directory,
    "Audit trail": audit_trail,
    "Officer account": officer_account,
}

ROUTES.get(st.session_state.get("nav_page", "Overview"), dashboard)()
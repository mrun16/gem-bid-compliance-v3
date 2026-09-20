import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "audit_trail.db"))
MOCK_PORTAL_PATH = os.environ.get(
    "MOCK_PORTAL_PATH", os.path.join(BASE_DIR, "mock_portal_data.json")
)

# Bootstrap officer — used ONCE on first startup to seed the officers table.
# After the initial seed, officer records live in the SQLite database.
BOOTSTRAP_OFFICER_ID = os.environ.get("BOOTSTRAP_OFFICER_ID", "PO-001")
BOOTSTRAP_OFFICER_PASSWORD = os.environ.get("BOOTSTRAP_OFFICER_PASSWORD", "officer2026")

# Session token lifetime in seconds (default: 12 hours)
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", str(12 * 3600)))

CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501"
).split(",")

MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "..", "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)


BOOTSTRAP_OFFICER_ID = os.getenv(
    "BOOTSTRAP_OFFICER_ID",
    "PO-001",
)

BOOTSTRAP_OFFICER_PASSWORD = os.getenv(
    "BOOTSTRAP_OFFICER_PASSWORD",
    "",
)

PO_002_PASSWORD = os.getenv(
    "PO_002_PASSWORD",
    "",
)

PO_003_PASSWORD = os.getenv(
    "PO_003_PASSWORD",
    "",
)

SESSION_TTL_SECONDS = int(
    os.getenv("SESSION_TTL_SECONDS", "43200")
)

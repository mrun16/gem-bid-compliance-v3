import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt

from config import DB_PATH, MOCK_PORTAL_PATH, SESSION_TTL_SECONDS

# ---------------------------------------------------------------------------
# SCHEMA
# ---------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS officers (
    officer_id    TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    display_name  TEXT NOT NULL DEFAULT '',
    role          TEXT NOT NULL DEFAULT 'officer',
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS officer_sessions (
    token       TEXT PRIMARY KEY,
    officer_id  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    FOREIGN KEY (officer_id) REFERENCES officers(officer_id)
);

CREATE TABLE IF NOT EXISTS audit_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    bidder_pan TEXT NOT NULL,
    bidder_name TEXT NOT NULL,
    compliance_score INTEGER NOT NULL,
    risk_level TEXT NOT NULL,
    flags_json TEXT NOT NULL,
    ai_recommendation TEXT NOT NULL,
    officer_decision TEXT NOT NULL,
    officer_notes TEXT NOT NULL DEFAULT '',
    requirement_results_json TEXT NOT NULL DEFAULT '[]',
    rule_results_json TEXT NOT NULL DEFAULT '[]',
    verification_id INTEGER,
    officer_id TEXT
);

CREATE TABLE IF NOT EXISTS verification_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    bidder_pan TEXT NOT NULL,
    bidder_name TEXT NOT NULL,
    tender_filename TEXT NOT NULL,
    vendor_filename TEXT NOT NULL,
    tender_path TEXT,
    vendor_path TEXT,
    result_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'READY_FOR_REVIEW',
    officer_decision TEXT NOT NULL DEFAULT 'Not yet decided',
    officer_notes TEXT NOT NULL DEFAULT '',
    officer_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_verification_pan ON verification_runs(bidder_pan);
CREATE INDEX IF NOT EXISTS idx_verification_batch ON verification_runs(batch_id);
CREATE INDEX IF NOT EXISTS idx_audit_pan ON audit_entries(bidder_pan);
CREATE INDEX IF NOT EXISTS idx_sessions_officer ON officer_sessions(officer_id);
"""


# ---------------------------------------------------------------------------
# CONNECTION HELPER
# ---------------------------------------------------------------------------
@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_column(conn, table, column, definition):
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        # Safe migration for an existing V2 / early-V3 database.
        _ensure_column(conn, "audit_entries", "verification_id", "INTEGER")
        _ensure_column(conn, "audit_entries", "officer_id", "TEXT")


# ---------------------------------------------------------------------------
# OFFICER AUTH HELPERS (bcrypt-backed)
# ---------------------------------------------------------------------------
def _hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plain-text password."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _check_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def officer_exists(officer_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM officers WHERE officer_id = ?", (officer_id,)
        ).fetchone()
    return row is not None


def create_officer(
    officer_id: str,
    plain_password: str,
    display_name: str = "",
    role: str = "officer",
) -> dict:
    """Create a new officer record with a hashed password. Raises ValueError if ID already exists."""
    if officer_exists(officer_id):
        raise ValueError(f"Officer '{officer_id}' already exists.")
    password_hash = _hash_password(plain_password)
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO officers (officer_id, password_hash, display_name, role, is_active, created_at)
               VALUES (?, ?, ?, ?, 1, ?)""",
            (officer_id, password_hash, display_name or officer_id, role, created_at),
        )
    return get_officer(officer_id)


def get_officer(officer_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT officer_id, display_name, role, is_active, created_at FROM officers WHERE officer_id = ?",
            (officer_id,),
        ).fetchone()
    return dict(row) if row else None


def list_officers() -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT officer_id, display_name, role, is_active, created_at FROM officers ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def verify_officer_password(officer_id: str, plain_password: str) -> bool:
    """Return True if officer exists, is active, and password matches."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT password_hash, is_active FROM officers WHERE officer_id = ?",
            (officer_id,),
        ).fetchone()
    if not row or not row["is_active"]:
        return False
    return _check_password(plain_password, row["password_hash"])


def seed_bootstrap_officer(officer_id: str, plain_password: str) -> bool:
    """
    Create the bootstrap officer if the officers table is empty.
    Returns True if a new officer was seeded, False if already populated.
    """
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) c FROM officers").fetchone()["c"]
    if count > 0:
        return False
    create_officer(officer_id, plain_password, display_name=officer_id, role="officer")
    return True

def ensure_officer(
    officer_id: str,
    plain_password: str,
    display_name: str = "",
) -> bool:
    """
    Create an officer if that officer_id does not already exist.

    Returns:
        True  -> officer was created
        False -> officer already existed
    """
    officer_id = officer_id.strip().upper()

    if not officer_id:
        raise ValueError("Officer ID cannot be empty.")

    if not plain_password:
        raise ValueError(f"Password for {officer_id} cannot be empty.")

    if officer_exists(officer_id):
        return False

    create_officer(
        officer_id=officer_id,
        plain_password=plain_password,
        display_name=display_name or officer_id,
        role="officer",
    )
    return True


# ---------------------------------------------------------------------------
# SESSION MANAGEMENT
# ---------------------------------------------------------------------------
def create_session(officer_id: str) -> str:
    """Issue a new opaque session token for the officer. Returns the token."""
    token = secrets.token_hex(32)  # 64-char hex
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(seconds=SESSION_TTL_SECONDS)).isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO officer_sessions (token, officer_id, created_at, expires_at)
               VALUES (?, ?, ?, ?)""",
            (token, officer_id, now.isoformat(), expires_at),
        )
    return token


def get_session(token: str) -> Optional[str]:
    """
    Validate a session token.
    Returns the officer_id if the token exists and is not expired, else None.
    """
    if not token:
        return None
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """SELECT officer_id FROM officer_sessions
               WHERE token = ? AND expires_at > ?""",
            (token, now),
        ).fetchone()
    return row["officer_id"] if row else None


def delete_session(token: str) -> None:
    """Invalidate a session token (logout)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM officer_sessions WHERE token = ?", (token,))


def purge_expired_sessions() -> int:
    """Remove expired sessions. Returns number of rows deleted."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM officer_sessions WHERE expires_at <= ?", (now,))
        return cur.rowcount


# ---------------------------------------------------------------------------
# DECODE HELPERS
# ---------------------------------------------------------------------------
def _decode_audit(row):
    if not row:
        return None
    d = dict(row)
    d["flags"] = json.loads(d.pop("flags_json"))
    d["requirement_results"] = json.loads(d.pop("requirement_results_json"))
    d["rule_results"] = json.loads(d.pop("rule_results_json"))
    return d


def _decode_verification(row):
    if not row:
        return None
    d = dict(row)
    d["result"] = json.loads(d.pop("result_json"))
    return d


# ---------------------------------------------------------------------------
# VERIFICATION RUNS
# ---------------------------------------------------------------------------
def insert_verification_run(
    batch_id, bidder_pan, bidder_name, tender_filename, vendor_filename,
    tender_path, vendor_path, result, status="READY_FOR_REVIEW"
):
    timestamp = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO verification_runs
            (batch_id,timestamp,bidder_pan,bidder_name,tender_filename,vendor_filename,
             tender_path,vendor_path,result_json,status)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                batch_id, timestamp, bidder_pan, bidder_name, tender_filename, vendor_filename,
                tender_path, vendor_path, json.dumps(result), status,
            ),
        )
        rowid = cur.lastrowid
    return get_verification_run(rowid)


def get_verification_run(verification_id: int) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM verification_runs WHERE id = ?", (verification_id,)
        ).fetchone()
    return _decode_verification(row)


def list_verification_runs(limit=200):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM verification_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_decode_verification(r) for r in rows]


def update_verification_decision(verification_id, decision, notes, officer_id):
    with get_connection() as conn:
        conn.execute(
            """UPDATE verification_runs
               SET officer_decision=?, officer_notes=?, officer_id=?, status=?
               WHERE id=?""",
            (decision, notes, officer_id, "DECISION_RECORDED", verification_id),
        )
    return get_verification_run(verification_id)


# ---------------------------------------------------------------------------
# AUDIT ENTRIES
# ---------------------------------------------------------------------------
def insert_audit_entry(
    bidder_pan, bidder_name, compliance_score, risk_level, flags,
    ai_recommendation, officer_decision, officer_notes, requirement_results,
    rule_results, verification_id=None, officer_id=None
):
    timestamp = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO audit_entries
            (timestamp,bidder_pan,bidder_name,compliance_score,risk_level,flags_json,
             ai_recommendation,officer_decision,officer_notes,requirement_results_json,
             rule_results_json,verification_id,officer_id)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                timestamp, bidder_pan, bidder_name, compliance_score, risk_level,
                json.dumps(flags), ai_recommendation, officer_decision, officer_notes,
                json.dumps(requirement_results), json.dumps(rule_results),
                verification_id, officer_id,
            ),
        )
        rowid = cursor.lastrowid
    return get_audit_entry(rowid)


def get_audit_entry(entry_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM audit_entries WHERE id=?", (entry_id,)).fetchone()
    return _decode_audit(row)


def list_audit_entries(limit=200):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_entries ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_decode_audit(r) for r in rows]


# ---------------------------------------------------------------------------
# DASHBOARD / DIRECTORY
# ---------------------------------------------------------------------------
def dashboard_stats():
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(DISTINCT bidder_pan) c FROM verification_runs").fetchone()["c"]
        verified = conn.execute(
            "SELECT COUNT(*) c FROM verification_runs WHERE status IN ('DECISION_RECORDED','COMPLETED')"
        ).fetchone()["c"]
        pending = conn.execute(
            "SELECT COUNT(*) c FROM verification_runs WHERE status='READY_FOR_REVIEW'"
        ).fetchone()["c"]
        high = conn.execute(
            "SELECT COUNT(*) c FROM verification_runs WHERE UPPER(json_extract(result_json,'$.risk_level'))='HIGH'"
        ).fetchone()["c"]
        avg = conn.execute(
            "SELECT AVG(CAST(json_extract(result_json,'$.compliance_score') AS REAL)) a FROM verification_runs WHERE json_extract(result_json,'$.compliance_score') IS NOT NULL"
        ).fetchone()["a"]
    return {
        "active_bidders": total,
        "verified": verified,
        "pending": pending,
        "high_risk": high,
        "average_compliance": round(avg) if avg is not None else 0,
    }


def bidder_directory():
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT bidder_pan, bidder_name, COUNT(*) AS verifications,
                      MAX(timestamp) AS last_verified,
                      AVG(CAST(json_extract(result_json,'$.compliance_score') AS REAL)) AS avg_score
               FROM verification_runs
               GROUP BY bidder_pan, bidder_name
               ORDER BY last_verified DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def bidder_history(bidder_pan):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM verification_runs
               WHERE UPPER(bidder_pan)=UPPER(?)
               ORDER BY id DESC""", (bidder_pan,)
        ).fetchall()
    return [_decode_verification(r) for r in rows]


def load_portal_database():
    with open(MOCK_PORTAL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

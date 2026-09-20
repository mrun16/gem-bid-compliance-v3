import json
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

import database
import verification_service as vs
from config import (
    CORS_ORIGINS,
    BOOTSTRAP_OFFICER_ID,
    BOOTSTRAP_OFFICER_PASSWORD,
    PO_002_PASSWORD,
    PO_003_PASSWORD,
    MAX_FILE_SIZE_BYTES,
    MAX_FILE_SIZE_MB,
    UPLOAD_DIR,
)
from schemas import (
    VerificationResponse, AuditEntryCreate, AuditEntry, ReportRequest,
    OfficerLogin, OfficerLoginResponse, OfficerDecision,
)

app = FastAPI(
    title="SendaTender Procurement Verification API",
    description=(
        "SIH26100 decision-support backend. "
        "AI assists verification; an authorized officer makes the final decision."
    ),
    version="3.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# STARTUP
# ---------------------------------------------------------------------------
@app.on_event("startup")
def on_startup():
    database.init_db()

    # ---------------------------------------------------------
    # Bootstrap / provision authorized demo officers
    # ---------------------------------------------------------

    if BOOTSTRAP_OFFICER_PASSWORD:
        seeded = database.seed_bootstrap_officer(
            BOOTSTRAP_OFFICER_ID,
            BOOTSTRAP_OFFICER_PASSWORD,
        )

        if seeded:
            print(
                f"[SendaTender] Bootstrap officer "
                f"'{BOOTSTRAP_OFFICER_ID}' seeded."
            )
        else:
            print(
                f"[SendaTender] Bootstrap officer "
                f"'{BOOTSTRAP_OFFICER_ID}' already exists."
            )
    else:
        print(
            "[SendaTender] WARNING: "
            "BOOTSTRAP_OFFICER_PASSWORD is not configured."
        )

    # PO-002
    if PO_002_PASSWORD:
        created = database.ensure_officer(
            officer_id="PO-002",
            plain_password=PO_002_PASSWORD,
            display_name="Procurement Officer 002",
        )

        if created:
            print("[SendaTender] Officer 'PO-002' provisioned.")
        else:
            print("[SendaTender] Officer 'PO-002' already exists.")

    # PO-003
    if PO_003_PASSWORD:
        created = database.ensure_officer(
            officer_id="PO-003",
            plain_password=PO_003_PASSWORD,
            display_name="Procurement Officer 003",
        )

        if created:
            print("[SendaTender] Officer 'PO-003' provisioned.")
        else:
            print("[SendaTender] Officer 'PO-003' already exists.")

    # ---------------------------------------------------------
    # Remove expired sessions
    # ---------------------------------------------------------

    purged = database.purge_expired_sessions()

    if purged:
        print(
            f"[SendaTender] Purged {purged} expired session(s)."
        )

# ---------------------------------------------------------------------------
# AUTH DEPENDENCY
# ---------------------------------------------------------------------------
def require_officer_access(
    x_officer_token: Optional[str] = Header(default=None),
) -> str:
    """
    Validate the session token supplied in the x-officer-token header.
    Returns the authenticated officer_id on success, raises 401 on failure.
    """
    officer_id = database.get_session(x_officer_token or "")
    if not officer_id:
        raise HTTPException(
            status_code=401,
            detail="Valid officer session token required. Please log in.",
        )
    return officer_id


# ---------------------------------------------------------------------------
# UTILITY
# ---------------------------------------------------------------------------
def _safe_filename(name: str) -> str:
    return Path(name or "document.pdf").name.replace(" ", "_")


async def _read_pdf_checked(upload: UploadFile) -> bytes:
    if not (upload.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail=f"{upload.filename}: only PDF files are accepted.")
    data = await upload.read()
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"{upload.filename} exceeds the {MAX_FILE_SIZE_MB} MB per-file limit.",
        )
    if not data:
        raise HTTPException(status_code=400, detail=f"{upload.filename}: empty file.")
    return data


def _store_document(batch_id: str, role: str, filename: str, data: bytes) -> str:
    folder = Path(UPLOAD_DIR) / batch_id
    folder.mkdir(parents=True, exist_ok=True)
    safe = _safe_filename(filename)
    path = folder / f"{role}_{safe}"
    path.write_bytes(data)
    return str(path)


# ---------------------------------------------------------------------------
# HEALTH
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "version": "3.1.0", "max_file_size_mb": MAX_FILE_SIZE_MB}


# ---------------------------------------------------------------------------
# AUTHENTICATION ENDPOINTS
# ---------------------------------------------------------------------------
@app.post("/auth/login", response_model=OfficerLoginResponse)
def login(req: OfficerLogin):
    """
    Authenticate an officer and issue a session token.
    The token is stored in the database with a 12-hour expiry.
    """
    officer_id = req.officer_id.strip()
    if not officer_id or not req.password:
        raise HTTPException(status_code=400, detail="officer_id and password are required.")

    if not database.verify_officer_password(officer_id, req.password):
        raise HTTPException(status_code=401, detail="Invalid officer credentials.")

    token = database.create_session(officer_id)
    return {"authenticated": True, "officer_id": officer_id, "token": token}


@app.post("/auth/logout")
def logout(officer_id: str = Depends(require_officer_access),
           x_officer_token: Optional[str] = Header(default=None)):
    """Invalidate the current session token."""
    if x_officer_token:
        database.delete_session(x_officer_token)
    return {"logged_out": True}


@app.get("/auth/me")
def auth_me(officer_id: str = Depends(require_officer_access)):
    officer = database.get_officer(officer_id)
    return {
        "authenticated": True,
        "officer_id": officer_id,
        "display_name": (officer or {}).get("display_name", officer_id),
        "role": (officer or {}).get("role", "officer"),
    }


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
@app.get("/dashboard")
def dashboard(officer_id: str = Depends(require_officer_access)):
    stats = database.dashboard_stats()
    recent = database.list_verification_runs(limit=8)
    return {
        "stats": stats,
        "recent": [
            {
                "id": x["id"],
                "bidder_name": x["bidder_name"],
                "bidder_pan": x["bidder_pan"],
                "timestamp": x["timestamp"],
                "score": x["result"].get("compliance_score"),
                "risk": x["result"].get("risk_level"),
                "status": x["status"],
                "decision": x["officer_decision"],
                "tender_filename": x["tender_filename"],
            }
            for x in recent
        ],
    }


# ---------------------------------------------------------------------------
# SINGLE VERIFY (legacy — still used by /verify endpoint)
# ---------------------------------------------------------------------------
@app.post("/verify", response_model=VerificationResponse)
async def verify(
    tender_file: UploadFile = File(...),
    vendor_file: UploadFile = File(...),
    bidder_pan: str = Form(...),
    officer_id: str = Depends(require_officer_access),
):
    tender_bytes = await _read_pdf_checked(tender_file)
    vendor_bytes = await _read_pdf_checked(vendor_file)

    if not bidder_pan.strip():
        raise HTTPException(status_code=400, detail="Bidder PAN is required.")

    portal_db = database.load_portal_database()
    portal_record = portal_db.get(bidder_pan.strip().upper())

    try:
        result = vs.run_full_pipeline(tender_bytes, vendor_bytes, bidder_pan, portal_record)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    result.setdefault("blocked", False)
    return result


# ---------------------------------------------------------------------------
# BATCH VERIFY
# ---------------------------------------------------------------------------
@app.post("/verify/batch")
async def verify_batch(
    tender_file: UploadFile = File(...),
    vendor_files: list[UploadFile] = File(...),
    vendor_pans: str = Form(...),
    vendor_names: str = Form("[]"),
    officer_id: str = Depends(require_officer_access),
):
    """One tender + N vendor bids. Each bidder is verified independently."""
    tender_bytes = await _read_pdf_checked(tender_file)

    try:
        pans = json.loads(vendor_pans)
        names = json.loads(vendor_names or "[]")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="vendor_pans/vendor_names must be valid JSON arrays.")

    if not isinstance(pans, list) or len(pans) != len(vendor_files):
        raise HTTPException(status_code=400, detail="Each vendor bid must have its own PAN.")
    if names and len(names) != len(vendor_files):
        raise HTTPException(status_code=400, detail="Each vendor bid must have its own bidder name.")
    if not names:
        names = ["" for _ in vendor_files]

    batch_id = uuid.uuid4().hex[:12]
    tender_path = _store_document(batch_id, "tender", tender_file.filename, tender_bytes)
    portal_db = database.load_portal_database()
    results = []

    for index, vendor_file in enumerate(vendor_files):
        vendor_bytes = await _read_pdf_checked(vendor_file)
        pan = str(pans[index]).strip().upper()
        if not pan:
            raise HTTPException(status_code=400, detail=f"Vendor bid #{index + 1} is missing PAN.")

        vendor_path = _store_document(batch_id, f"vendor_{index+1}", vendor_file.filename, vendor_bytes)
        portal_record = portal_db.get(pan)

        try:
            result = vs.run_full_pipeline(tender_bytes, vendor_bytes, pan, portal_record)
        except RuntimeError as e:
            result = {"blocked": True, "error": str(e), "block_reason": "Backend verification error."}
        except Exception as e:
            result = {"blocked": True, "error": str(e), "block_reason": "Document could not be processed."}

        bidder_name = (
            str(names[index]).strip()
            or result.get("bidder_name")
            or (portal_record or {}).get("bidder_name")
            or f"Vendor {index + 1}"
        )
        result["bidder_name"] = bidder_name
        result["bidder_pan"] = pan

        status = "BLOCKED" if result.get("blocked") else "READY_FOR_REVIEW"
        saved = database.insert_verification_run(
            batch_id=batch_id,
            bidder_pan=pan,
            bidder_name=bidder_name,
            tender_filename=tender_file.filename,
            vendor_filename=vendor_file.filename,
            tender_path=tender_path,
            vendor_path=vendor_path,
            result=result,
            status=status,
        )
        results.append({
            "id": saved["id"],
            "batch_id": batch_id,
            "bidder_name": bidder_name,
            "bidder_pan": pan,
            "vendor_filename": vendor_file.filename,
            "status": status,
            "score": result.get("compliance_score"),
            "risk": result.get("risk_level"),
            "blocked": result.get("blocked", False),
            "block_reason": result.get("block_reason"),
            "alignment_warning": result.get("alignment_warning"),
        })

    return {"batch_id": batch_id, "count": len(results), "results": results}


# ---------------------------------------------------------------------------
# VERIFICATION DETAIL & DOCUMENTS
# ---------------------------------------------------------------------------
@app.get("/verification/{verification_id}")
def get_verification(verification_id: int, officer_id: str = Depends(require_officer_access)):
    item = database.get_verification_run(verification_id)
    if not item:
        raise HTTPException(status_code=404, detail="Verification not found.")
    return item


@app.get("/verification/{verification_id}/document/{kind}")
def get_verification_document(
    verification_id: int,
    kind: str,
    officer_id: str = Depends(require_officer_access),
):
    item = database.get_verification_run(verification_id)
    if not item:
        raise HTTPException(status_code=404, detail="Verification not found.")
    if kind not in {"tender", "vendor"}:
        raise HTTPException(status_code=400, detail="Document kind must be tender or vendor.")
    path = item["tender_path"] if kind == "tender" else item["vendor_path"]
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Stored document not found.")
    return Response(content=Path(path).read_bytes(), media_type="application/pdf")


# ---------------------------------------------------------------------------
# OFFICER DECISION
# ---------------------------------------------------------------------------
@app.post("/verification/{verification_id}/decision")
def save_verification_decision(
    verification_id: int,
    req: OfficerDecision,
    officer_id: str = Depends(require_officer_access),
):
    if req.decision not in {"Qualify bidder", "Disqualify bidder", "Hold for further review"}:
        raise HTTPException(status_code=400, detail="Invalid officer decision.")

    item = database.get_verification_run(verification_id)
    if not item:
        raise HTTPException(status_code=404, detail="Verification not found.")

    # officer_id comes from the authenticated session — not from the request body
    updated = database.update_verification_decision(
        verification_id, req.decision, req.notes, officer_id
    )
    result = item["result"]
    saved = database.insert_audit_entry(
        bidder_pan=item["bidder_pan"],
        bidder_name=item["bidder_name"],
        compliance_score=int(result.get("compliance_score") or 0),
        risk_level=result.get("risk_level") or "Unknown",
        flags=result.get("flags") or [],
        ai_recommendation=result.get("recommendation") or "",
        officer_decision=req.decision,
        officer_notes=req.notes,
        requirement_results=result.get("requirement_results") or [],
        rule_results=result.get("rule_results") or [],
        verification_id=verification_id,
        officer_id=officer_id,   # always the session-authenticated officer
    )
    return {"verification": updated, "audit_entry": saved}


# ---------------------------------------------------------------------------
# REPORT
# ---------------------------------------------------------------------------
@app.get("/verification/{verification_id}/report")
def report_for_verification(verification_id: int, officer_id: str = Depends(require_officer_access)):
    item = database.get_verification_run(verification_id)
    if not item:
        raise HTTPException(status_code=404, detail="Verification not found.")
    r = item["result"]
    pdf = vs.generate_compliance_pdf(
        bidder_name=item["bidder_name"],
        bidder_pan=item["bidder_pan"],
        score=int(r.get("compliance_score") or 0),
        risk=r.get("risk_level") or "Unknown",
        flags=r.get("flags") or [],
        recommendation=r.get("recommendation") or "",
        requirement_results=r.get("requirement_results") or [],
        rule_results=r.get("rule_results") or [],
        officer_decision=item["officer_decision"],
        officer_notes=item["officer_notes"],
    )
    return Response(content=pdf, media_type="application/pdf")


# ---------------------------------------------------------------------------
# HISTORY / BIDDER DIRECTORY / AUDIT
# ---------------------------------------------------------------------------
@app.get("/history")
def history(officer_id: str = Depends(require_officer_access)):
    return database.list_verification_runs()


@app.get("/bidder-directory")
def bidder_directory(officer_id: str = Depends(require_officer_access)):
    return database.bidder_directory()


@app.get("/bidder/{bidder_pan}")
def bidder_history(bidder_pan: str, officer_id: str = Depends(require_officer_access)):
    return {
        "bidder_pan": bidder_pan.upper(),
        "history": database.bidder_history(bidder_pan),
    }


@app.post("/audit", response_model=AuditEntry)
def create_audit_entry(entry: AuditEntryCreate, officer_id: str = Depends(require_officer_access)):
    saved = database.insert_audit_entry(
        bidder_pan=entry.bidder_pan,
        bidder_name=entry.bidder_name,
        compliance_score=entry.compliance_score,
        risk_level=entry.risk_level,
        flags=entry.flags,
        ai_recommendation=entry.ai_recommendation,
        officer_decision=entry.officer_decision,
        officer_notes=entry.officer_notes,
        requirement_results=entry.requirement_results,
        rule_results=entry.rule_results,
        verification_id=entry.verification_id,
        officer_id=officer_id,  # always session-authenticated
    )
    return saved


@app.get("/audit", response_model=list[AuditEntry])
def get_audit_trail(officer_id: str = Depends(require_officer_access)):
    return database.list_audit_entries()


# ---------------------------------------------------------------------------
# PORTAL DATABASE (admin/debug)
# ---------------------------------------------------------------------------
@app.get("/portal-database")
def get_portal_database(officer_id: str = Depends(require_officer_access)):
    return database.load_portal_database()


# ---------------------------------------------------------------------------
# REPORT ENDPOINTS
# ---------------------------------------------------------------------------
@app.post("/report/preview")
def generate_report_preview(req: ReportRequest, officer_id: str = Depends(require_officer_access)):
    pdf_bytes = vs.generate_compliance_pdf(
        bidder_name=req.bidder_name,
        bidder_pan=req.bidder_pan,
        score=req.compliance_score,
        risk=req.risk_level,
        flags=req.flags,
        recommendation=req.recommendation,
        requirement_results=req.requirement_results,
        rule_results=req.rule_results,
        officer_decision=req.officer_decision,
        officer_notes=req.officer_notes,
    )
    return Response(content=pdf_bytes, media_type="application/pdf")


@app.get("/audit/{entry_id}/report")
def generate_report_from_audit(entry_id: int, officer_id: str = Depends(require_officer_access)):
    entry = database.get_audit_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Audit entry not found.")
    pdf_bytes = vs.generate_compliance_pdf(
        bidder_name=entry["bidder_name"],
        bidder_pan=entry["bidder_pan"],
        score=entry["compliance_score"],
        risk=entry["risk_level"],
        flags=entry["flags"],
        recommendation=entry["ai_recommendation"],
        requirement_results=entry["requirement_results"],
        rule_results=entry["rule_results"],
        officer_decision=entry["officer_decision"],
        officer_notes=entry["officer_notes"],
    )
    return Response(content=pdf_bytes, media_type="application/pdf")

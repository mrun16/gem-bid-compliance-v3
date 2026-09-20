import json
import os
import uuid

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import database

from config import (
    BOOTSTRAP_OFFICER_ID,
    BOOTSTRAP_OFFICER_PASSWORD,
    CORS_ORIGINS,
    MAX_FILE_SIZE_BYTES,
    PO_002_PASSWORD,
    PO_003_PASSWORD,
    UPLOAD_DIR,
)


# ---------------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SendaTender V3 API",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in CORS_ORIGINS
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# SCHEMAS
# ---------------------------------------------------------------------------

class OfficerLogin(BaseModel):
    officer_id: str
    password: str


class OfficerLoginResponse(BaseModel):
    authenticated: bool
    officer_id: str
    token: str


class DecisionRequest(BaseModel):
    decision: str
    notes: str = ""
    officer_id: str = ""


# ---------------------------------------------------------------------------
# STARTUP
# ---------------------------------------------------------------------------

@app.on_event("startup")
def on_startup():
    database.init_db()

    # ---------------------------------------------------------
    # PO-001 / Bootstrap officer
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

    # ---------------------------------------------------------
    # PO-002
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # PO-003
    # ---------------------------------------------------------
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
    # SAFE PASSWORD DIAGNOSTIC
    # ---------------------------------------------------------

    if BOOTSTRAP_OFFICER_PASSWORD:
        check = database.verify_officer_password(
            BOOTSTRAP_OFFICER_ID,
            BOOTSTRAP_OFFICER_PASSWORD,
        )

        print(
            f"[SendaTender] Password verification check for "
            f"{BOOTSTRAP_OFFICER_ID}: {check}"
        )

    if PO_002_PASSWORD:
        check = database.verify_officer_password(
            "PO-002",
            PO_002_PASSWORD,
        )

        print(
            f"[SendaTender] Password verification check for "
            f"PO-002: {check}"
        )

    if PO_003_PASSWORD:
        check = database.verify_officer_password(
            "PO-003",
            PO_003_PASSWORD,
        )

        print(
            f"[SendaTender] Password verification check for "
            f"PO-003: {check}"
        )

    # ---------------------------------------------------------
    # Clean expired sessions
    # ---------------------------------------------------------

    purged = database.purge_expired_sessions()

    if purged:
        print(
            f"[SendaTender] Purged {purged} expired session(s)."
        )


# ---------------------------------------------------------------------------
# HEALTH
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "service": "SendaTender V3 API",
        "status": "online",
        "version": "3.0.0",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "SendaTender V3 API",
    }


# ---------------------------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------------------------

@app.post(
    "/auth/login",
    response_model=OfficerLoginResponse,
)
def login(req: OfficerLogin):
    officer_id = req.officer_id.strip().upper()

    if not officer_id or not req.password:
        raise HTTPException(
            status_code=400,
            detail="officer_id and password are required.",
        )

    # IMPORTANT:
    # Password is intentionally NOT stripped or modified.
    if not database.verify_officer_password(
        officer_id,
        req.password,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid officer credentials.",
        )

    token = database.create_session(officer_id)

    return {
        "authenticated": True,
        "officer_id": officer_id,
        "token": token,
    }


@app.post("/auth/logout")
def logout(
    x_officer_token: str | None = Header(default=None),
):
    if x_officer_token:
        database.delete_session(x_officer_token)

    return {
        "success": True,
        "message": "Signed out successfully.",
    }


# ---------------------------------------------------------------------------
# AUTH HELPER
# ---------------------------------------------------------------------------

def require_officer(
    x_officer_token: str | None = Header(default=None),
) -> str:

    if not x_officer_token:
        raise HTTPException(
            status_code=401,
            detail="Officer authentication required.",
        )

    officer_id = database.get_session(x_officer_token)

    if not officer_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired officer session.",
        )

    return officer_id


# ---------------------------------------------------------------------------
# ACCOUNT
# ---------------------------------------------------------------------------

@app.get("/account")
def account(
    officer_id: str = Depends(require_officer),
):
    officer = database.get_officer(officer_id)

    if not officer:
        raise HTTPException(
            status_code=404,
            detail="Officer account not found.",
        )

    return officer


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------

@app.get("/dashboard")
def dashboard(
    officer_id: str = Depends(require_officer),
):
    stats = database.dashboard_stats()

    return {
        "officer_id": officer_id,
        **stats,
    }


# ---------------------------------------------------------------------------
# OFFICERS
# ---------------------------------------------------------------------------

@app.get("/officers")
def officers(
    officer_id: str = Depends(require_officer),
):
    return {
        "officers": database.list_officers(),
    }


# ---------------------------------------------------------------------------
# BATCH VERIFICATION
# ---------------------------------------------------------------------------

@app.post("/verify/batch")
async def verify_batch(
    tender_file: UploadFile = File(...),
    vendor_files: list[UploadFile] = File(...),
    vendor_pans: str = Form("[]"),
    vendor_names: str = Form("[]"),
    officer_id: str = Depends(require_officer),
):
    if not tender_file.filename:
        raise HTTPException(
            status_code=400,
            detail="Tender document is required.",
        )

    if not vendor_files:
        raise HTTPException(
            status_code=400,
            detail="At least one vendor bid is required.",
        )

    # ---------------------------------------------------------
    # Read and validate tender
    # ---------------------------------------------------------

    tender_bytes = await tender_file.read()

    if not tender_bytes:
        raise HTTPException(
            status_code=400,
            detail="Tender document is empty.",
        )

    if len(tender_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Tender file exceeds the maximum allowed size.",
        )

    # ---------------------------------------------------------
    # Parse bidder metadata
    # ---------------------------------------------------------

    try:
        pans = json.loads(vendor_pans)
    except Exception:
        pans = []

    try:
        names = json.loads(vendor_names)
    except Exception:
        names = []

    if not isinstance(pans, list):
        pans = []

    if not isinstance(names, list):
        names = []

    batch_id = str(uuid.uuid4())

    # ---------------------------------------------------------
    # IMPORTANT:
    # The verification service exposes run_full_pipeline()
    # as a function. There is NO VerificationService class.
    # ---------------------------------------------------------

    from verification_service import run_full_pipeline

    results = []

    # ---------------------------------------------------------
    # Save tender source document once for this batch
    # ---------------------------------------------------------

    batch_upload_dir = os.path.join(
        UPLOAD_DIR,
        batch_id,
    )

    os.makedirs(
        batch_upload_dir,
        exist_ok=True,
    )

    safe_tender_name = os.path.basename(
        tender_file.filename
    )

    tender_path = os.path.join(
        batch_upload_dir,
        f"tender_{safe_tender_name}",
    )

    with open(tender_path, "wb") as tender_out:
        tender_out.write(tender_bytes)

    # ---------------------------------------------------------
    # Process every vendor bid
    # ---------------------------------------------------------

    for index, vendor_file in enumerate(vendor_files):

        if not vendor_file.filename:
            raise HTTPException(
                status_code=400,
                detail=f"Vendor file #{index + 1} has no filename.",
            )

        vendor_bytes = await vendor_file.read()

        if not vendor_bytes:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Vendor file '{vendor_file.filename}' "
                    "is empty."
                ),
            )

        if len(vendor_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Vendor file '{vendor_file.filename}' "
                    "exceeds the maximum allowed size."
                ),
            )

        pan = (
            str(pans[index]).strip().upper()
            if index < len(pans)
            else ""
        )

        name = (
            str(names[index]).strip()
            if index < len(names)
            else vendor_file.filename
        )

        if not name:
            name = vendor_file.filename

        # -----------------------------------------------------
        # Save vendor source document
        # -----------------------------------------------------

        safe_vendor_name = os.path.basename(
            vendor_file.filename
        )

        vendor_path = os.path.join(
            batch_upload_dir,
            f"vendor_{index + 1}_{safe_vendor_name}",
        )

        with open(vendor_path, "wb") as vendor_out:
            vendor_out.write(vendor_bytes)

        # -----------------------------------------------------
        # Portal record
        # -----------------------------------------------------

        portal_record = None

        try:
            portal_data = database.load_portal_database()

            if isinstance(portal_data, dict):
                portal_record = portal_data.get(pan)

                # Also support records whose PAN casing differs.
                if portal_record is None and pan:
                    for key, record in portal_data.items():
                        if str(key).upper() == pan.upper():
                            portal_record = record
                            break

            elif isinstance(portal_data, list):
                for record in portal_data:
                    if (
                        str(record.get("pan", "")).upper()
                        == pan.upper()
                    ):
                        portal_record = record
                        break

        except Exception:
            portal_record = None

        # -----------------------------------------------------
        # Verification
        # -----------------------------------------------------

        try:
            result = run_full_pipeline(
                tender_bytes,
                vendor_bytes,
                pan,
                portal_record,
            )

        except Exception:
            # Never expose traceback/internal implementation details
            # to the procurement officer.
            result = {
                "blocked": True,
                "status": "ERROR",
                "risk_level": "UNKNOWN",
                "compliance_score": 0,
                "flags": [
                    "Verification service error. "
                    "Please review the documents manually."
                ],
                "recommendation": (
                    "Manual review required because automated "
                    "verification could not be completed."
                ),
            }

        # -----------------------------------------------------
        # Store verification
        # -----------------------------------------------------

        verification = database.insert_verification_run(
            batch_id=batch_id,
            bidder_pan=pan,
            bidder_name=name,
            tender_filename=tender_file.filename,
            vendor_filename=vendor_file.filename,
            tender_path=tender_path,
            vendor_path=vendor_path,
            result=result,
            status=(
                "BLOCKED"
                if result.get("blocked")
                else "READY_FOR_REVIEW"
            ),
        )

        results.append(
            {
                "verification_id": verification["id"],
                "batch_id": batch_id,
                "bidder_pan": pan,
                "bidder_name": name,
                "tender_filename": tender_file.filename,
                "vendor_filename": vendor_file.filename,
                "result": result,
            }
        )

    return {
        "batch_id": batch_id,
        "officer_id": officer_id,
        "count": len(results),
        "results": results,
    }


# ---------------------------------------------------------------------------
# VERIFICATION DETAILS
# ---------------------------------------------------------------------------

@app.get("/verification/{verification_id}")
def verification(
    verification_id: int,
    officer_id: str = Depends(require_officer),
):
    result = database.get_verification_run(
        verification_id
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Verification not found.",
        )

    return result


# ---------------------------------------------------------------------------
# DOCUMENT VIEWER
# ---------------------------------------------------------------------------

@app.get("/verification/{verification_id}/document/{kind}")
def verification_document(
    verification_id: int,
    kind: str,
    officer_id: str = Depends(require_officer),
):
    verification = database.get_verification_run(
        verification_id
    )

    if not verification:
        raise HTTPException(
            status_code=404,
            detail="Verification not found.",
        )

    if kind not in {"tender", "vendor"}:
        raise HTTPException(
            status_code=400,
            detail="Document kind must be 'tender' or 'vendor'.",
        )

    path_key = f"{kind}_path"
    path = verification.get(path_key)

    if not path or not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail="Source document is not available.",
        )

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=os.path.basename(path),
    )


# ---------------------------------------------------------------------------
# OFFICER DECISION
# ---------------------------------------------------------------------------

@app.post("/verification/{verification_id}/decision")
def record_decision(
    verification_id: int,
    req: DecisionRequest,
    officer_id: str = Depends(require_officer),
):
    verification = database.get_verification_run(
        verification_id
    )

    if not verification:
        raise HTTPException(
            status_code=404,
            detail="Verification not found.",
        )

    decision = req.decision.strip()

    if not decision:
        raise HTTPException(
            status_code=400,
            detail="Decision is required.",
        )

    updated = database.update_verification_decision(
        verification_id=verification_id,
        decision=decision,
        notes=req.notes.strip(),
        officer_id=officer_id,
    )

    return updated


# ---------------------------------------------------------------------------
# HISTORY
# ---------------------------------------------------------------------------

@app.get("/history")
def history(
    officer_id: str = Depends(require_officer),
):
    return {
        "officer_id": officer_id,
        "items": database.list_verification_runs(),
    }


# ---------------------------------------------------------------------------
# BIDDER DIRECTORY
# ---------------------------------------------------------------------------

@app.get("/bidder-directory")
def bidder_directory(
    officer_id: str = Depends(require_officer),
):
    return {
        "items": database.bidder_directory(),
    }


@app.get("/bidder/{pan}")
def bidder(
    pan: str,
    officer_id: str = Depends(require_officer),
):
    return {
        "pan": pan,
        "history": database.bidder_history(pan),
    }


# ---------------------------------------------------------------------------
# AUDIT TRAIL
# ---------------------------------------------------------------------------

@app.get("/audit")
def audit(
    officer_id: str = Depends(require_officer),
):
    return {
        "items": database.list_audit_entries(),
    }


# ---------------------------------------------------------------------------
# REPORT
# ---------------------------------------------------------------------------

@app.get("/verification/{verification_id}/report")
def verification_report(
    verification_id: int,
    officer_id: str = Depends(require_officer),
):
    verification = database.get_verification_run(
        verification_id
    )

    if not verification:
        raise HTTPException(
            status_code=404,
            detail="Verification not found.",
        )

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    reports_dir = os.path.join(
        os.path.dirname(__file__),
        "..",
        "reports",
    )

    os.makedirs(
        reports_dir,
        exist_ok=True,
    )

    report_path = os.path.join(
        reports_dir,
        f"verification_{verification_id}.pdf",
    )

    result = verification.get("result", {})

    c = canvas.Canvas(
        report_path,
        pagesize=A4,
    )

    width, height = A4
    y = height - 50

    c.setFont(
        "Helvetica-Bold",
        18,
    )

    c.drawString(
        40,
        y,
        "SendaTender V3 Verification Report",
    )

    y -= 35

    c.setFont(
        "Helvetica",
        10,
    )

    lines = [
        f"Verification ID: {verification_id}",
        f"Bidder: {verification.get('bidder_name', '')}",
        f"PAN: {verification.get('bidder_pan', '')}",
        f"Tender: {verification.get('tender_filename', '')}",
        f"Vendor Bid: {verification.get('vendor_filename', '')}",
        f"Officer: {officer_id}",
        "",
        f"Risk Level: {result.get('risk_level', 'UNKNOWN')}",
        f"Compliance Score: {result.get('compliance_score', 'N/A')}",
        "",
        "AI Verification Result:",
        str(
            result.get(
                "recommendation",
                result.get("ai_recommendation", ""),
            )
        ),
    ]

    for line in lines:
        if y < 50:
            c.showPage()
            y = height - 50
            c.setFont(
                "Helvetica",
                10,
            )

        c.drawString(
            40,
            y,
            line[:110],
        )

        y -= 18

    c.save()

    return FileResponse(
        report_path,
        media_type="application/pdf",
        filename=f"verification_{verification_id}.pdf",
    )
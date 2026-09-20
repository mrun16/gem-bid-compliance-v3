"""
Comprehensive integration test suite for SendaTender FastAPI backend.
Tests health, authentication, dashboard stats, batch verification, PDF retrieval,
officer decision recording, compliance report generation, and audit logging.
"""
import os
import sys

# Ensure backend directory is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import json
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from starlette.testclient import TestClient

import main
import database

def create_sample_pdf(content_text: str) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf)
    styles = getSampleStyleSheet()
    doc.build([Paragraph(content_text, styles["Normal"])])
    return buf.getvalue()

def run_tests():
    database.init_db()
    client = TestClient(main.app)

    # 1. Health check
    res = client.get("/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    health_data = res.json()
    assert health_data["status"] == "ok"
    assert health_data["max_file_size_mb"] == 50
    print("[PASS] GET /health: OK")

    # 2. Login
    res = client.post("/auth/login", json={"officer_id": "PO-001", "password": "officer2026"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    token = res.json()["token"]
    assert token == "officer2026"
    headers = {"x-officer-token": token}
    print("[PASS] POST /auth/login: OK")

    # 3. Unauthorized access check
    bad_res = client.get("/dashboard", headers={"x-officer-token": "wrong-token"})
    assert bad_res.status_code == 401
    print("[PASS] Auth guard 401 on bad token: OK")

    # 4. Dashboard
    res = client.get("/dashboard", headers=headers)
    assert res.status_code == 200, f"Dashboard failed: {res.text}"
    dash = res.json()
    assert "stats" in dash
    assert "recent" in dash
    print("[PASS] GET /dashboard: OK")

    # 5. Batch Verification
    tender_pdf = create_sample_pdf(
        "GeM Tender Notice for IT Equipment Supply. Mandatory eligibility requirements: "
        "Udyam registration certificate, GST active status, PAN validation, "
        "Make in India 50 percent local content, EPFO and ESIC compliance, OEM authorization."
    )
    vendor1_pdf = create_sample_pdf(
        "Bid Submission by Sample Vendor Pvt Ltd. PAN: AABCU1234C. "
        "Udyam Registration UDYAM-MH-01-0012345 attached. Active GSTIN on record. "
        "Make in India local content 62 percent. OEM authorization attached. EPFO/ESIC compliant."
    )
    vendor2_pdf = create_sample_pdf(
        "Bid Submission by Global Solutions Ltd. PAN: AABCU1234C. "
        "We agree to supply the required items according to tender specifications."
    )

    files = [
        ("tender_file", ("tender_2026.pdf", tender_pdf, "application/pdf")),
        ("vendor_files", ("vendor1_bid.pdf", vendor1_pdf, "application/pdf")),
        ("vendor_files", ("vendor2_bid.pdf", vendor2_pdf, "application/pdf")),
    ]
    form_data = {
        "vendor_pans": json.dumps(["AABCU1234C", "AABCU1234C"]),
        "vendor_names": json.dumps(["Sample Vendor Pvt Ltd", "Global Solutions Ltd"]),
    }

    res = client.post("/verify/batch", files=files, data=form_data, headers=headers)
    assert res.status_code == 200, f"Batch verification failed: {res.text}"
    batch_res = res.json()
    assert "batch_id" in batch_res
    assert len(batch_res["results"]) == 2
    ver_id = batch_res["results"][0]["id"]
    print(f"[PASS] POST /verify/batch: OK (Batch ID: {batch_res['batch_id']}, 2 bidders verified)")

    # 6. Retrieve verification details
    res = client.get(f"/verification/{ver_id}", headers=headers)
    assert res.status_code == 200
    v_data = res.json()
    assert v_data["bidder_pan"] == "AABCU1234C"
    print(f"[PASS] GET /verification/{ver_id}: OK")

    # 7. Document retrieval
    res_doc = client.get(f"/verification/{ver_id}/document/vendor", headers=headers)
    assert res_doc.status_code == 200
    assert res_doc.headers["content-type"] == "application/pdf"
    assert len(res_doc.content) > 0
    print(f"[PASS] GET /verification/{ver_id}/document/vendor: OK ({len(res_doc.content)} bytes)")

    # 8. Record Officer Decision
    res_dec = client.post(
        f"/verification/{ver_id}/decision",
        json={
            "decision": "Qualify bidder",
            "notes": "Verified all statutory documents and portal records. Bidder meets all criteria.",
            "officer_id": "PO-001",
        },
        headers=headers,
    )
    assert res_dec.status_code == 200
    dec_data = res_dec.json()
    assert dec_data["verification"]["officer_decision"] == "Qualify bidder"
    assert dec_data["verification"]["status"] == "DECISION_RECORDED"
    print("[PASS] POST /verification/{id}/decision: OK")

    # 9. Download Compliance Report PDF
    res_rep = client.get(f"/verification/{ver_id}/report", headers=headers)
    assert res_rep.status_code == 200
    assert res_rep.headers["content-type"] == "application/pdf"
    assert len(res_rep.content) > 1000
    print(f"[PASS] GET /verification/{ver_id}/report: OK ({len(res_rep.content)} bytes)")

    # 10. Bidder directory and history
    res_bidders = client.get("/bidder-directory", headers=headers)
    assert res_bidders.status_code == 200
    assert len(res_bidders.json()) >= 1
    print(f"[PASS] GET /bidder-directory: OK ({len(res_bidders.json())} bidders)")

    res_b_hist = client.get("/bidder/AABCU1234C", headers=headers)
    assert res_b_hist.status_code == 200
    assert len(res_b_hist.json()["history"]) >= 1
    print("[PASS] GET /bidder/AABCU1234C: OK")

    # 11. Audit trail
    res_audit = client.get("/audit", headers=headers)
    assert res_audit.status_code == 200
    assert len(res_audit.json()) >= 1
    print(f"[PASS] GET /audit: OK ({len(res_audit.json())} audit entries)")

    print("\n==========================================")
    print("ALL 11 BACKEND API TESTS PASSED SUCCESSFULLY!")
    print("==========================================")

if __name__ == "__main__":
    run_tests()

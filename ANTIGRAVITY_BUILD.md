# ANTIGRAVITY — BUILD INSTRUCTIONS

You have been given a complete `gem-v3` project generated from the user's uploaded `gem-v2`.

## CRITICAL SAFETY RULE

Do not modify the user's original `gem-v2` directory.

This folder is the new V3 project. Work only inside this project.

Do not copy `.env`, API keys, `.venv`, or Streamlit secrets from V2.

## What has already been implemented

The project already contains:
- Streamlit frontend
- FastAPI backend
- existing V2 Gemini verification pipeline
- batch verification endpoint
- 50 MB per-PDF validation
- officer authentication
- SQLite verification-run storage
- bidder history
- audit trail
- PDF reports
- document storage
- document/evidence viewer
- polished SendaTender UI

The UI reference is `UI_REFERENCE.png`.

The V3 UI also includes a user-controlled Light / Dark appearance switch. Preserve it and improve it if useful. A better-than-reference UI is welcome as long as it remains professional, fast, readable, and procurement-workspace focused.

## Your job

1. Inspect every file.
2. Compare the V3 code against the supplied V2 source only when needed to confirm compatibility.
3. Do not replace working verification logic unnecessarily.
4. Fix integration/runtime issues you find.
5. Run syntax/import checks.
6. Start FastAPI and Streamlit locally if the environment permits.
7. Test `/health`.
8. Test officer login.
9. Test database initialization.
10. If a Gemini key is unavailable, do not invent one. Verify everything that can be verified without a live Gemini call.
11. Keep the UI visually close to `UI_REFERENCE.png`.

## Do NOT

- introduce React
- introduce Next.js
- move Gemini calls into Streamlit
- expose GEMINI_API_KEY to the frontend
- add public officer registration
- remove the alignment gate
- replace the officer decision with an AI decision
- lower the 50 MB file limit
- hard-code dashboard statistics
- fabricate government portal integration

## If changes are required

Prefer small compatibility fixes over rewrites.

The intended architecture is:

Streamlit
  ↓
FastAPI
  ↓
verification_service.py
  ↓
rules + Gemini
  ↓
SQLite / reports / stored documents

## Demo acceptance

The finished app should let an officer:

1. Sign in.
2. See the SendaTender dashboard.
3. Upload one tender.
4. Add multiple vendor bids.
5. Enter each bidder's PAN.
6. Run all verifications.
7. See blocked mismatched documents.
8. Open a bidder result.
9. See requirement findings and evidence.
10. Open the actual vendor PDF in the evidence area.
11. Record Qualify / Disqualify / Hold.
12. Download a report.
13. Find the bidder in Bidder Directory.
14. See previous stored verifications.
15. Open the protected Audit Trail.

The application is a decision-support prototype. The officer makes the final decision.

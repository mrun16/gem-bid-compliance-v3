# SendaTender V3

A separate upgrade of the supplied `gem-v2` project. **The original V2 project is not modified.**

## What is new

- Polished Streamlit officer workspace matching the supplied SendaTender visual direction
- Officer login / protected workspace
- Dashboard backed by SQLite data
- One tender + multiple vendor bids
- 50 MB maximum per PDF, enforced in Streamlit and FastAPI
- Tender ↔ bid alignment gate
- Evidence-first requirement findings
- Stored verification runs
- Document retrieval / embedded PDF evidence viewer
- Officer decision workflow
- Bidder directory and stored verification history
- Protected audit trail
- PDF report generation
- Existing V2 Gemini/rule-engine pipeline preserved and extended rather than replaced

## Project layout

```text
gem-v3/
├── backend/
│   ├── main.py
│   ├── verification_service.py
│   ├── database.py
│   ├── schemas.py
│   ├── config.py
│   ├── rules.py
│   ├── requirement_help.py
│   ├── mock_portal_data.json
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app.py
│   ├── api_client.py
│   ├── requirements.txt
│   └── .streamlit/config.toml
├── uploads/
├── reports/
└── README.md
```

## Setup

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
# Put your Gemini key in backend/.env

uvicorn main:app --reload --port 8000
```

### Frontend

Open a second terminal:

```bash
cd frontend
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt

streamlit run app.py
```

Default prototype credentials are controlled by `backend/.env`:
- Officer ID: `PO-001`
- Password: value of `OFFICER_ACCESS_CODE`

Change the password before demonstrating publicly.

## Important

Do not copy the real V2 `.env` or Streamlit secrets into this project.

Gemini remains backend-only:

```text
Streamlit → FastAPI → verification_service.py → Gemini
```

## Verification flow

```text
One Tender
    ↓
Multiple Vendor Bids
    ↓
Document Alignment
    ↓
Requirement Extraction
    ↓
Deterministic Rules + Gemini
    ↓
Evidence / Findings
    ↓
Officer Review
    ↓
Officer Decision
    ↓
Audit Trail + PDF Report
```

The AI recommendation is advisory. The authorized procurement officer records the final decision.

## Prototype data notice

The supplied V2 project uses `mock_portal_data.json` for Udyam, GSTN, PAN, EPFO/ESIC, Startup India, NSIC and blacklist-style checks. V3 keeps that prototype approach. It does not claim live government portal access.


## Appearance

The Streamlit frontend supports a Light / Dark workspace switch in the sidebar (and on the login screen). The visual direction remains based on the supplied SendaTender reference, with permission to improve polish without adding unnecessary complexity.

# ForgeLedger

Freelance invoice, expense and proposal command center.

**Author / signature: Mourad.Soltani** · **v1.1.0**

Built as a sellable 2026 micro-SaaS: agencies and independent operators still assemble proposals in docs and chase invoices in spreadsheets. ForgeLedger keeps clients, invoices, expenses and proposal drafts in one local-first product that can be licensed or hosted.

## Why this product

Validated demand in 2026 clusters around:

- freelancer client portals and billing
- proposal generators for agencies
- subscription / invoice hygiene for SMBs

ForgeLedger ships the wedge that closes those buyers: issue numbered invoices, track billable spend, generate a signed proposal, export PDF, and collect payment via Stripe (or demo checkout offline).

## Stack

- FastAPI + SQLAlchemy + SQLite
- ReportLab PDF export
- Stripe Checkout (optional; demo mode without keys)
- Vanilla HTML/CSS/JS console
- Pytest health suite

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Open http://127.0.0.1:8080

Health: http://127.0.0.1:8080/health

### Optional env

| Variable | Purpose |
|---|---|
| `STRIPE_SECRET_KEY` | Live Stripe Checkout |
| `FORGELEDGER_STUDIO_NAME` | White-label product name |
| `FORGELEDGER_FOOTER` | White-label footer text |
| `FORGELEDGER_HIDE_SIGNATURE` | `1` hides Mourad.Soltani line on PDFs (licensed) |
| `FORGELEDGER_DB` | SQLite path override |

## Tests

```bash
FORGELEDGER_DB=/tmp/forgeledger-test.db pytest -q
```

Expected: all tests pass, `/health` returns `"status": "ok"` and `"author": "Mourad.Soltani"`.

## Commercial positioning

- **Buyer:** freelance studios, 1–10 person agencies, fractional operators
- **Price suggestion:** $29/mo solo · $79/mo studio · $1,490 lifetime license
- **Close motion:** 15-minute demo on their last unpaid invoice, export PDF, collect via Checkout, then send a branded proposal generated inside the product

## License to sell

Commercial rights reserved by Mourad.Soltani unless a written license is issued.

— Mourad.Soltani

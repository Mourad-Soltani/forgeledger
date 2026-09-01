# Dev-team context snapshot — Mourad.Soltani

Use this file to resume if a free-tier or session limit is hit.

## Product
ForgeLedger v1.1.0 — freelance invoice / expense / proposal command center.

## Done
- FastAPI app with clients, invoices, expenses, proposals
- Health endpoint (+ pdf / stripe checks)
- UI console
- Pytest suite
- Sales kit + buyer shortlist
- GitHub push: https://github.com/Mourad-Soltani/forgeledger
- PDF invoice export (reportlab)
- Stripe checkout (demo mode offline; live when STRIPE_SECRET_KEY set)
- White-label brand API (FORGELEDGER_STUDIO_NAME / FOOTER / HIDE_SIGNATURE)

## Next
- Stripe webhook to auto-mark paid
- Multi-line invoice editor in UI
- Hosted deploy (Railway / Fly)
- License key gate for white-label

## Health command
FORGELEDGER_DB=/tmp/forgeledger-test.db pytest -q

## Signature
Mourad.Soltani

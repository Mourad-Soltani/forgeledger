# ForgeLedger

Freelance **invoice · proposal · portal · payments** command center.

**Author / signature: Mourad.Soltani** · **v1.10.0**

> **Buy the founding license — $1,490 lifetime** (source + white-label)  
> Open [`/onboarding`](./templates/onboarding.html) on a running instance or `POST /api/commerce/founding-license`  
> Solo SaaS **$29/mo** · Studio **$79/mo** · see [docs/SALES.md](docs/SALES.md) & [docs/VALUATION.md](docs/VALUATION.md)

Agencies still assemble proposals in docs and chase invoices in spreadsheets. ForgeLedger keeps clients, multi-currency invoices, expenses, recurring billing, reminders, PDF, Stripe Checkout, client portal (Pay now), CSV export, and multi-user API keys in one product you can self-host or license.

## Quick start

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
# or: docker compose up --build
```

- Console: http://127.0.0.1:8080  
- Onboarding / license: http://127.0.0.1:8080/onboarding  
- Health: http://127.0.0.1:8080/health  
- Login (API key mode): http://127.0.0.1:8080/login  

## Tests

```bash
FORGELEDGER_DB=/tmp/fl-test.db pytest -q
```

## Signature

Commercial rights reserved by **Mourad.Soltani** unless a written license is issued.

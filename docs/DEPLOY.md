# Deploy notes — Mourad.Soltani

## Railway / Fly / any Docker host

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Required env for production

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET` (endpoint: `/api/stripe/webhook`)
- `FORGELEDGER_LICENSE_KEY` (enables white-label)
- Optional: `FORGELEDGER_STUDIO_NAME`, `FORGELEDGER_FOOTER`, `FORGELEDGER_HIDE_SIGNATURE=1`

## Webhook

Point Stripe to `https://YOUR_HOST/api/stripe/webhook` for `checkout.session.completed`.
Metadata must include `invoice_id`.

— Mourad.Soltani

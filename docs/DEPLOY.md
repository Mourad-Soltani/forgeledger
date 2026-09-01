# Deploy notes — Mourad.Soltani

## Docker

```bash
docker compose up --build -d
# health: curl localhost:8080/health
```

Image uses non-root user, SQLite volume at `/data`, healthcheck on `/health`.

## Railway / Fly / any host

Use the included `Dockerfile`. Set:

| Env | Purpose |
|---|---|
| `STRIPE_SECRET_KEY` | Live Checkout |
| `STRIPE_WEBHOOK_SECRET` | Webhook verify |
| `FORGELEDGER_PUBLIC_URL` | e.g. `https://app.example.com` (success/cancel links) |
| `FORGELEDGER_LICENSE_KEY` | Active white-label key |
| `FORGELEDGER_LICENSE_SECRET` | HMAC secret for issued keys |
| `FORGELEDGER_ADMIN_TOKEN` | Required to call `/api/admin/license/issue` |
| `FORGELEDGER_STUDIO_NAME` / `FOOTER` / `HIDE_SIGNATURE` | Branding (licensed only) |

Webhook URL: `https://YOUR_HOST/api/stripe/webhook`  
Success page: `https://YOUR_HOST/success?paid=1`

## Issue a license key

```bash
curl -X POST https://YOUR_HOST/api/admin/license/issue \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $FORGELEDGER_ADMIN_TOKEN" \
  -d '{"seed":"ACME2026","tier":"founder"}'
```

— Mourad.Soltani


## Cron

```bash
# inside container or host with curl access to the API
15 6 * * * FORGELEDGER_PUBLIC_URL=https://YOUR_HOST /path/to/scripts/cron_jobs.sh
```

Reminder emails include a signed client portal link (14-day TTL by default).

— Mourad.Soltani

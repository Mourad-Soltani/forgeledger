#!/usr/bin/env bash
# ForgeLedger daily jobs — Mourad.Soltani
# crontab example: 15 6 * * * /app/scripts/cron_jobs.sh >> /data/cron.log 2>&1
set -euo pipefail
BASE="${FORGELEDGER_PUBLIC_URL:-http://127.0.0.1:8080}"
curl -fsS -X POST "$BASE/api/jobs/run-recurring" || true
curl -fsS -X POST "$BASE/api/jobs/run-reminders" || true

"""License key gate for white-label — Mourad.Soltani / ForgeLedger."""

import hashlib
import hmac
import os
from functools import lru_cache


def _digest(key: str) -> str:
    secret = os.environ.get("FORGELEDGER_LICENSE_SECRET", "forgeledger-mourad-soltani-2026")
    return hmac.new(secret.encode(), key.encode(), hashlib.sha256).hexdigest()[:24]


def validate_license(key: str | None) -> dict:
    """
    Accept keys shaped FL-XXXX-XXXX-XXXX when they match the HMAC of the body,
    or the explicit env FORGELEDGER_LICENSE_KEY.
    """
    if not key:
        return {"valid": False, "tier": "unlicensed", "white_label": False}
    env_key = os.environ.get("FORGELEDGER_LICENSE_KEY", "").strip()
    if env_key and key.strip() == env_key:
        return {"valid": True, "tier": "studio", "white_label": True, "author": "Mourad.Soltani"}
    parts = key.strip().upper().split("-")
    if len(parts) == 4 and parts[0] == "FL":
        body = "-".join(parts[1:3])
        expected = _digest(body).upper()[:8]
        if parts[3] == expected:
            return {"valid": True, "tier": "founder", "white_label": True, "author": "Mourad.Soltani"}
    return {"valid": False, "tier": "invalid", "white_label": False}


@lru_cache(maxsize=1)
def active_license() -> dict:
    key = os.environ.get("FORGELEDGER_LICENSE_KEY")
    return validate_license(key)


def issue_demo_key(seed: str = "STUDIO") -> str:
    """Dev helper — not for production issuance."""
    body = seed.upper()[:8].ljust(8, "X")
    mid = body[:4] + "-" + body[4:]
    sig = _digest(body).upper()[:8]
    return f"FL-{mid}-{sig}"

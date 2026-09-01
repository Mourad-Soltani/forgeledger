"""License key gate for white-label — Mourad.Soltani / ForgeLedger."""

import hashlib
import hmac
import os
import secrets
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
        expected = _digest(body.replace("-", "")).upper()[:8]
        # body for digest is 8 chars without dash: parts[1]+parts[2]
        body_compact = (parts[1] + parts[2])[:8]
        expected = _digest(body_compact).upper()[:8]
        if parts[3] == expected:
            return {"valid": True, "tier": "founder", "white_label": True, "author": "Mourad.Soltani"}
    return {"valid": False, "tier": "invalid", "white_label": False}


@lru_cache(maxsize=1)
def active_license() -> dict:
    key = os.environ.get("FORGELEDGER_LICENSE_KEY")
    return validate_license(key)


def issue_key(seed: str | None = None, tier: str = "founder") -> dict:
    """Issue a signed FL-XXXX-XXXX-XXXXXXXX key. Admin-only in production."""
    raw = (seed or secrets.token_hex(4)).upper().replace("-", "")[:8].ljust(8, "X")
    mid = f"{raw[:4]}-{raw[4:8]}"
    sig = _digest(raw).upper()[:8]
    key = f"FL-{mid}-{sig}"
    check = validate_license(key)
    return {
        "key": key,
        "tier": tier if check.get("valid") else check.get("tier"),
        "valid": check.get("valid"),
        "white_label": check.get("white_label"),
        "author": "Mourad.Soltani",
    }


def issue_demo_key(seed: str = "STUDIO") -> str:
    return issue_key(seed=seed)["key"]

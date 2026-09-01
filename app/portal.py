"""Client portal magic links — Mourad.Soltani / ForgeLedger."""

import hashlib
import hmac
import os
import time
from typing import Optional


def _secret() -> str:
    return os.environ.get(
        "FORGELEDGER_PORTAL_SECRET",
        os.environ.get("FORGELEDGER_LICENSE_SECRET", "forgeledger-mourad-soltani-2026"),
    )


def mint_portal_token(client_id: int, ttl_seconds: int = 60 * 60 * 24 * 14) -> str:
    """Signed token: client_id.expiry.signature"""
    exp = int(time.time()) + ttl_seconds
    body = f"{client_id}.{exp}"
    sig = hmac.new(_secret().encode(), body.encode(), hashlib.sha256).hexdigest()[:20]
    return f"{body}.{sig}"


def verify_portal_token(token: str) -> Optional[int]:
    try:
        client_id_s, exp_s, sig = token.split(".")
        body = f"{client_id_s}.{exp_s}"
        expected = hmac.new(_secret().encode(), body.encode(), hashlib.sha256).hexdigest()[:20]
        if not hmac.compare_digest(sig, expected):
            return None
        if int(exp_s) < int(time.time()):
            return None
        return int(client_id_s)
    except Exception:
        return None

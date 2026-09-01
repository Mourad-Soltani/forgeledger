"""White-label branding — Mourad.Soltani / ForgeLedger."""

import os
from functools import lru_cache

from .license import active_license


@lru_cache(maxsize=1)
def get_brand() -> dict:
    """
    Env-driven white-label config.
    White-label (hide signature / custom name) requires a valid license.
    """
    lic = active_license()
    licensed = bool(lic.get("valid") and lic.get("white_label"))
    hide_requested = os.environ.get("FORGELEDGER_HIDE_SIGNATURE", "").lower() in {
        "1",
        "true",
        "yes",
    }
    # Only hide Mourad.Soltani signature when licensed
    hide = hide_requested and licensed
    studio = os.environ.get("FORGELEDGER_STUDIO_NAME", "ForgeLedger")
    if not licensed:
        studio = "ForgeLedger"
    footer = os.environ.get(
        "FORGELEDGER_FOOTER",
        "ForgeLedger © 2026 · Designed, built and signed by Mourad.Soltani",
    )
    if not licensed:
        footer = "ForgeLedger © 2026 · Designed, built and signed by Mourad.Soltani"
    return {
        "studio_name": studio,
        "footer": footer,
        "show_signature": not hide,
        "licensed": licensed,
        "license_tier": lic.get("tier", "unlicensed"),
        "product": "ForgeLedger",
        "author": "Mourad.Soltani",
    }

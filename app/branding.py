"""White-label branding — Mourad.Soltani / ForgeLedger."""

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def get_brand() -> dict:
    """
    Env-driven white-label config.
    Set FORGELEDGER_STUDIO_NAME, FORGELEDGER_FOOTER, FORGELEDGER_HIDE_SIGNATURE=1
    for licensed white-label deployments.
    """
    hide = os.environ.get("FORGELEDGER_HIDE_SIGNATURE", "").lower() in {"1", "true", "yes"}
    return {
        "studio_name": os.environ.get("FORGELEDGER_STUDIO_NAME", "ForgeLedger"),
        "footer": os.environ.get(
            "FORGELEDGER_FOOTER",
            "ForgeLedger © 2026 · Designed, built and signed by Mourad.Soltani",
        ),
        "show_signature": not hide,
        "product": "ForgeLedger",
        "author": "Mourad.Soltani",
    }

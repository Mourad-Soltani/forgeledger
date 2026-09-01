"""Stripe checkout + webhook (demo-safe) — Mourad.Soltani / ForgeLedger."""

import json
import os
import secrets
from typing import Optional


def stripe_configured() -> bool:
    return bool(os.environ.get("STRIPE_SECRET_KEY"))


def create_checkout_session(
    *,
    invoice_id: int,
    invoice_number: str,
    amount_cents: int,
    currency: str,
    customer_email: Optional[str] = None,
    success_url: str = "http://127.0.0.1:8080/?paid=1",
    cancel_url: str = "http://127.0.0.1:8080/?canceled=1",
) -> dict:
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        demo_id = f"cs_demo_{secrets.token_hex(8)}"
        return {
            "id": demo_id,
            "url": f"{success_url}&session_id={demo_id}&demo=1",
            "mode": "demo",
            "invoice_id": invoice_id,
            "amount_cents": amount_cents,
            "currency": currency.lower(),
            "author": "Mourad.Soltani",
            "message": "Demo checkout — set STRIPE_SECRET_KEY for live Stripe.",
        }

    try:
        import stripe

        stripe.api_key = key
        session = stripe.checkout.Session.create(
            mode="payment",
            success_url=success_url + "&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            customer_email=customer_email or None,
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": currency.lower(),
                        "unit_amount": amount_cents,
                        "product_data": {
                            "name": f"Invoice {invoice_number}",
                            "description": "Payment collected via ForgeLedger · Mourad.Soltani",
                        },
                    },
                }
            ],
            metadata={
                "invoice_id": str(invoice_id),
                "invoice_number": invoice_number,
                "product": "ForgeLedger",
                "author": "Mourad.Soltani",
            },
        )
        return {
            "id": session.id,
            "url": session.url,
            "mode": "live",
            "invoice_id": invoice_id,
            "amount_cents": amount_cents,
            "currency": currency.lower(),
            "author": "Mourad.Soltani",
        }
    except Exception as exc:
        return {
            "id": None,
            "url": None,
            "mode": "error",
            "error": str(exc),
            "author": "Mourad.Soltani",
        }


def parse_webhook_event(payload: bytes, sig_header: Optional[str]) -> dict:
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if secret and sig_header:
        try:
            import stripe

            event = stripe.Webhook.construct_event(payload, sig_header, secret)
            return {"ok": True, "mode": "live", "event": event, "author": "Mourad.Soltani"}
        except Exception as exc:
            return {"ok": False, "mode": "live", "error": str(exc), "author": "Mourad.Soltani"}

    try:
        body = json.loads(payload.decode() or "{}")
    except Exception:
        return {"ok": False, "mode": "demo", "error": "invalid json", "author": "Mourad.Soltani"}
    return {"ok": True, "mode": "demo", "event": body, "author": "Mourad.Soltani"}


def invoice_id_from_event(event) -> Optional[int]:
    if not event:
        return None
    if hasattr(event, "type"):
        etype = event.type
        data_obj = event.data.object if event.data else None
        meta = getattr(data_obj, "metadata", None) or {}
        if etype == "checkout.session.completed":
            raw = meta.get("invoice_id") if isinstance(meta, dict) else getattr(meta, "invoice_id", None)
            return int(raw) if raw is not None else None
        return None
    if event.get("type") != "checkout.session.completed":
        return None
    meta = (event.get("data") or {}).get("object", {}).get("metadata") or {}
    raw = meta.get("invoice_id")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def create_billing_portal_session(
    *,
    customer_id: str,
    return_url: str = "http://127.0.0.1:8080/",
) -> dict:
    """Stripe Customer Portal deep link (live only)."""
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        return {
            "url": None,
            "mode": "demo",
            "message": "Set STRIPE_SECRET_KEY and a Stripe customer id to open Billing Portal.",
            "author": "Mourad.Soltani",
        }
    try:
        import stripe

        stripe.api_key = key
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return {
            "url": session.url,
            "mode": "live",
            "author": "Mourad.Soltani",
        }
    except Exception as exc:
        return {
            "url": None,
            "mode": "error",
            "error": str(exc),
            "author": "Mourad.Soltani",
        }


def webhook_status() -> dict:
    return {
        "stripe_secret": bool(os.environ.get("STRIPE_SECRET_KEY")),
        "webhook_secret": bool(os.environ.get("STRIPE_WEBHOOK_SECRET")),
        "webhook_path": "/api/stripe/webhook",
        "author": "Mourad.Soltani",
    }


FOUNDING_LICENSE_AMOUNT_CENTS = int(__import__("os").environ.get("FORGELEDGER_FOUNDING_PRICE_CENTS", "149000"))


def create_founding_license_checkout(
    *,
    email: str | None = None,
    success_url: str = "http://127.0.0.1:8080/onboarding?licensed=1",
    cancel_url: str = "http://127.0.0.1:8080/onboarding?canceled=1",
) -> dict:
    """One-time founding license SKU ($1,490 default)."""
    import secrets
    key = os.environ.get("STRIPE_SECRET_KEY")
    amount = FOUNDING_LICENSE_AMOUNT_CENTS
    if not key:
        demo_id = f"cs_license_{secrets.token_hex(6)}"
        return {
            "id": demo_id,
            "url": f"{success_url}&session_id={demo_id}&demo=1",
            "mode": "demo",
            "amount_cents": amount,
            "product": "ForgeLedger Founding License",
            "author": "Mourad.Soltani",
            "message": "Demo license checkout — set STRIPE_SECRET_KEY for live charges.",
        }
    try:
        import stripe
        stripe.api_key = key
        session = stripe.checkout.Session.create(
            mode="payment",
            success_url=success_url + "&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            customer_email=email or None,
            line_items=[{
                "quantity": 1,
                "price_data": {
                    "currency": "usd",
                    "unit_amount": amount,
                    "product_data": {
                        "name": "ForgeLedger Founding License",
                        "description": "Lifetime source + white-label rights · Mourad.Soltani",
                    },
                },
            }],
            metadata={
                "product": "founding_license",
                "author": "Mourad.Soltani",
            },
        )
        return {
            "id": session.id,
            "url": session.url,
            "mode": "live",
            "amount_cents": amount,
            "product": "ForgeLedger Founding License",
            "author": "Mourad.Soltani",
        }
    except Exception as exc:
        return {"id": None, "url": None, "mode": "error", "error": str(exc), "author": "Mourad.Soltani"}

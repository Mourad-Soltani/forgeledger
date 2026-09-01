"""Stripe checkout (demo-safe) — Mourad.Soltani / ForgeLedger."""

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
    """
    Create a Stripe Checkout Session when STRIPE_SECRET_KEY is set.
    Otherwise return a demo session so the product stays fully testable offline.
    """
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
        import stripe  # optional dependency

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

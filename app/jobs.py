"""Recurring invoices + reminder digests — Mourad.Soltani / ForgeLedger."""

from datetime import date, timedelta
from sqlalchemy.orm import Session
from . import models, services
from .email_invoice import build_invoice_email, send_invoice_email, smtp_configured
from .pdf_export import build_invoice_pdf
from .branding import get_brand
from .portal import mint_portal_token
import os


def _advance(d: date, cadence: str) -> date:
    cadence = (cadence or "monthly").lower()
    if cadence == "weekly":
        return d + timedelta(days=7)
    if cadence == "quarterly":
        return d + timedelta(days=90)
    # monthly ~ 30 days
    return d + timedelta(days=30)


def run_recurring(db: Session) -> dict:
    today = date.today()
    due = (
        db.query(models.RecurringInvoice)
        .filter(models.RecurringInvoice.active.is_(True))
        .filter(models.RecurringInvoice.next_run <= today)
        .all()
    )
    created = []
    for r in due:
        client = db.get(models.Client, r.client_id)
        if not client or getattr(client, "archived", False):
            continue
        inv = models.Invoice(
            number=services.next_invoice_number(db),
            client_id=r.client_id,
            issue_date=today,
            due_date=today + timedelta(days=14),
            status="sent",
            currency=r.currency or "USD",
            notes=f"Auto-generated from recurring #{r.id} · Mourad.Soltani",
        )
        db.add(inv)
        db.flush()
        db.add(
            models.LineItem(
                invoice_id=inv.id,
                description=r.description or "Retainer",
                qty=1.0,
                unit_price=float(r.amount or 0),
            )
        )
        r.last_invoice_id = inv.id
        r.next_run = _advance(r.next_run or today, r.cadence)
        created.append({"recurring_id": r.id, "invoice_id": inv.id, "number": inv.number})
    db.commit()
    return {"created": created, "count": len(created), "author": "Mourad.Soltani"}


def run_reminders(db: Session) -> dict:
    """Email clients about overdue / due-soon invoices (demo if no SMTP)."""
    today = date.today()
    invs = (
        db.query(models.Invoice)
        .filter(models.Invoice.status.in_(("sent", "overdue")))
        .filter(models.Invoice.archived.is_(False))
        .all()
    )
    brand = get_brand()
    base = os.environ.get("FORGELEDGER_PUBLIC_URL", "http://127.0.0.1:8080").rstrip("/")
    results = []
    for inv in invs:
        if inv.due_date and inv.due_date < today and inv.status != "overdue":
            inv.status = "overdue"
        if not inv.due_date:
            continue
        days = (inv.due_date - today).days
        # remind if overdue or due within 3 days
        if days > 3:
            continue
        client = db.get(models.Client, inv.client_id)
        if not client or not client.email:
            results.append({"invoice_id": inv.id, "skipped": "no email"})
            continue
        msg = build_invoice_email(invoice=inv, client=client, brand=brand, public_url=base)
        prefix = "OVERDUE: " if days < 0 else "Reminder: "
        msg["subject"] = prefix + msg["subject"]
        try:
            token = mint_portal_token(client.id)
            portal = f"{base}/portal/{token}"
            msg["body"] = msg["body"] + f"\n\nClient portal (view & pay): {portal}\n"
        except Exception:
            pass
        pdf_bytes = build_invoice_pdf(inv, client, brand)
        sent = send_invoice_email(msg, pdf_bytes=pdf_bytes)
        results.append(
            {
                "invoice_id": inv.id,
                "number": inv.number,
                "days_to_due": days,
                "mode": sent.get("mode"),
                "sent": sent.get("sent"),
            }
        )
    db.commit()
    return {
        "reminders": results,
        "count": len([r for r in results if r.get("sent") or r.get("mode") == "demo"]),
        "smtp": smtp_configured(),
        "author": "Mourad.Soltani",
    }

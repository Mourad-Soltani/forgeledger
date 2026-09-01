"""Business logic — Mourad.Soltani / ForgeLedger."""

from datetime import date
from sqlalchemy.orm import Session
from . import models


def next_invoice_number(db: Session) -> str:
    count = db.query(models.Invoice).count() + 1
    year = date.today().year
    return f"FL-{year}-{count:04d}"


def generate_proposal_body(data) -> str:
    """Template engine — no external LLM required for MVP."""
    return f"""# {data.title}

Prepared for {data.client_name or "the client"}
by Mourad.Soltani — ForgeLedger

## The problem
{data.problem or "The current process is manual, slow, and leaking margin."}

## The proposed solution
{data.solution or "A focused delivery plan with weekly checkpoints and a single owner."}

## Scope
{data.scope or "Discovery, implementation, handoff documentation, and 14 days of hypercare."}

## Investment
{data.investment:,.2f} USD

## Timeline
{data.timeline or "3–6 weeks depending on access and feedback speed."}

## Why this works
Clear scope. Fixed checkpoints. Written acceptance criteria. No surprise invoices.

— Mourad.Soltani
"""


def dashboard_stats(db: Session) -> dict:
    invoices = [
        inv for inv in db.query(models.Invoice).all()
        if not getattr(inv, "archived", False)
    ]
    expenses = db.query(models.Expense).all()
    billed = sum(inv.total for inv in invoices)
    paid = sum(inv.total for inv in invoices if inv.status == "paid")
    outstanding = sum(inv.total for inv in invoices if inv.status in ("sent", "overdue", "draft"))
    spent = sum(e.amount for e in expenses)
    by_currency: dict = {}
    for inv in invoices:
        cur = inv.currency or "USD"
        slot = by_currency.setdefault(
            cur, {"billed": 0.0, "paid": 0.0, "outstanding": 0.0, "count": 0}
        )
        slot["billed"] = round(slot["billed"] + inv.total, 2)
        slot["count"] += 1
        if inv.status == "paid":
            slot["paid"] = round(slot["paid"] + inv.total, 2)
        if inv.status in ("sent", "overdue", "draft"):
            slot["outstanding"] = round(slot["outstanding"] + inv.total, 2)
    return {
        "clients": db.query(models.Client).filter(models.Client.archived.is_(False)).count(),
        "invoices": len(invoices),
        "proposals": db.query(models.Proposal).count(),
        "billed": round(billed, 2),
        "paid": round(paid, 2),
        "outstanding": round(outstanding, 2),
        "expenses": round(spent, 2),
        "net": round(paid - spent, 2),
        "by_currency": by_currency,
        "author": "Mourad.Soltani",
    }

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
    invoices = db.query(models.Invoice).all()
    expenses = db.query(models.Expense).all()
    billed = sum(inv.total for inv in invoices)
    paid = sum(inv.total for inv in invoices if inv.status == "paid")
    outstanding = sum(inv.total for inv in invoices if inv.status in ("sent", "overdue", "draft"))
    spent = sum(e.amount for e in expenses)
    return {
        "clients": db.query(models.Client).count(),
        "invoices": len(invoices),
        "proposals": db.query(models.Proposal).count(),
        "billed": round(billed, 2),
        "paid": round(paid, 2),
        "outstanding": round(outstanding, 2),
        "expenses": round(spent, 2),
        "net": round(paid - spent, 2),
        "author": "Mourad.Soltani",
    }

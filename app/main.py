"""ForgeLedger API — designed and signed by Mourad.Soltani."""

from datetime import date
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import models, schemas, services
from .database import get_db, init_db
from . import __version__, __author__
from .branding import get_brand
from .pdf_export import build_invoice_pdf
from .stripe_checkout import (
    create_checkout_session,
    stripe_configured,
    parse_webhook_event,
    invoice_id_from_event,
)
from .license import validate_license, active_license, issue_key
import os

ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="ForgeLedger",
    description="Freelance invoice, expense and proposal command center. Signature: Mourad.Soltani",
    version=__version__,
    contact={"name": "Mourad.Soltani"},
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health", response_model=schemas.HealthOut)
def health(db: Session = Depends(get_db)):
    try:
        db.query(models.Client).count()
        db_ok = True
    except Exception:
        db_ok = False
    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "product": "ForgeLedger",
        "author": __author__,
        "version": __version__,
        "checks": {
            "database": db_ok,
            "api": True,
            "pdf": True,
            "stripe": stripe_configured(),
        },
    }


@app.get("/api/brand")
def brand_config():
    return get_brand()


@app.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    return services.dashboard_stats(db)


@app.get("/api/clients", response_model=list[schemas.ClientOut])
def list_clients(db: Session = Depends(get_db)):
    return db.query(models.Client).order_by(models.Client.id.desc()).all()


@app.post("/api/clients", response_model=schemas.ClientOut, status_code=201)
def create_client(payload: schemas.ClientIn, db: Session = Depends(get_db)):
    row = models.Client(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.delete("/api/clients/{client_id}", status_code=204)
def delete_client(client_id: int, db: Session = Depends(get_db)):
    row = db.get(models.Client, client_id)
    if not row:
        raise HTTPException(404, "Client not found")
    db.delete(row)
    db.commit()


@app.get("/api/invoices", response_model=list[schemas.InvoiceOut])
def list_invoices(db: Session = Depends(get_db)):
    rows = db.query(models.Invoice).order_by(models.Invoice.id.desc()).all()
    return [
        schemas.InvoiceOut(
            id=r.id,
            number=r.number,
            client_id=r.client_id,
            issue_date=r.issue_date,
            due_date=r.due_date,
            status=r.status,
            currency=r.currency,
            notes=r.notes,
            total=r.total,
            items=r.items,
        )
        for r in rows
    ]


@app.post("/api/invoices", response_model=schemas.InvoiceOut, status_code=201)
def create_invoice(payload: schemas.InvoiceIn, db: Session = Depends(get_db)):
    client = db.get(models.Client, payload.client_id)
    if not client:
        raise HTTPException(400, "Unknown client")
    inv = models.Invoice(
        number=services.next_invoice_number(db),
        client_id=payload.client_id,
        issue_date=payload.issue_date or date.today(),
        due_date=payload.due_date,
        status=payload.status,
        currency=payload.currency,
        notes=payload.notes,
    )
    db.add(inv)
    db.flush()
    for item in payload.items:
        db.add(
            models.LineItem(
                invoice_id=inv.id,
                description=item.description,
                qty=item.qty,
                unit_price=item.unit_price,
            )
        )
    db.commit()
    db.refresh(inv)
    return schemas.InvoiceOut(
        id=inv.id,
        number=inv.number,
        client_id=inv.client_id,
        issue_date=inv.issue_date,
        due_date=inv.due_date,
        status=inv.status,
        currency=inv.currency,
        notes=inv.notes,
        total=inv.total,
        items=inv.items,
    )


@app.patch("/api/invoices/{invoice_id}/status")
def set_status(invoice_id: int, status: str, db: Session = Depends(get_db)):
    allowed = {"draft", "sent", "paid", "overdue"}
    if status not in allowed:
        raise HTTPException(400, "Invalid status")
    inv = db.get(models.Invoice, invoice_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    inv.status = status
    db.commit()
    return {"id": inv.id, "status": inv.status, "author": "Mourad.Soltani"}


@app.get("/api/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: int, db: Session = Depends(get_db)):
    inv = db.get(models.Invoice, invoice_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    client = db.get(models.Client, inv.client_id)
    if not client:
        raise HTTPException(400, "Client missing")
    pdf_bytes = build_invoice_pdf(inv, client, get_brand())
    filename = f"{inv.number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/invoices/{invoice_id}/checkout")
def invoice_checkout(invoice_id: int, db: Session = Depends(get_db)):
    inv = db.get(models.Invoice, invoice_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if inv.total <= 0:
        raise HTTPException(400, "Invoice total must be positive")
    client = db.get(models.Client, inv.client_id)
    amount_cents = int(round(inv.total * 100))
    base = os.environ.get("FORGELEDGER_PUBLIC_URL", "http://127.0.0.1:8080").rstrip("/")
    session = create_checkout_session(
        invoice_id=inv.id,
        invoice_number=inv.number,
        amount_cents=amount_cents,
        currency=inv.currency or "USD",
        customer_email=(client.email if client else None) or None,
        success_url=f"{base}/success?paid=1",
        cancel_url=f"{base}/success?canceled=1",
    )
    if session.get("mode") == "error":
        raise HTTPException(502, session.get("error") or "Checkout failed")
    return session


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    parsed = parse_webhook_event(payload, sig)
    if not parsed.get("ok"):
        raise HTTPException(400, parsed.get("error") or "Webhook rejected")
    inv_id = invoice_id_from_event(parsed.get("event"))
    if inv_id is None:
        return {"received": True, "action": "ignored", "author": "Mourad.Soltani"}
    inv = db.get(models.Invoice, inv_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    inv.status = "paid"
    db.commit()
    return {
        "received": True,
        "action": "marked_paid",
        "invoice_id": inv.id,
        "number": inv.number,
        "mode": parsed.get("mode"),
        "author": "Mourad.Soltani",
    }


@app.post("/api/license/validate")
def license_validate(payload: dict):
    key = (payload or {}).get("key") or ""
    result = validate_license(key)
    result["author"] = "Mourad.Soltani"
    return result


@app.get("/api/license/status")
def license_status():
    status = active_license()
    status["author"] = "Mourad.Soltani"
    return status


@app.post("/api/admin/license/issue")
def admin_issue_license(request: Request, payload: dict | None = None):
    """Issue a founder white-label key. Requires FORGELEDGER_ADMIN_TOKEN header X-Admin-Token."""
    expected = os.environ.get("FORGELEDGER_ADMIN_TOKEN", "").strip()
    if not expected:
        raise HTTPException(503, "Admin token not configured")
    got = request.headers.get("x-admin-token") or ""
    if got != expected:
        raise HTTPException(401, "Unauthorized")
    payload = payload or {}
    seed = payload.get("seed")
    tier = payload.get("tier") or "founder"
    return issue_key(seed=seed, tier=tier)


@app.get("/api/expenses", response_model=list[schemas.ExpenseOut])
def list_expenses(db: Session = Depends(get_db)):
    return db.query(models.Expense).order_by(models.Expense.id.desc()).all()


@app.post("/api/expenses", response_model=schemas.ExpenseOut, status_code=201)
def create_expense(payload: schemas.ExpenseIn, db: Session = Depends(get_db)):
    data = payload.model_dump()
    if not data.get("incurred_on"):
        data["incurred_on"] = date.today()
    row = models.Expense(**data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.get("/api/proposals", response_model=list[schemas.ProposalOut])
def list_proposals(db: Session = Depends(get_db)):
    return db.query(models.Proposal).order_by(models.Proposal.id.desc()).all()


@app.post("/api/proposals", response_model=schemas.ProposalOut, status_code=201)
def create_proposal(payload: schemas.ProposalIn, db: Session = Depends(get_db)):
    body = services.generate_proposal_body(payload)
    row = models.Proposal(**payload.model_dump(), body=body)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.get("/", response_class=HTMLResponse)
def home():
    return FileResponse(ROOT / "templates" / "index.html")


@app.get("/success", response_class=HTMLResponse)
def payment_success():
    return FileResponse(ROOT / "templates" / "success.html")


app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "author": "Mourad.Soltani"},
    )

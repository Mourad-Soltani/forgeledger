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
    create_billing_portal_session,
    webhook_status,
    create_founding_license_checkout,
)
from .license import validate_license, active_license, issue_key
from .email_invoice import build_invoice_email, send_invoice_email, smtp_configured, SUPPORTED
from .jobs import run_recurring, run_reminders
from .auth import (
    get_current_principal,
    require_role,
    auth_required,
    bootstrap_owner_key,
    create_api_key,
)
import csv
import io
from .portal import mint_portal_token, verify_portal_token
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
    from .database import SessionLocal
    db = SessionLocal()
    try:
        created = bootstrap_owner_key(db)
        if created:
            print(f"[ForgeLedger] Owner API key created (save it): {created}")
    finally:
        db.close()


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
            "smtp": smtp_configured(),
            "auth_required": auth_required(),
        },
    }


@app.get("/api/brand")
def brand_config():
    return get_brand()


@app.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    return services.dashboard_stats(db)


@app.get("/api/clients", response_model=list[schemas.ClientOut])
def list_clients(include_archived: bool = False, db: Session = Depends(get_db)):
    q = db.query(models.Client)
    if not include_archived:
        q = q.filter(models.Client.archived.is_(False))
    return q.order_by(models.Client.id.desc()).all()


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


@app.post("/api/clients/{client_id}/archive")
def archive_client(client_id: int, db: Session = Depends(get_db)):
    row = db.get(models.Client, client_id)
    if not row:
        raise HTTPException(404, "Client not found")
    row.archived = True
    db.commit()
    return {"id": client_id, "archived": True, "author": "Mourad.Soltani"}


@app.post("/api/invoices/{invoice_id}/archive")
def archive_invoice(invoice_id: int, db: Session = Depends(get_db)):
    row = db.get(models.Invoice, invoice_id)
    if not row:
        raise HTTPException(404, "Invoice not found")
    row.archived = True
    db.commit()
    return {"id": invoice_id, "archived": True, "author": "Mourad.Soltani"}


@app.get("/api/invoices", response_model=list[schemas.InvoiceOut])
def list_invoices(include_archived: bool = False, db: Session = Depends(get_db)):
    q = db.query(models.Invoice)
    if not include_archived:
        q = q.filter(models.Invoice.archived.is_(False))
    rows = q.order_by(models.Invoice.id.desc()).all()
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
            archived=bool(getattr(r, "archived", False)),
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
        archived=bool(getattr(inv, "archived", False)),
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


@app.post("/api/invoices/{invoice_id}/email")
def email_invoice(invoice_id: int, db: Session = Depends(get_db)):
    inv = db.get(models.Invoice, invoice_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    client = db.get(models.Client, inv.client_id)
    if not client:
        raise HTTPException(400, "Client missing")
    base = os.environ.get("FORGELEDGER_PUBLIC_URL", "http://127.0.0.1:8080").rstrip("/")
    msg = build_invoice_email(invoice=inv, client=client, brand=get_brand(), public_url=base)
    pdf_bytes = build_invoice_pdf(inv, client, get_brand())
    result = send_invoice_email(msg, pdf_bytes=pdf_bytes)
    if result.get("mode") == "error" and not result.get("sent"):
        if result.get("error") == "Client has no email address":
            raise HTTPException(400, result["error"])
    if inv.status == "draft":
        inv.status = "sent"
        db.commit()
    result["invoice_id"] = inv.id
    result["status"] = inv.status
    return result


@app.get("/api/currencies")
def list_currencies():
    return {"currencies": list(SUPPORTED), "author": "Mourad.Soltani"}


@app.get("/api/stripe/status")
def stripe_status(principal=Depends(get_current_principal)):
    st = webhook_status()
    st["configured"] = stripe_configured()
    return st


@app.post("/api/stripe/billing-portal")
def stripe_billing_portal(payload: dict, principal=Depends(require_role("owner", "member"))):
    customer_id = (payload or {}).get("customer_id") or ""
    if not customer_id:
        raise HTTPException(400, "customer_id required")
    base = os.environ.get("FORGELEDGER_PUBLIC_URL", "http://127.0.0.1:8080").rstrip("/")
    session = create_billing_portal_session(customer_id=customer_id, return_url=f"{base}/")
    if session.get("mode") == "error":
        raise HTTPException(502, session.get("error") or "Portal failed")
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



@app.post("/api/clients/{client_id}/portal-link")
def create_portal_link(client_id: int, db: Session = Depends(get_db)):
    client = db.get(models.Client, client_id)
    if not client:
        raise HTTPException(404, "Client not found")
    token = mint_portal_token(client_id)
    base = os.environ.get("FORGELEDGER_PUBLIC_URL", "http://127.0.0.1:8080").rstrip("/")
    return {
        "client_id": client_id,
        "token": token,
        "url": f"{base}/portal/{token}",
        "author": "Mourad.Soltani",
    }


@app.get("/api/portal/{token}")
def portal_data(token: str, db: Session = Depends(get_db)):
    client_id = verify_portal_token(token)
    if client_id is None:
        raise HTTPException(401, "Invalid or expired portal link")
    client = db.get(models.Client, client_id)
    if not client:
        raise HTTPException(404, "Client not found")
    invs = (
        db.query(models.Invoice)
        .filter(models.Invoice.client_id == client_id)
        .filter(models.Invoice.archived.is_(False))
        .order_by(models.Invoice.id.desc())
        .all()
    )
    return {
        "client": {"id": client.id, "name": client.name, "company": client.company, "email": client.email},
        "invoices": [
            {
                "id": i.id,
                "number": i.number,
                "status": i.status,
                "currency": i.currency,
                "total": i.total,
                "issue_date": str(i.issue_date) if i.issue_date else None,
                "pdf": f"/api/invoices/{i.id}/pdf",
                "payable": i.status != "paid" and i.total > 0,
            }
            for i in invs
        ],
        "brand": get_brand(),
        "author": "Mourad.Soltani",
    }


@app.post("/api/portal/{token}/invoices/{invoice_id}/checkout")
def portal_checkout(token: str, invoice_id: int, db: Session = Depends(get_db)):
    client_id = verify_portal_token(token)
    if client_id is None:
        raise HTTPException(401, "Invalid or expired portal link")
    inv = db.get(models.Invoice, invoice_id)
    if not inv or inv.client_id != client_id or getattr(inv, "archived", False):
        raise HTTPException(404, "Invoice not found")
    if inv.total <= 0:
        raise HTTPException(400, "Invoice total must be positive")
    if inv.status == "paid":
        raise HTTPException(400, "Already paid")
    client = db.get(models.Client, client_id)
    amount_cents = int(round(inv.total * 100))
    base = os.environ.get("FORGELEDGER_PUBLIC_URL", "http://127.0.0.1:8080").rstrip("/")
    session = create_checkout_session(
        invoice_id=inv.id,
        invoice_number=inv.number,
        amount_cents=amount_cents,
        currency=inv.currency or "USD",
        customer_email=(client.email if client else None) or None,
        success_url=f"{base}/success?paid=1",
        cancel_url=f"{base}/portal/{token}",
    )
    if session.get("mode") == "error":
        raise HTTPException(502, session.get("error") or "Checkout failed")
    if session.get("mode") == "demo":
        inv.status = "paid"
        db.commit()
        session["marked_paid"] = True
    return session


@app.get("/portal/{token}", response_class=HTMLResponse)
def portal_page(token: str):
    return FileResponse(ROOT / "templates" / "portal.html")


@app.get("/api/recurring", response_model=list[schemas.RecurringOut])
def list_recurring(db: Session = Depends(get_db)):
    return db.query(models.RecurringInvoice).order_by(models.RecurringInvoice.id.desc()).all()


@app.post("/api/recurring", response_model=schemas.RecurringOut, status_code=201)
def create_recurring(payload: schemas.RecurringIn, db: Session = Depends(get_db)):
    client = db.get(models.Client, payload.client_id)
    if not client:
        raise HTTPException(400, "Unknown client")
    data = payload.model_dump()
    if not data.get("next_run"):
        data["next_run"] = date.today()
    row = models.RecurringInvoice(**data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.post("/api/recurring/{rid}/toggle")
def toggle_recurring(rid: int, db: Session = Depends(get_db)):
    row = db.get(models.RecurringInvoice, rid)
    if not row:
        raise HTTPException(404, "Not found")
    row.active = not bool(row.active)
    db.commit()
    return {"id": rid, "active": row.active, "author": "Mourad.Soltani"}


@app.post("/api/jobs/run-recurring")
def job_recurring(db: Session = Depends(get_db)):
    return run_recurring(db)


@app.post("/api/jobs/run-reminders")
def job_reminders(db: Session = Depends(get_db)):
    return run_reminders(db)


@app.get("/api/export/invoices.csv")
def export_invoices_csv(include_archived: bool = False, db: Session = Depends(get_db)):
    q = db.query(models.Invoice)
    if not include_archived:
        q = q.filter(models.Invoice.archived.is_(False))
    rows = q.order_by(models.Invoice.id.asc()).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "number", "client_id", "status", "currency", "total", "issue_date", "due_date", "archived"])
    for r in rows:
        w.writerow([
            r.id, r.number, r.client_id, r.status, r.currency, r.total,
            r.issue_date, r.due_date, int(bool(getattr(r, "archived", False))),
        ])
    data = buf.getvalue()
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="forgeledger-invoices.csv"'},
    )


@app.get("/api/export/clients.csv")
def export_clients_csv(include_archived: bool = False, db: Session = Depends(get_db)):
    q = db.query(models.Client)
    if not include_archived:
        q = q.filter(models.Client.archived.is_(False))
    rows = q.order_by(models.Client.id.asc()).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "name", "email", "company", "archived"])
    for r in rows:
        w.writerow([r.id, r.name, r.email, r.company, int(bool(getattr(r, "archived", False)))])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="forgeledger-clients.csv"'},
    )


@app.get("/api/keys")
def list_keys(db: Session = Depends(get_db), principal=Depends(require_role("owner"))):
    rows = db.query(models.ApiKey).order_by(models.ApiKey.id.desc()).all()
    return [
        {"id": r.id, "name": r.name, "role": r.role, "active": r.active, "created_at": r.created_at}
        for r in rows
    ]


@app.post("/api/keys", status_code=201)
def issue_api_key(payload: dict, db: Session = Depends(get_db), principal=Depends(require_role("owner"))):
    name = (payload or {}).get("name") or "member"
    role = (payload or {}).get("role") or "member"
    if role == "owner" and principal.get("role") != "owner":
        raise HTTPException(403, "Only owner can mint owner keys")
    return create_api_key(db, name=name, role=role)


@app.post("/api/keys/{kid}/revoke")
def revoke_key(kid: int, db: Session = Depends(get_db), principal=Depends(require_role("owner"))):
    row = db.get(models.ApiKey, kid)
    if not row:
        raise HTTPException(404, "Key not found")
    if row.role == "owner":
        owners = db.query(models.ApiKey).filter(models.ApiKey.role == "owner", models.ApiKey.active.is_(True)).count()
        if owners <= 1:
            raise HTTPException(400, "Cannot revoke the last owner key")
    row.active = False
    db.commit()
    return {"id": kid, "active": False, "author": "Mourad.Soltani"}


@app.get("/api/me")
def me(principal=Depends(get_current_principal)):
    principal = dict(principal)
    principal["author"] = "Mourad.Soltani"
    return principal


@app.get("/", response_class=HTMLResponse)
def home():
    return FileResponse(ROOT / "templates" / "index.html")


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return FileResponse(ROOT / "templates" / "login.html")


@app.get("/onboarding", response_class=HTMLResponse)
def onboarding_page():
    return FileResponse(ROOT / "templates" / "onboarding.html")


@app.post("/api/commerce/founding-license")
def buy_founding_license(payload: dict | None = None):
    email = (payload or {}).get("email")
    base = os.environ.get("FORGELEDGER_PUBLIC_URL", "http://127.0.0.1:8080").rstrip("/")
    session = create_founding_license_checkout(
        email=email,
        success_url=f"{base}/onboarding?licensed=1",
        cancel_url=f"{base}/onboarding?canceled=1",
    )
    if session.get("mode") == "error":
        raise HTTPException(502, session.get("error") or "Checkout failed")
    return session


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

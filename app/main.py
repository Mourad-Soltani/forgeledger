"""ForgeLedger API — designed and signed by Mourad.Soltani."""

from datetime import date
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import models, schemas, services
from .database import get_db, init_db, engine
from . import __version__, __author__

ROOT = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(ROOT / "templates"))

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
        "checks": {"database": db_ok, "api": True},
    }


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


app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "author": "Mourad.Soltani"},
    )

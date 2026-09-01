"""Health and API tests — Mourad.Soltani."""

import os
import tempfile
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    dbfile = tmp_path / "test.db"
    monkeypatch.setenv("FORGELEDGER_DB", str(dbfile))
    # re-import with isolated db
    from importlib import reload
    import app.database as database
    reload(database)
    import app.main as main
    reload(main)
    database.init_db()
    with TestClient(main.app) as c:
        yield c


def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["author"] == "Mourad.Soltani"
    assert body["checks"]["database"] is True
    assert body["checks"]["api"] is True


def test_client_invoice_expense_proposal_flow(client):
    c = client.post("/api/clients", json={"name": "Acme Labs", "email": "ops@acme.test"}).json()
    assert c["name"] == "Acme Labs"
    inv = client.post(
        "/api/invoices",
        json={
            "client_id": c["id"],
            "status": "sent",
            "items": [{"description": "Sprint 1", "qty": 2, "unit_price": 1500}],
        },
    ).json()
    assert inv["total"] == 3000
    assert inv["number"].startswith("FL-")
    paid = client.patch(f"/api/invoices/{inv['id']}/status?status=paid").json()
    assert paid["status"] == "paid"
    exp = client.post("/api/expenses", json={"description": "Figma", "amount": 15, "category": "software"}).json()
    assert exp["amount"] == 15
    prop = client.post(
        "/api/proposals",
        json={"title": "Rebuild billing", "client_name": "Acme Labs", "investment": 12000},
    ).json()
    assert "Mourad.Soltani" in prop["body"]
    stats = client.get("/api/stats").json()
    assert stats["clients"] == 1
    assert stats["paid"] == 3000
    assert stats["author"] == "Mourad.Soltani"


def test_home_renders(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "ForgeLedger" in res.text
    assert "Mourad.Soltani" in res.text


def test_pdf_and_checkout(client):
    c = client.post("/api/clients", json={"name": "PDF Co", "email": "bill@pdf.test"}).json()
    inv = client.post(
        "/api/invoices",
        json={
            "client_id": c["id"],
            "status": "sent",
            "items": [{"description": "Design sprint", "qty": 1, "unit_price": 2500}],
        },
    ).json()
    pdf = client.get(f"/api/invoices/{inv['id']}/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content[:4] == b"%PDF"
    checkout = client.post(f"/api/invoices/{inv['id']}/checkout").json()
    assert checkout["mode"] == "demo"
    assert checkout["url"]
    assert checkout["author"] == "Mourad.Soltani"
    brand = client.get("/api/brand").json()
    assert brand["author"] == "Mourad.Soltani"
    assert "ForgeLedger" in brand["footer"]

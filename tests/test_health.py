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
            "items": [{"description": "Design sprint", "qty": 1, "unit_price": 2500},
                {"description": "Copy deck", "qty": 2, "unit_price": 400}],
        },
    ).json()
    assert inv["total"] == 3300
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


def test_webhook_marks_paid(client):
    c = client.post("/api/clients", json={"name": "Pay Co"}).json()
    inv = client.post(
        "/api/invoices",
        json={
            "client_id": c["id"],
            "status": "sent",
            "items": [{"description": "Retainer", "qty": 1, "unit_price": 900}],
        },
    ).json()
    body = {
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"invoice_id": str(inv["id"])}}},
    }
    res = client.post("/api/stripe/webhook", json=body)
    assert res.status_code == 200
    data = res.json()
    assert data["action"] == "marked_paid"
    assert data["author"] == "Mourad.Soltani"
    listed = client.get("/api/invoices").json()
    match = next(x for x in listed if x["id"] == inv["id"])
    assert match["status"] == "paid"


def test_license_validate(client):
    bad = client.post("/api/license/validate", json={"key": "nope"}).json()
    assert bad["valid"] is False
    assert bad["author"] == "Mourad.Soltani"
    status = client.get("/api/license/status").json()
    assert "tier" in status



def test_success_page(client):
    res = client.get("/success?paid=1")
    assert res.status_code == 200
    assert "Payment" in res.text or "ForgeLedger" in res.text
    assert "Mourad.Soltani" in res.text


def test_admin_issue_license(client, monkeypatch):
    monkeypatch.setenv("FORGELEDGER_ADMIN_TOKEN", "test-admin-token")
    # clear cached license
    from importlib import reload
    import app.license as lic
    reload(lic)
    denied = client.post("/api/admin/license/issue", json={"seed": "DEMO0001"})
    assert denied.status_code == 401
    ok = client.post(
        "/api/admin/license/issue",
        json={"seed": "DEMO0001"},
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["valid"] is True
    assert body["key"].startswith("FL-")
    assert body["author"] == "Mourad.Soltani"
    # issued key validates
    check = client.post("/api/license/validate", json={"key": body["key"]}).json()
    assert check["valid"] is True



def test_email_invoice_demo(client):
    c = client.post(
        "/api/clients",
        json={"name": "Mail Co", "email": "finance@mail.test"},
    ).json()
    inv = client.post(
        "/api/invoices",
        json={
            "client_id": c["id"],
            "status": "draft",
            "currency": "EUR",
            "items": [{"description": "EU sprint", "qty": 1, "unit_price": 1200}],
        },
    ).json()
    assert inv["currency"] == "EUR"
    assert inv["total"] == 1200
    res = client.post(f"/api/invoices/{inv['id']}/email").json()
    assert res["mode"] == "demo"
    assert res["preview"]["to"] == "finance@mail.test"
    assert "FL-" in res["preview"]["subject"] or "Invoice" in res["preview"]["subject"]
    assert res["author"] == "Mourad.Soltani"
    listed = client.get("/api/invoices").json()
    match = next(x for x in listed if x["id"] == inv["id"])
    assert match["status"] == "sent"
    cur = client.get("/api/currencies").json()
    assert "EUR" in cur["currencies"]



def test_portal_and_currency_stats(client):
    c = client.post(
        "/api/clients",
        json={"name": "Portal Co", "email": "c@portal.test"},
    ).json()
    client.post(
        "/api/invoices",
        json={
            "client_id": c["id"],
            "status": "sent",
            "currency": "GBP",
            "items": [{"description": "UK work", "qty": 1, "unit_price": 500}],
        },
    )
    stats = client.get("/api/stats").json()
    assert "by_currency" in stats
    assert "GBP" in stats["by_currency"]
    assert stats["by_currency"]["GBP"]["billed"] == 500
    link = client.post(f"/api/clients/{c['id']}/portal-link").json()
    assert link["url"].endswith(link["token"])
    assert link["author"] == "Mourad.Soltani"
    portal = client.get(f"/api/portal/{link['token']}").json()
    assert portal["client"]["name"] == "Portal Co"
    assert len(portal["invoices"]) == 1
    page = client.get(f"/portal/{link['token']}")
    assert page.status_code == 200
    assert "portal" in page.text.lower() or "ForgeLedger" in page.text
    mail = client.post(
        f"/api/invoices/{portal['invoices'][0]['id']}/email"
    ).json()
    assert mail.get("pdf_attached") is True or mail.get("pdf_bytes", 0) > 0



def test_archive_and_portal_pay(client):
    c = client.post("/api/clients", json={"name": "Archive Co", "email": "a@x.test"}).json()
    inv = client.post(
        "/api/invoices",
        json={
            "client_id": c["id"],
            "status": "sent",
            "currency": "USD",
            "items": [{"description": "Work", "qty": 1, "unit_price": 100}],
        },
    ).json()
    link = client.post(f"/api/clients/{c['id']}/portal-link").json()
    assert "/portal/" in link["url"]
    token = link["token"]
    portal = client.get(f"/api/portal/{token}").json()
    assert portal["client"]["name"] == "Archive Co"
    assert portal["invoices"][0]["payable"] is True
    pay = client.post(f"/api/portal/{token}/invoices/{inv['id']}/checkout").json()
    assert pay["mode"] == "demo"
    assert pay.get("marked_paid") is True
    listed = client.get("/api/invoices").json()
    assert next(x for x in listed if x["id"] == inv["id"])["status"] == "paid"
    ar = client.post(f"/api/invoices/{inv['id']}/archive").json()
    assert ar["archived"] is True
    listed2 = client.get("/api/invoices").json()
    assert all(x["id"] != inv["id"] for x in listed2)
    client.post(f"/api/clients/{c['id']}/archive")
    clients = client.get("/api/clients").json()
    assert all(x["id"] != c["id"] for x in clients)



def test_recurring_reminders_csv(client):
    c = client.post("/api/clients", json={"name": "Retainer Co", "email": "r@x.test"}).json()
    rec = client.post(
        "/api/recurring",
        json={
            "client_id": c["id"],
            "description": "Monthly",
            "amount": 2500,
            "currency": "USD",
            "cadence": "monthly",
            "next_run": "2020-01-01",
        },
    ).json()
    assert rec["amount"] == 2500
    ran = client.post("/api/jobs/run-recurring").json()
    assert ran["count"] >= 1
    invs = client.get("/api/invoices").json()
    assert any(i["client_id"] == c["id"] for i in invs)
    # force due soon
    inv = next(i for i in invs if i["client_id"] == c["id"])
    # reminders demo
    rem = client.post("/api/jobs/run-reminders").json()
    assert rem["author"] == "Mourad.Soltani"
    csv_inv = client.get("/api/export/invoices.csv")
    assert csv_inv.status_code == 200
    assert "text/csv" in csv_inv.headers["content-type"]
    assert "number" in csv_inv.text
    csv_cli = client.get("/api/export/clients.csv")
    assert "Retainer Co" in csv_cli.text



def test_api_keys_auth(client, monkeypatch):
    # open mode
    me = client.get("/api/me").json()
    assert me["role"] == "owner"
    assert me["auth"] is False
    # enable auth
    monkeypatch.setenv("FORGELEDGER_REQUIRE_AUTH", "1")
    monkeypatch.setenv("FORGELEDGER_OWNER_API_KEY", "fl_owner_testkey_1234567890")
    from importlib import reload
    import app.auth as auth
    import app.database as database
    import app.main as main
    reload(auth)
    reload(database)
    database.init_db()
    db = database.SessionLocal()
    try:
        auth.bootstrap_owner_key(db)
    finally:
        db.close()
    reload(main)
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c2:
        denied = c2.get("/api/me")
        assert denied.status_code == 401
        ok = c2.get("/api/me", headers={"X-API-Key": "fl_owner_testkey_1234567890"})
        assert ok.status_code == 200
        assert ok.json()["role"] == "owner"
        issued = c2.post(
            "/api/keys",
            headers={"X-API-Key": "fl_owner_testkey_1234567890"},
            json={"name": "ops", "role": "member"},
        )
        assert issued.status_code == 201
        body = issued.json()
        assert body["key"].startswith("fl_member_")
        assert body["author"] == "Mourad.Soltani"

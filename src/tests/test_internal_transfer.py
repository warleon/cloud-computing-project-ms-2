# ============================================================
# test_internal_transfer.py — Pruebas de integración del endpoint /internal/transfer
# ============================================================

from __future__ import annotations
import uuid
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from src import models
from .conftest import create_account  # ✅ usamos el helper centralizado

HEADERS = {"x-service-key": "test-ms3-key"}


# ============================================================
# Escenario 1: Transferencia exitosa e idempotente
# ============================================================
def test_transfer_success_idempotent(client: TestClient, db: Session):
    a = create_account(db, balance=1000.0, currency="PEN")
    b = create_account(db, balance=500.0, currency="PEN")

    req_id = str(uuid.uuid4())
    payload = {
        "requestId": req_id,
        "fromAccount": str(a.id),
        "toAccount": str(b.id),
        "amount": 150.0,
        "currency": "PEN",
    }

    # Primera ejecución
    r1 = client.post("/internal/transfer", json=payload, headers=HEADERS)
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["status"] == "OK"
    assert round(body1["balances"]["from"], 2) == 1000.0 - 150.0
    assert round(body1["balances"]["to"], 2) == 500.0 + 150.0
    assert body1["debitEntryId"] and body1["creditEntryId"]

    # Segunda ejecución (idempotente)
    r2 = client.post("/internal/transfer", json=payload, headers=HEADERS)
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["status"] == "OK"
    assert body2["balances"]["from"] == body1["balances"]["from"]
    assert body2["balances"]["to"] == body1["balances"]["to"]

    # Verifica que existan exactamente dos movimientos (DEBIT/CREDIT)
    tx_id = uuid.UUID(req_id)
    debits = db.query(models.LedgerEntry).filter(
        models.LedgerEntry.tx_id == tx_id,
        models.LedgerEntry.direction == "DEBIT"
    ).all()
    credits = db.query(models.LedgerEntry).filter(
        models.LedgerEntry.tx_id == tx_id,
        models.LedgerEntry.direction == "CREDIT"
    ).all()
    assert len(debits) == 1
    assert len(credits) == 1


# ============================================================
# Escenario 2: Fondos insuficientes
# ============================================================
def test_insufficient_funds(client: TestClient, db: Session):
    a = create_account(db, balance=50.0, currency="PEN")
    b = create_account(db, balance=0.0, currency="PEN")

    payload = {
        "requestId": str(uuid.uuid4()),
        "fromAccount": str(a.id),
        "toAccount": str(b.id),
        "amount": 100.0,
        "currency": "PEN",
    }

    r = client.post("/internal/transfer", json=payload, headers=HEADERS)
    assert r.status_code == 400
    assert "insufficient" in r.json()["detail"].lower()


# ============================================================
# Escenario 3: Diferencia de moneda entre cuentas
# ============================================================
def test_currency_mismatch(client: TestClient, db: Session):
    a = create_account(db, balance=1000.0, currency="USD")
    b = create_account(db, balance=1000.0, currency="PEN")

    payload = {
        "requestId": str(uuid.uuid4()),
        "fromAccount": str(a.id),
        "toAccount": str(b.id),
        "amount": 10.0,
        "currency": "USD",
    }

    r = client.post("/internal/transfer", json=payload, headers=HEADERS)
    assert r.status_code == 422
    assert "currency mismatch" in r.json()["detail"].lower()


# ============================================================
# Escenario 4: Servicio no autorizado (clave errónea)
# ============================================================
def test_unauthorized_service_key(client: TestClient, db: Session):
    a = create_account(db, balance=100.0, currency="PEN")
    b = create_account(db, balance=100.0, currency="PEN")

    payload = {
        "requestId": str(uuid.uuid4()),
        "fromAccount": str(a.id),
        "toAccount": str(b.id),
        "amount": 10.0,
        "currency": "PEN",
    }

    r = client.post("/internal/transfer", json=payload, headers={"x-service-key": "wrong"})
    assert r.status_code == 403

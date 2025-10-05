# src/tests/test_notify_ms3.py
from __future__ import annotations

import uuid
import time
from typing import Any, Dict, List

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from .conftest import create_account  # helper definido en tu conftest


class _RecordedRequest(Dict[str, Any]):
    """Estructura simple para registrar requests salientes."""


def _install_httpx_async_mock(monkeypatch, bucket: List[_RecordedRequest], ok_status: int = 200):
    """
    Reemplaza httpx.AsyncClient por un cliente falso que captura los POSTs
    y devuelve siempre una respuesta con status 2xx (configurable).
    """

    class _FakeResponse:
        def __init__(self, status_code: int = ok_status, text: str = ""):
            self.status_code = status_code
            self.text = text

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            # kwargs incluyen 'timeout', etc.; no los necesitamos.
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, *, json: Any = None, headers: Dict[str, str] | None = None):
            bucket.append(
                _RecordedRequest(
                    url=url,
                    json=json,
                    headers=headers or {},
                )
            )
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)


def test_notifies_ms3_twice_on_successful_transfer(
    client: TestClient, db: Session, monkeypatch
):
    """
    Verifica que, tras una transferencia exitosa, MS2 notifica 2 eventos a MS3:
    - Uno con el nuevo balance de la cuenta origen
    - Otro con el nuevo balance de la cuenta destino
    """

    # --- Configuración del entorno de notificaciones ---
    ms3_url = "http://ms3.test/api/v1/balance-updates"
    ms3_key = "k123"
    monkeypatch.setenv("MS3_NOTIFY_ENABLED", "true")
    monkeypatch.setenv("MS3_NOTIFY_URL", ms3_url)
    monkeypatch.setenv("MS3_NOTIFY_KEY", ms3_key)

    # SERVICE_KEY_FOR_MS3 ya se setea en conftest; si quieres forzar:
    monkeypatch.setenv("SERVICE_KEY_FOR_MS3", "test-ms3-key")

    # Bucket para registrar los POST que "salgan" a MS3
    recorded: List[_RecordedRequest] = []
    _install_httpx_async_mock(monkeypatch, recorded, ok_status=200)

    # --- Datos de prueba ---
    a = create_account(db, balance=1000.0, currency="PEN")  # origen
    b = create_account(db, balance=500.0, currency="PEN")   # destino

    amount = 150.0
    expected_from = 1000.0 - amount
    expected_to = 500.0 + amount

    payload = {
        "requestId": str(uuid.uuid4()),
        "fromAccount": str(a.id),
        "toAccount": str(b.id),
        "amount": amount,
        "currency": "PEN",
    }

    # Ejecutar transferencia
    r = client.post("/internal/transfer", json=payload, headers={"x-service-key": "test-ms3-key"})
    assert r.status_code == 200, r.text

    # Darle un respiro al event loop para que se ejecuten las tareas asíncronas
    time.sleep(0.05)

    # --- Aserciones de notificación ---
    # Deben haberse enviado exactamente 2 POSTs
    assert len(recorded) == 2, f"Se esperaban 2 notificaciones, se capturaron {len(recorded)}: {recorded}"

    # Todas a la misma URL configurada
    assert all(req["url"] == ms3_url for req in recorded)

    # Headers correctos (Content-Type + x-service-key)
    for req in recorded:
        headers = req["headers"]
        assert headers.get("Content-Type") == "application/json"
        assert headers.get("x-service-key") == ms3_key

    # Payload correcto y con saldos esperados
    # Armamos un mapa accountId -> balance notificado
    notified = {req["json"]["data"]["accountId"]: req["json"]["data"]["balance"]["value"] for req in recorded}

    assert str(a.id) in notified
    assert str(b.id) in notified
    assert notified[str(a.id)] == expected_from
    assert notified[str(b.id)] == expected_to

    # Tipo de evento correcto
    for req in recorded:
        assert req["json"]["type"] == "account.balance.updated"
        assert req["json"]["data"]["balance"]["currency"] == "PEN"

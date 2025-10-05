# ============================================================
# conftest.py  —  Configuración global de pruebas para MS2
# ============================================================

from __future__ import annotations
from collections.abc import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

# Importar la app, base y modelos
from src.main import app
from src.database import SessionLocal, engine, Base
from src import models


# ------------------------------------------------------------
# 1️⃣  Crear el esquema una sola vez por sesión de pruebas
# ------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def ensure_schema() -> Generator[None, None, None]:
    """
    Crea todas las tablas del modelo antes de ejecutar los tests.
    Se ejecuta automáticamente una sola vez por sesión de pytest.
    """
    Base.metadata.create_all(bind=engine)
    yield
    # Si deseas limpiar completamente al final:
    # Base.metadata.drop_all(bind=engine)


# ------------------------------------------------------------
# 2️⃣  Limpiar la base antes de cada test
# ------------------------------------------------------------
@pytest.fixture(autouse=True)
def clean_db() -> Generator[None, None, None]:
    """
    Limpia las tablas principales antes de cada test para evitar
    datos residuales entre ejecuciones.
    """
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM ledger_entries;"))
        conn.execute(text("DELETE FROM accounts;"))
    yield


# ------------------------------------------------------------
# 3️⃣  Sesión de base de datos (Session) para usar en tests
# ------------------------------------------------------------
@pytest.fixture
def db() -> Generator[Session, None, None]:
    """
    Crea una sesión transaccional para cada test y la cierra al final.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ------------------------------------------------------------
# 4️⃣  Cliente HTTP de pruebas (FastAPI TestClient)
# ------------------------------------------------------------
@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """
    Devuelve un cliente de pruebas para realizar solicitudes HTTP
    contra la aplicación FastAPI sin levantar un servidor real.
    """
    client = TestClient(app)
    yield client


# ------------------------------------------------------------
# 5️⃣  Helper para crear cuentas directamente en la BD
# ------------------------------------------------------------
def create_account(
    db: Session,
    *,
    customer_id: str | None = None,
    balance: float = 0.0,
    currency: str = "PEN",
    type_: str = "SAVINGS",
    status: str = "ACTIVE"
) -> models.Account:
    """
    Inserta una cuenta de prueba directamente en la base de datos.

    Args:
        db: sesión de SQLAlchemy activa
        customer_id: UUID o string identificador de cliente (si no se pasa, se genera uno nuevo)
        balance: saldo inicial
        currency: código ISO 4217, ej. 'PEN', 'USD'
        type_: tipo de cuenta ('SAVINGS', 'CHECKING', etc.)
        status: estado ('ACTIVE', 'BLOCKED', 'CLOSED')

    Returns:
        models.Account persistida y refrescada
    """
    import uuid

    if not customer_id:
        customer_id = str(uuid.uuid4())

    account = models.Account(
        customer_id=customer_id,
        type=type_.upper(),
        status=status.upper(),
        currency=currency.upper(),
        balance=balance,
        opened_at=datetime.utcnow(),
    )

    db.add(account)
    db.commit()
    db.refresh(account)
    return account

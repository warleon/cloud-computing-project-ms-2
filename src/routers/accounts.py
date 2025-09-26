from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime

from .. import models, schemas, database

router = APIRouter()

# ============================================================
# Crear cuenta
# ============================================================
@router.post("/", response_model=schemas.AccountOut, status_code=201)
def create_account(payload: schemas.AccountCreate, db: Session = Depends(database.get_db)):
    """
    Crea una nueva cuenta bancaria asociada a un cliente.
    - customer_id debe provenir de MS1 (Customers).
    - Inicialmente la cuenta se crea con balance = 0 y estado = ACTIVE.
    """
    account = models.Account(
        customer_id=payload.customer_id,
        type=payload.type,
        status="ACTIVE",
        currency=payload.currency,
        balance=0,
        opened_at=datetime.utcnow()
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


# ============================================================
# Listar cuentas (paginado y filtrado)
# ============================================================
@router.get("/", response_model=list[schemas.AccountOut])
def list_accounts(
    db: Session = Depends(database.get_db),
    skip: int = Query(0, ge=0, description="Número de registros a omitir (offset)"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de cuentas a retornar"),
    status: str | None = Query(None, description="Filtrar por estado: ACTIVE | BLOCKED | CLOSED"),
    type: str | None = Query(None, description="Filtrar por tipo: SAVINGS | CHECKING | BUSINESS"),
):
    """
    Lista cuentas bancarias con soporte de **paginación** y **filtros opcionales**.
    - Se recomienda para el pipeline de ingesta (Athena).
    """
    query = db.query(models.Account)

    if status:
        query = query.filter(models.Account.status == status.upper())
    if type:
        query = query.filter(models.Account.type == type.upper())

    accounts = query.offset(skip).limit(limit).all()
    return accounts


# ============================================================
# Obtener cuenta por ID
# ============================================================
@router.get("/{account_id}", response_model=schemas.AccountOut)
def get_account(account_id: UUID, db: Session = Depends(database.get_db)):
    """
    Obtiene el detalle de una cuenta bancaria por su ID.
    """
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


# ============================================================
# Actualizar estado de una cuenta
# ============================================================
@router.put("/{account_id}/status", response_model=schemas.AccountOut)
def update_account_status(account_id: UUID, payload: schemas.AccountUpdateStatus, db: Session = Depends(database.get_db)):
    """
    Cambia el estado de una cuenta bancaria.
    - Estados permitidos: ACTIVE, BLOCKED, CLOSED.
    """
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.status = payload.status.upper()
    if account.status == "CLOSED":
        account.closed_at = datetime.utcnow()

    db.commit()
    db.refresh(account)
    return account


# ============================================================
# Consultar balance de una cuenta
# ============================================================
@router.get("/{account_id}/balance", response_model=schemas.AccountBalanceOut)
def get_account_balance(account_id: UUID, db: Session = Depends(database.get_db)):
    """
    Obtiene el balance actual de una cuenta bancaria.
    """
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    return {
        "account_id": account.id,
        "balance": float(account.balance),
        "currency": account.currency,
        "updated_at": datetime.utcnow()
    }

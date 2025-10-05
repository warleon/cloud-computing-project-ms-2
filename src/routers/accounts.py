from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime

from .. import models, schemas, database
from ..services.ms1_client import ms1

router = APIRouter()

@router.post("/", response_model=schemas.AccountOut, status_code=201)
def create_account(payload: schemas.AccountCreate, db: Session = Depends(database.get_db)):
    try:
        exists = ms1.customer_exists(str(payload.customer_id))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not exists:
        raise HTTPException(status_code=422, detail="Customer not found in MS1")

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

@router.get("/", response_model=list[schemas.AccountOut])
def list_accounts(
    db: Session = Depends(database.get_db),
    skip: int = Query(0, ge=0, description="Número de registros a omitir (offset)"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de cuentas a retornar"),
    status: str | None = Query(None, description="Filtrar por estado: ACTIVE | BLOCKED | CLOSED"),
    type: str | None = Query(None, description="Filtrar por tipo: SAVINGS | CHECKING | BUSINESS"),
):
    query = db.query(models.Account)
    if status:
        query = query.filter(models.Account.status == status.upper())
    if type:
        query = query.filter(models.Account.type == type.upper())
    accounts = query.offset(skip).limit(limit).all()
    return accounts

@router.get("/{account_id}", response_model=schemas.AccountOut)
def get_account(account_id: UUID, db: Session = Depends(database.get_db)):
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account

@router.put("/{account_id}/status", response_model=schemas.AccountOut)
def update_account_status(account_id: UUID, payload: schemas.AccountUpdateStatus, db: Session = Depends(database.get_db)):
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    account.status = payload.status.upper()
    if account.status == "CLOSED":
        account.closed_at = datetime.utcnow()
    db.commit()
    db.refresh(account)
    return account

@router.get("/{account_id}/balance", response_model=schemas.AccountBalanceOut)
def get_account_balance(account_id: UUID, db: Session = Depends(database.get_db)):
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return {
        "account_id": account.id,
        "balance": float(account.balance),
        "currency": account.currency,
        "updated_at": datetime.utcnow()
    }

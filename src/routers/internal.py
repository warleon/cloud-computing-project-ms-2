from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from uuid import UUID
import os
from datetime import datetime
from ..services.ms3_notifier import notify_balance_updated

from .. import models, schemas, database
import asyncio

router = APIRouter()

# ============================================================
# Utilidades internas
# ============================================================

def _require_service_key(service_key: str | None):
    expected = os.getenv("SERVICE_KEY_FOR_MS3", "")
    if not service_key or service_key != expected:
        raise HTTPException(status_code=403, detail="Unauthorized service")

def _validate_account_for_transfer(account: models.Account, role: str):
    if account.status != "ACTIVE":
        raise HTTPException(
            status_code=422,
            detail=f"{role} account is not ACTIVE (status={account.status})"
        )

# ============================================================
# Endpoint: Transferencia interna (MS3 -> MS2)
# ============================================================
@router.post(
    "/transfer",
    response_model=schemas.TransferResponse,
    summary="Transfiere fondos entre dos cuentas (idempotente por requestId)",
    description="""
Opera una **transferencia interna** entre dos cuentas **de forma atómica**:
- Bloquea ambas cuentas con **FOR UPDATE**.
- Valida **estado**, **moneda** y **fondos**.
- Inserta **dos asientos contables** (DEBIT/CREDIT) y **actualiza balances**.
- **Idempotencia** por `requestId`: si ya fue aplicada, retorna el resultado previo.
"""
)
def transfer_funds(
    payload: schemas.TransferRequest,
    db: Session = Depends(database.get_db),
    service_key: str | None = Header(default=None, alias="x-service-key"),
):
    # 1) Autenticación inter-servicios
    _require_service_key(service_key)

    if payload.amount <= 0:
        raise HTTPException(status_code=422, detail="Amount must be > 0")

    # 2) Idempotencia: si ya existen asientos con este tx_id (usamos requestId como tx_id), devolvemos OK
    #    Nota: si prefieres usar payload.txId (de MS3) como tx_id, intercámbialo abajo.
    existing = (
        db.query(models.LedgerEntry)
        .filter(models.LedgerEntry.tx_id == payload.requestId)
        .first()
    )
    if existing:
        # Buscamos las dos líneas (DEBIT/CREDIT) asociadas al mismo tx_id para responder balances
        debit = (
            db.query(models.LedgerEntry)
            .filter(
                models.LedgerEntry.tx_id == payload.requestId,
                models.LedgerEntry.direction == "DEBIT",
            )
            .first()
        )
        credit = (
            db.query(models.LedgerEntry)
            .filter(
                models.LedgerEntry.tx_id == payload.requestId,
                models.LedgerEntry.direction == "CREDIT",
            )
            .first()
        )

        # Intentamos leer balances actuales de las cuentas involucradas
        from_acc = (
            db.query(models.Account)
            .filter(models.Account.id == payload.fromAccount)
            .first()
        )
        to_acc = (
            db.query(models.Account)
            .filter(models.Account.id == payload.toAccount)
            .first()
        )
        return schemas.TransferResponse(
            status="OK",
            debitEntryId=debit.id if debit else None,
            creditEntryId=credit.id if credit else None,
            balances={
                "from": float(from_acc.balance) if from_acc else 0.0,
                "to": float(to_acc.balance) if to_acc else 0.0,
            },
            message="Idempotent replay",
        )


    # 3) Transacción SQL con locking de ambas cuentas
    try:
        # Bloqueamos en orden por UUID para evitar deadlocks
        ids_sorted = sorted([payload.fromAccount, payload.toAccount], key=lambda x: str(x))

        acc_a = (
            db.query(models.Account)
            .filter(models.Account.id == ids_sorted[0])
            .with_for_update()
            .first()
        )
        acc_b = (
            db.query(models.Account)
            .filter(models.Account.id == ids_sorted[1])
            .with_for_update()
            .first()
        )

        # Reasignar semántica a from/to
        if not acc_a or not acc_b:
            raise HTTPException(status_code=404, detail="Account not found")

        if acc_a.id == payload.fromAccount:
            from_acc, to_acc = acc_a, acc_b
        else:
            from_acc, to_acc = acc_b, acc_a

        # 4) Validaciones de negocio
        _validate_account_for_transfer(from_acc, "Origin")
        _validate_account_for_transfer(to_acc, "Destination")

        if from_acc.currency != to_acc.currency or from_acc.currency != payload.currency:
            raise HTTPException(
                status_code=422,
                detail=f"Currency mismatch (from={from_acc.currency}, to={to_acc.currency}, req={payload.currency})",
            )

        if float(from_acc.balance) < float(payload.amount):
            raise HTTPException(status_code=400, detail="Insufficient funds")

        # 5) Aplicar movimiento atómico
        # Usamos requestId como tx_id; si prefieres, usa payload.txId.
        tx_identifier: UUID = payload.requestId

        debit = models.LedgerEntry(
            account_id=from_acc.id,
            tx_id=tx_identifier,
            direction="DEBIT",
            amount=payload.amount,
        )
        credit = models.LedgerEntry(
            account_id=to_acc.id,
            tx_id=tx_identifier,
            direction="CREDIT",
            amount=payload.amount,
        )

        # Actualizamos balances
        from_acc.balance = float(from_acc.balance) - float(payload.amount)
        to_acc.balance = float(to_acc.balance) + float(payload.amount)

        # Persistimos todo
        db.add(debit)
        db.add(credit)
        db.commit()
        db.refresh(from_acc)
        db.refresh(to_acc)
        db.refresh(debit)
        db.refresh(credit)

        if os.getenv("MS3_NOTIFY_ENABLED", "false").lower() == "true":
            asyncio.create_task(
                notify_balance_updated(str(from_acc.id), float(from_acc.balance), from_acc.currency)
            )
            asyncio.create_task(
                notify_balance_updated(str(to_acc.id), float(to_acc.balance), to_acc.currency)
            )

        return schemas.TransferResponse(
            status="OK",
            debitEntryId=debit.id,
            creditEntryId=credit.id,
            balances={"from": float(from_acc.balance), "to": float(to_acc.balance)},
            message="Transfer applied",
        )

    except HTTPException:
        # Errores de negocio/validación: no hacer rollback aquí (FastAPI lo maneja tras levantar)
        raise
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

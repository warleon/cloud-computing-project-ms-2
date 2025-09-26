from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_
from . import models

# ============================================================
# ACCOUNTS – CRUD
# ============================================================

def create_account(
    db: Session,
    *,
    customer_id: UUID,
    acc_type: str,
    currency: str,
    opened_at: Optional[datetime] = None
) -> models.Account:
    """Crea una cuenta con balance 0 y estado ACTIVE."""
    account = models.Account(
        customer_id=customer_id,
        type=acc_type.upper(),
        status="ACTIVE",
        currency=currency.upper(),
        balance=0,
        opened_at=opened_at or datetime.utcnow()
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def get_account(db: Session, account_id: UUID) -> Optional[models.Account]:
    """Obtiene una cuenta por ID."""
    return db.query(models.Account).filter(models.Account.id == account_id).first()


def list_accounts(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 10,
    status: Optional[str] = None,
    acc_type: Optional[str] = None
) -> List[models.Account]:
    """Lista cuentas con filtros opcionales y paginación."""
    q = db.query(models.Account)
    if status:
        q = q.filter(models.Account.status == status.upper())
    if acc_type:
        q = q.filter(models.Account.type == acc_type.upper())
    return q.offset(skip).limit(limit).all()


def update_account_status(
    db: Session,
    *,
    account_id: UUID,
    new_status: str
) -> Optional[models.Account]:
    """Actualiza el estado de la cuenta. Si se cierra, setea closed_at."""
    acc = get_account(db, account_id)
    if not acc:
        return None
    acc.status = new_status.upper()
    if acc.status == "CLOSED":
        acc.closed_at = datetime.utcnow()
    db.commit()
    db.refresh(acc)
    return acc


def get_account_balance(db: Session, *, account_id: UUID):
    acc = get_account(db, account_id)
    if not acc:
        return None
    return (
        UUID(str(acc.id)),              # fuerza el tipo
        float(acc.balance),             # convierte Decimal → float
        str(acc.currency),              # asegura str
        datetime.utcnow()
    )


# ============================================================
# LEDGER – CRUD
# ============================================================

def list_ledger_entries(
    db: Session,
    *,
    account_id: UUID,
    skip: int = 0,
    limit: int = 50,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None
) -> List[models.LedgerEntry]:
    """Lista las entradas de ledger con filtros y paginación."""
    q = db.query(models.LedgerEntry).filter(models.LedgerEntry.account_id == account_id)

    if from_date:
        q = q.filter(models.LedgerEntry.created_at >= from_date)
    if to_date:
        q = q.filter(models.LedgerEntry.created_at <= to_date)
    if min_amount is not None:
        q = q.filter(models.LedgerEntry.amount >= min_amount)
    if max_amount is not None:
        q = q.filter(models.LedgerEntry.amount <= max_amount)

    return q.order_by(models.LedgerEntry.created_at.desc()).offset(skip).limit(limit).all()


def create_ledger_entry(
    db: Session,
    *,
    account_id: UUID,
    direction: str,
    amount: float,
    tx_id: Optional[UUID] = None
) -> models.LedgerEntry:
    """Crea una entrada en ledger (DEBIT o CREDIT)."""
    entry = models.LedgerEntry(
        account_id=account_id,
        tx_id=tx_id,
        direction=direction.upper(),
        amount=amount
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# ============================================================
# TRANSFER – RULES & TX (UTIL PARA INTERNAL ROUTER)
# ============================================================

class TransferError(Exception):
    """Excepción de negocio para transferencias."""
    def __init__(self, message: str, http_status: int = 400):
        super().__init__(message)
        self.http_status = http_status


def _validate_account_active(account: models.Account, role: str) -> None:
    if account.status != "ACTIVE":
        raise TransferError(f"{role} account is not ACTIVE (status={account.status})", http_status=422)


def _lock_accounts_for_update(db: Session, a_id: UUID, b_id: UUID) -> Tuple[models.Account, models.Account]:
    """
    Bloquea 2 cuentas por orden (para minimizar deadlocks) y retorna en el mismo
    orden semántico (from_acc, to_acc) según IDs recibidos.
    """
    ids_sorted = sorted([a_id, b_id], key=lambda x: str(x))
    acc_a = db.query(models.Account).filter(models.Account.id == ids_sorted[0]).with_for_update().first()
    acc_b = db.query(models.Account).filter(models.Account.id == ids_sorted[1]).with_for_update().first()
    if not acc_a or not acc_b:
        raise TransferError("Account not found", http_status=404)

    if acc_a.id == a_id:
        return acc_a, acc_b
    return acc_b, acc_a


def apply_transfer_atomic(
    db: Session,
    *,
    request_id: UUID,
    from_account_id: UUID,
    to_account_id: UUID,
    amount: float,
    currency: str,
    tx_id: Optional[UUID] = None
) -> Tuple[models.LedgerEntry, models.LedgerEntry, float, float]:
    """
    Ejecuta una transferencia **atómica e idempotente** entre cuentas:
      - Chequea si ya existe tx con mismo request_id (replay).
      - Bloquea ambas cuentas con FOR UPDATE.
      - Valida estado/currency/fondos.
      - Inserta DEBIT/CREDIT y actualiza balances.
      - Commit y retorna (debit_entry, credit_entry, new_from_balance, new_to_balance)
    """
    if amount <= 0:
        raise TransferError("Amount must be > 0", http_status=422)

    # Idempotencia: si ya fue aplicada, devolver asientos existentes
    existing_debit = db.query(models.LedgerEntry).filter(
        and_(models.LedgerEntry.tx_id == request_id, models.LedgerEntry.direction == "DEBIT")
    ).first()
    existing_credit = db.query(models.LedgerEntry).filter(
        and_(models.LedgerEntry.tx_id == request_id, models.LedgerEntry.direction == "CREDIT")
    ).first()

    if existing_debit and existing_credit:
        # leer balances actuales
        from_acc = db.query(models.Account).filter(models.Account.id == from_account_id).first()
        to_acc = db.query(models.Account).filter(models.Account.id == to_account_id).first()
        return existing_debit, existing_credit, float(from_acc.balance) if from_acc else 0.0, float(to_acc.balance) if to_acc else 0.0

    try:
        # 1) Lock de cuentas (ordena para evitar deadlocks)
        from_acc, to_acc = _lock_accounts_for_update(db, from_account_id, to_account_id)

        # 2) Validaciones de negocio
        _validate_account_active(from_acc, "Origin")
        _validate_account_active(to_acc, "Destination")

        if from_acc.currency != to_acc.currency or from_acc.currency != currency.upper():
            raise TransferError(
                f"Currency mismatch (from={from_acc.currency}, to={to_acc.currency}, req={currency})",
                http_status=422
            )

        if float(from_acc.balance) < float(amount):
            raise TransferError("Insufficient funds", http_status=400)

        # 3) Asientos y actualización de balances
        tx_identifier = request_id  # puede ser tx_id si lo prefieres
        debit = models.LedgerEntry(
            account_id=from_acc.id,
            tx_id=tx_identifier,
            direction="DEBIT",
            amount=amount
        )
        credit = models.LedgerEntry(
            account_id=to_acc.id,
            tx_id=tx_identifier,
            direction="CREDIT",
            amount=amount
        )

        from_acc.balance = float(from_acc.balance) - float(amount)
        to_acc.balance = float(to_acc.balance) + float(amount)

        db.add(debit)
        db.add(credit)
        db.commit()
        db.refresh(from_acc)
        db.refresh(to_acc)
        db.refresh(debit)
        db.refresh(credit)

        return debit, credit, float(from_acc.balance), float(to_acc.balance)

    except TransferError:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        raise TransferError(f"Database error: {str(e)}", http_status=500)
    except Exception as e:
        db.rollback()
        raise TransferError(f"Unexpected error: {str(e)}", http_status=500)

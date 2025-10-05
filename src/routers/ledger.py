# src/routers/ledger.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from typing import Optional, List

from .. import models, schemas, database

router = APIRouter()

# ============================================================
# Consultar movimientos contables (ledger) de una cuenta
# ============================================================
@router.get("/{account_id}", response_model=List[schemas.LedgerEntryOut])
def get_ledger_entries(
    account_id: UUID,
    db: Session = Depends(database.get_db),
    skip: int = Query(0, ge=0, description="Número de registros a omitir (offset)"),
    limit: int = Query(50, ge=1, le=500, description="Número máximo de registros a devolver"),
    from_date: Optional[datetime] = Query(None, description="Filtrar movimientos desde esta fecha"),
    to_date: Optional[datetime] = Query(None, description="Filtrar movimientos hasta esta fecha"),
    min_amount: Optional[float] = Query(None, description="Filtrar movimientos con monto >= a este valor"),
    max_amount: Optional[float] = Query(None, description="Filtrar movimientos con monto <= a este valor"),
    direction: Optional[str] = Query(None, description="Filtrar por tipo de movimiento: CREDIT o DEBIT"),
):
    """
    Retorna el historial de **movimientos contables (ledger_entries)** de una cuenta bancaria.

    Soporta:
    - Paginación (`skip`, `limit`)
    - Filtros opcionales de fecha, monto y tipo de movimiento
    - Orden descendente por fecha
    """

    # Validar existencia de la cuenta
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Evitar acceder a cuentas cerradas (opcional)
    if account.status == "CLOSED":
        raise HTTPException(status_code=403, detail="Account is closed and cannot be queried")

    # Validar rango de fechas
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=400, detail="Invalid date range: from_date must be <= to_date")

    # Query base
    query = db.query(models.LedgerEntry).filter(models.LedgerEntry.account_id == account_id)

    # Filtros opcionales
    if from_date:
        query = query.filter(models.LedgerEntry.created_at >= from_date)
    if to_date:
        query = query.filter(models.LedgerEntry.created_at <= to_date)
    if min_amount:
        query = query.filter(models.LedgerEntry.amount >= min_amount)
    if max_amount:
        query = query.filter(models.LedgerEntry.amount <= max_amount)
    if direction:
        query = query.filter(models.LedgerEntry.direction == direction.upper())

    # Ordenar y paginar
    entries = query.order_by(models.LedgerEntry.created_at.desc()).offset(skip).limit(limit).all()

    return entries

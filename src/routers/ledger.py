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
):
    """
    Retorna el historial de **movimientos contables (ledger_entries)** de una cuenta bancaria.
    - Se soporta paginación (`skip`, `limit`).
    - Se pueden aplicar filtros opcionales de fecha y rango de montos.
    - Los resultados se devuelven ordenados por fecha descendente.
    """
    # Validar existencia de la cuenta
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

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

    # Ordenar y paginar
    entries = query.order_by(models.LedgerEntry.created_at.desc()).offset(skip).limit(limit).all()

    return entries

# src/models.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import String, Numeric, TIMESTAMP, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID   # <-- tipo UUID de Postgres
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .database import Base

# ============================================================
# Tabla: Accounts
# ============================================================
class Account(Base):
    __tablename__ = "accounts"
    __allow_unmapped__ = True  # silencia advertencias de analizadores estáticos

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # SAVINGS|CHECKING|BUSINESS
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")  # ACTIVE|BLOCKED|CLOSED
    currency: Mapped[str] = mapped_column(String(3), nullable=False)  # ISO 4217
    opened_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    balance: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("balance >= 0", name="check_balance_non_negative"),
    )


# ============================================================
# Tabla: Ledger Entries (movimientos contables)
# ============================================================
class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __allow_unmapped__ = True

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    tx_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )  # referencia opcional a MS3
    direction: Mapped[str] = mapped_column(String(6), nullable=False)  # CREDIT | DEBIT
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="check_amount_positive"),
        CheckConstraint("direction IN ('CREDIT','DEBIT')", name="check_valid_direction"),
    )

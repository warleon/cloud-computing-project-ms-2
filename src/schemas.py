from __future__ import annotations

from uuid import UUID
from datetime import datetime
from typing import Annotated, Optional, List, Dict

from pydantic import BaseModel, Field, ConfigDict, StringConstraints

# =====================================================================
# Tipos reusables con restricciones (Pydantic v2)
# =====================================================================

IsoCurrency = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, min_length=3, max_length=3),
]

AccountType = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^(SAVINGS|CHECKING|BUSINESS)$"),
]

AccountStatus = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^(ACTIVE|BLOCKED|CLOSED)$"),
]

LedgerDirection = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^(CREDIT|DEBIT)$"),
]


# =====================================================================
# SCHEMAS – ACCOUNTS
# =====================================================================

class AccountCreate(BaseModel):
    """Payload para crear una cuenta bancaria."""
    customer_id: UUID = Field(..., description="ID del cliente (proveniente del MS1)")
    type: AccountType = Field(..., description="Tipo de cuenta: SAVINGS, CHECKING o BUSINESS")
    currency: IsoCurrency = Field(..., description="Código de moneda ISO 4217, ej: PEN, USD")


class AccountUpdateStatus(BaseModel):
    """Payload para actualizar el estado de una cuenta."""
    status: AccountStatus = Field(..., description="Nuevo estado: ACTIVE, BLOCKED o CLOSED")


class AccountOut(BaseModel):
    """Respuesta detallada de una cuenta."""
    id: UUID
    customer_id: UUID
    type: str
    status: str
    balance: float
    currency: str
    opened_at: datetime
    closed_at: Optional[datetime]

    # Pydantic v2: habilita lectura desde objetos ORM (SQLAlchemy)
    model_config = ConfigDict(from_attributes=True)


class AccountBalanceOut(BaseModel):
    """Respuesta simplificada del balance de una cuenta."""
    account_id: UUID
    balance: float
    currency: str
    updated_at: datetime


# =====================================================================
# SCHEMAS – LEDGER
# =====================================================================

class LedgerEntryCreate(BaseModel):
    """Payload opcional si algún servicio externo crea entradas manuales."""
    account_id: UUID
    direction: LedgerDirection
    amount: float


class LedgerEntryOut(BaseModel):
    """Respuesta de una entrada contable."""
    id: UUID
    account_id: UUID
    tx_id: Optional[UUID]
    direction: str
    amount: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =====================================================================
# SCHEMAS – TRANSFERENCIA INTERNA (MS3 -> MS2)
# =====================================================================

class TransferRequest(BaseModel):
    """Payload de transferencia interna (consumida por MS3)."""
    requestId: UUID = Field(..., description="ID único para idempotencia")
    fromAccount: UUID
    toAccount: UUID
    amount: float = Field(..., gt=0, description="Monto de la transferencia (>0)")
    currency: IsoCurrency
    txId: Optional[UUID] = Field(None, description="ID de la transacción generado por MS3 (opcional)")


class TransferResponse(BaseModel):
    """Respuesta a la transferencia interna."""
    status: str = Field(..., description="OK o ERROR")
    debitEntryId: Optional[UUID]
    creditEntryId: Optional[UUID]
    balances: Optional[Dict[str, float]]  # <-- siempre float, nunca None
    message: Optional[str]

    model_config = ConfigDict(from_attributes=True)

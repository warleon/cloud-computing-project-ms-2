from __future__ import annotations
from datetime import datetime
from typing import Annotated, Optional, Dict
from pydantic import BaseModel, Field, ConfigDict, StringConstraints
from enum import Enum


# ============================================================
# ENUMS Y TIPOS BÁSICOS REUSABLES
# ============================================================

class AccountType(str, Enum):
    SAVINGS = "SAVINGS"
    CHECKING = "CHECKING"
    BUSINESS = "BUSINESS"


class AccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    CLOSED = "CLOSED"


class LedgerDirection(str, Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class IsoCurrency(str, Enum):
    PEN = "PEN"
    USD = "USD"
    EUR = "EUR"


# Tipo base para IDs genéricos (pueden ser UUID o string tipo ObjectId)
ObjectIdStr = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=12,
        max_length=36,
        pattern=r"^[a-fA-F0-9\-]+$",
    ),
]


# ============================================================
# SCHEMAS – ACCOUNTS
# ============================================================

class AccountCreate(BaseModel):
    """
    Payload para crear una cuenta bancaria.
    MS1 proporciona el ID del cliente (ObjectId de MongoDB),
    y MS2 valida con el microservicio MS1 antes de crear la cuenta.
    """
    customer_id: ObjectIdStr = Field(
        ...,
        description="ID del cliente (proveniente del MS1, tipo ObjectId de MongoDB)"
    )
    type: AccountType = Field(..., description="Tipo de cuenta: SAVINGS, CHECKING o BUSINESS")
    currency: IsoCurrency = Field(..., description="Código de moneda ISO 4217, ej: PEN, USD, EUR")


class AccountUpdateStatus(BaseModel):
    """Payload para actualizar el estado de una cuenta."""
    status: AccountStatus = Field(..., description="Nuevo estado: ACTIVE, BLOCKED o CLOSED")


class AccountOut(BaseModel):
    """Respuesta detallada de una cuenta."""
    id: ObjectIdStr
    customer_id: ObjectIdStr
    type: AccountType
    status: AccountStatus
    balance: float
    currency: IsoCurrency
    opened_at: datetime
    closed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AccountBalanceOut(BaseModel):
    """Respuesta simplificada del balance de una cuenta."""
    account_id: ObjectIdStr
    balance: float
    currency: IsoCurrency
    updated_at: datetime


# ============================================================
# SCHEMAS – LEDGER (ASIENTOS CONTABLES)
# ============================================================

class LedgerEntryCreate(BaseModel):
    """Payload opcional si algún servicio externo crea entradas manuales."""
    account_id: ObjectIdStr
    direction: LedgerDirection
    amount: float = Field(..., gt=0, description="Monto del movimiento (> 0)")


class LedgerEntryOut(BaseModel):
    """Respuesta de una entrada contable."""
    id: ObjectIdStr
    account_id: ObjectIdStr
    tx_id: Optional[ObjectIdStr] = None
    direction: LedgerDirection
    amount: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# SCHEMAS – TRANSFERENCIA INTERNA (MS3 → MS2)
# ============================================================

class TransferRequest(BaseModel):
    """
    Payload de transferencia interna (consumida por MS3).
    Representa un débito/crédito simultáneo en cuentas diferentes.
    """
    requestId: ObjectIdStr = Field(..., description="ID único para idempotencia")
    fromAccount: ObjectIdStr = Field(..., description="ID de la cuenta origen")
    toAccount: ObjectIdStr = Field(..., description="ID de la cuenta destino")
    amount: float = Field(..., gt=0, description="Monto de la transferencia (> 0)")
    currency: IsoCurrency
    txId: Optional[ObjectIdStr] = Field(None, description="ID de la transacción generada por MS3 (opcional)")


class TransferResponse(BaseModel):
    """Respuesta a la transferencia interna (devuelta a MS3)."""
    status: str = Field(..., description="OK o ERROR")
    debitEntryId: Optional[ObjectIdStr] = None
    creditEntryId: Optional[ObjectIdStr] = None
    balances: Optional[Dict[str, float]] = None
    message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

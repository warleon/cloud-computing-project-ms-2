from __future__ import annotations
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Annotated

from pydantic import BaseModel, Field, ConfigDict, StringConstraints

IsoCurrency = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_upper=True,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$"
    )
]

AccountType = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_upper=True,
        pattern=r"^(SAVINGS|CHECKING|BUSINESS)$"
    )
]

AccountStatus = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_upper=True,
        pattern=r"^(ACTIVE|BLOCKED|CLOSED)$"
    )
]

LedgerDirection = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_upper=True,
        pattern=r"^(CREDIT|DEBIT)$"
    )
]

class AccountCreate(BaseModel):
    customer_id: str = Field(..., min_length=24, max_length=24, description="ObjectId de MS1 (24 hex)")
    type: AccountType = Field(..., description="SAVINGS, CHECKING o BUSINESS")
    currency: IsoCurrency = Field(..., description="ISO 4217, ej: PEN, USD")

class AccountUpdateStatus(BaseModel):
    status: AccountStatus = Field(..., description="ACTIVE, BLOCKED o CLOSED")

class AccountOut(BaseModel):
    id: UUID
    customer_id: str
    type: str
    status: str
    balance: float
    currency: str
    opened_at: datetime
    closed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class AccountBalanceOut(BaseModel):
    account_id: UUID
    balance: float
    currency: str
    updated_at: datetime

class LedgerEntryCreate(BaseModel):
    account_id: UUID
    direction: LedgerDirection
    amount: float = Field(..., gt=0)

class LedgerEntryOut(BaseModel):
    id: UUID
    account_id: UUID
    tx_id: Optional[UUID]
    direction: str
    amount: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TransferRequest(BaseModel):
    requestId: UUID
    fromAccount: UUID
    toAccount: UUID
    amount: float = Field(..., gt=0)
    currency: IsoCurrency
    txId: Optional[UUID] = None

class TransferResponse(BaseModel):
    status: str
    debitEntryId: Optional[UUID]
    creditEntryId: Optional[UUID]
    balances: Optional[Dict[str, float]]
    message: Optional[str]

    model_config = ConfigDict(from_attributes=True)

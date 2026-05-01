from pydantic import BaseModel, field_validator
from decimal import Decimal
from datetime import datetime
from typing import Optional
from app.models.account import AccountType, AccountStatus
from app.models.transaction import TransactionType, TransactionStatus


# ─── Account Schemas ──────────────────────────────────────────────────────────

class AccountCreate(BaseModel):
    account_type: AccountType = AccountType.SAVINGS


class AccountResponse(BaseModel):
    id: str
    account_number: str
    account_type: AccountType
    status: AccountStatus
    balance_npr: Decimal
    currency: str
    interest_rate: Decimal
    daily_transfer_limit_paisa: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountSummary(BaseModel):
    id: str
    account_number: str
    account_type: AccountType
    balance_npr: Decimal
    status: AccountStatus

    model_config = {"from_attributes": True}


# ─── Transaction Schemas ──────────────────────────────────────────────────────

class TransferRequest(BaseModel):
    receiver_account_number: str
    amount_npr: Decimal
    description: Optional[str] = None

    @field_validator("amount_npr")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be positive")
        if v > 1_000_000:
            raise ValueError("Amount exceeds single transaction limit of Rs. 10,00,000")
        # Max 2 decimal places
        if v != round(v, 2):
            raise ValueError("Amount can have at most 2 decimal places")
        return v


class DepositRequest(BaseModel):
    account_id: str
    amount_npr: Decimal
    description: Optional[str] = None

    @field_validator("amount_npr")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class TransactionResponse(BaseModel):
    id: str
    reference: str
    transaction_type: TransactionType
    status: TransactionStatus
    amount_npr: Decimal
    fee_paisa: int
    description: Optional[str]
    sender_account_id: Optional[str]
    receiver_account_id: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class QRPaymentRequest(BaseModel):
    qr_data: str  # Encoded QR payload
    amount_npr: Decimal
    description: Optional[str] = None


# ─── Loan Schemas ─────────────────────────────────────────────────────────────

class LoanApplicationRequest(BaseModel):
    account_id: str
    loan_type: str
    principal_npr: Decimal
    tenure_months: int
    purpose: Optional[str] = None
    collateral: Optional[str] = None

    @field_validator("tenure_months")
    @classmethod
    def validate_tenure(cls, v: int) -> int:
        if v < 1 or v > 360:
            raise ValueError("Tenure must be between 1 and 360 months")
        return v


class LoanResponse(BaseModel):
    id: str
    loan_type: str
    status: str
    principal_npr: Decimal
    outstanding_paisa: int
    emi_paisa: int
    interest_rate: Decimal
    tenure_months: int
    applied_at: datetime

    model_config = {"from_attributes": True}

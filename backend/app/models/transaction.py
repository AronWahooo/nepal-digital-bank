from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum as SAEnum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.core.database import Base


class TransactionType(str, enum.Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    QR_PAYMENT = "qr_payment"
    LOAN_DISBURSEMENT = "loan_disbursement"
    LOAN_REPAYMENT = "loan_repayment"
    INTEREST_CREDIT = "interest_credit"
    FEE = "fee"


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    reference: Mapped[str] = mapped_column(String(30), unique=True, index=True)  # e.g. TXN3F8A...

    # Accounts involved
    sender_account_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("accounts.id"), nullable=True, index=True
    )
    receiver_account_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("accounts.id"), nullable=True, index=True
    )

    transaction_type: Mapped[TransactionType] = mapped_column(SAEnum(TransactionType))
    status: Mapped[TransactionStatus] = mapped_column(SAEnum(TransactionStatus), default=TransactionStatus.PENDING)

    # Amount in paisa
    amount_paisa: Mapped[int] = mapped_column(Integer)
    fee_paisa: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="NPR")

    # Balances after transaction (for audit trail)
    sender_balance_after_paisa: Mapped[int | None] = mapped_column(Integer, nullable=True)
    receiver_balance_after_paisa: Mapped[int | None] = mapped_column(Integer, nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Metadata
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    sender_account: Mapped["Account"] = relationship(
        "Account", back_populates="sent_transactions", foreign_keys=[sender_account_id]
    )
    receiver_account: Mapped["Account"] = relationship(
        "Account", back_populates="received_transactions", foreign_keys=[receiver_account_id]
    )

    @property
    def amount_npr(self):
        from decimal import Decimal
        return Decimal(self.amount_paisa) / 100

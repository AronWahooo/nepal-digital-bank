from sqlalchemy import String, Numeric, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from decimal import Decimal
import enum

from app.core.database import Base


class AccountType(str, enum.Enum):
    SAVINGS = "savings"
    CURRENT = "current"
    FIXED_DEPOSIT = "fixed_deposit"


class AccountStatus(str, enum.Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    account_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    account_type: Mapped[AccountType] = mapped_column(SAEnum(AccountType), default=AccountType.SAVINGS)
    status: Mapped[AccountStatus] = mapped_column(SAEnum(AccountStatus), default=AccountStatus.ACTIVE)

    # Balance stored in NPR paisa (1 NPR = 100 paisa) to avoid float issues
    balance_paisa: Mapped[int] = mapped_column(default=0)  # integer, no float
    currency: Mapped[str] = mapped_column(String(3), default="NPR")

    # Interest rate (for savings/FD)
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("5.00"))

    # Daily limit in NPR paisa
    daily_transfer_limit_paisa: Mapped[int] = mapped_column(default=50000 * 100)  # Rs. 50,000

    # QR payment
    qr_code_data: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="accounts")
    sent_transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="sender_account", foreign_keys="Transaction.sender_account_id"
    )
    received_transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="receiver_account", foreign_keys="Transaction.receiver_account_id"
    )

    @property
    def balance_npr(self) -> Decimal:
        return Decimal(self.balance_paisa) / 100

    def can_debit(self, amount_paisa: int) -> bool:
        return self.status == AccountStatus.ACTIVE and self.balance_paisa >= amount_paisa

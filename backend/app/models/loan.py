from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, Enum as SAEnum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime, date
from decimal import Decimal
import enum

from app.core.database import Base


class LoanType(str, enum.Enum):
    PERSONAL = "personal"
    HOME = "home"
    BUSINESS = "business"
    EDUCATION = "education"
    VEHICLE = "vehicle"


class LoanStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DISBURSED = "disbursed"
    ACTIVE = "active"
    REPAID = "repaid"
    DEFAULTED = "defaulted"
    REJECTED = "rejected"


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.id"))

    loan_type: Mapped[LoanType] = mapped_column(SAEnum(LoanType))
    status: Mapped[LoanStatus] = mapped_column(SAEnum(LoanStatus), default=LoanStatus.PENDING)

    # All amounts in paisa
    principal_paisa: Mapped[int] = mapped_column(Integer)
    outstanding_paisa: Mapped[int] = mapped_column(Integer, default=0)
    emi_paisa: Mapped[int] = mapped_column(Integer, default=0)

    interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))  # Annual %
    tenure_months: Mapped[int] = mapped_column(Integer)

    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    collateral: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disbursed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[date | None] = mapped_column(nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
    account: Mapped["Account"] = relationship("Account")

    @property
    def principal_npr(self) -> Decimal:
        return Decimal(self.principal_paisa) / 100

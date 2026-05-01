from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal
from datetime import datetime, timezone, date
import uuid

from app.core.database import get_db
from app.models.user import User
from app.models.account import Account, AccountStatus
from app.models.loan import Loan, LoanType, LoanStatus
from app.schemas.banking import LoanApplicationRequest, LoanResponse
from app.api.v1.deps import get_current_user, require_admin

router = APIRouter(prefix="/loans", tags=["Loans"])

# Interest rates by loan type (annual %)
INTEREST_RATES = {
    "personal": Decimal("18.00"),
    "home": Decimal("10.50"),
    "business": Decimal("14.00"),
    "education": Decimal("8.00"),
    "vehicle": Decimal("12.00"),
}

# Max loan amounts in NPR
MAX_LOAN_AMOUNTS = {
    "personal": 500_000,
    "home": 10_000_000,
    "business": 5_000_000,
    "education": 2_000_000,
    "vehicle": 3_000_000,
}


def calculate_emi(principal: int, annual_rate: Decimal, tenure_months: int) -> int:
    """EMI = P * r * (1+r)^n / ((1+r)^n - 1) where r = monthly rate."""
    if annual_rate == 0:
        return principal // tenure_months
    monthly_rate = float(annual_rate) / 100 / 12
    n = tenure_months
    emi = principal * monthly_rate * (1 + monthly_rate) ** n / ((1 + monthly_rate) ** n - 1)
    return int(emi)


@router.post("/apply", response_model=LoanResponse, status_code=201)
async def apply_for_loan(
    body: LoanApplicationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_kyc_verified:
        raise HTTPException(
            status_code=403,
            detail="KYC verification required to apply for a loan. Visit your nearest branch.",
        )

    loan_type = body.loan_type.lower()
    if loan_type not in INTEREST_RATES:
        raise HTTPException(status_code=400, detail=f"Invalid loan type. Choose from: {list(INTEREST_RATES.keys())}")

    max_amount = MAX_LOAN_AMOUNTS[loan_type]
    if body.principal_npr > max_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum loan amount for {loan_type} is Rs. {max_amount:,}",
        )

    # Verify account belongs to user
    acc_result = await db.execute(
        select(Account).where(
            Account.id == body.account_id,
            Account.user_id == current_user.id,
            Account.status == AccountStatus.ACTIVE,
        )
    )
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Check no existing active loan
    existing = await db.execute(
        select(Loan).where(
            Loan.user_id == current_user.id,
            Loan.status.in_([LoanStatus.PENDING, LoanStatus.APPROVED, LoanStatus.ACTIVE]),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="You already have an active or pending loan. Repay it before applying again.",
        )

    principal_paisa = int(body.principal_npr * 100)
    rate = INTEREST_RATES[loan_type]
    emi = calculate_emi(principal_paisa, rate, body.tenure_months)

    loan = Loan(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        account_id=body.account_id,
        loan_type=LoanType(loan_type),
        principal_paisa=principal_paisa,
        outstanding_paisa=principal_paisa,
        emi_paisa=emi,
        interest_rate=rate,
        tenure_months=body.tenure_months,
        purpose=body.purpose,
        collateral=body.collateral,
    )
    db.add(loan)
    await db.commit()
    await db.refresh(loan)
    return loan


@router.get("", response_model=list[LoanResponse])
async def list_loans(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Loan).where(Loan.user_id == current_user.id).order_by(Loan.applied_at.desc())
    )
    return result.scalars().all()


@router.post("/{loan_id}/approve")
async def approve_loan(
    loan_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin: approve a pending loan."""
    result = await db.execute(select(Loan).where(Loan.id == loan_id))
    loan = result.scalar_one_or_none()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    if loan.status != LoanStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Loan is already {loan.status}")

    loan.status = LoanStatus.APPROVED
    loan.approved_at = datetime.now(timezone.utc)
    return {"message": "Loan approved", "loan_id": loan_id}


@router.post("/{loan_id}/disburse")
async def disburse_loan(
    loan_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin: disburse an approved loan into the customer's account."""
    result = await db.execute(select(Loan).where(Loan.id == loan_id))
    loan = result.scalar_one_or_none()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    if loan.status != LoanStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Loan must be approved before disbursement")

    # Credit the account
    acc_result = await db.execute(select(Account).where(Account.id == loan.account_id))
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Customer account not found")

    account.balance_paisa += loan.principal_paisa
    loan.status = LoanStatus.ACTIVE
    loan.disbursed_at = datetime.now(timezone.utc)
    loan.due_date = date.today().replace(month=date.today().month + 1)

    await db.commit()
    return {"message": f"Rs. {loan.principal_paisa / 100:,.2f} disbursed to account {account.account_number}"}


@router.post("/{loan_id}/reject")
async def reject_loan(
    loan_id: str,
    reason: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(Loan).where(Loan.id == loan_id))
    loan = result.scalar_one_or_none()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    loan.status = LoanStatus.REJECTED
    loan.rejection_reason = reason
    return {"message": "Loan rejected"}

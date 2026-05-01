from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.core.database import get_db
from app.core.security import generate_account_number
from app.models.user import User
from app.models.account import Account, AccountType, AccountStatus
from app.schemas.banking import AccountCreate, AccountResponse, AccountSummary
from app.api.v1.deps import get_current_user

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.post("", response_model=AccountResponse, status_code=201)
async def create_account(
    body: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new bank account. Each user can have up to 3 accounts."""
    existing = await db.execute(
        select(Account).where(
            Account.user_id == current_user.id,
            Account.status != AccountStatus.CLOSED,
        )
    )
    if len(existing.scalars().all()) >= 3:
        raise HTTPException(status_code=400, detail="Maximum 3 active accounts allowed per customer")

    account = Account(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        account_number=generate_account_number(),
        account_type=body.account_type,
        balance_paisa=0,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.get("", response_model=list[AccountSummary])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Account).where(
            Account.user_id == current_user.id,
            Account.status != AccountStatus.CLOSED,
        )
    )
    return result.scalars().all()


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.user_id == current_user.id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.get("/{account_id}/balance")
async def get_balance(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.user_id == current_user.id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return {
        "account_number": account.account_number,
        "balance_npr": str(account.balance_npr),
        "currency": "NPR",
        "status": account.status,
    }

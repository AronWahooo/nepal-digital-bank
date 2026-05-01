from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import uuid

from app.core.database import get_db
from app.core.security import generate_transaction_ref
from app.models.user import User
from app.models.account import Account, AccountStatus
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.audit_log import AuditLog
from app.schemas.banking import TransferRequest, DepositRequest, TransactionResponse
from app.api.v1.deps import get_current_user, require_admin

router = APIRouter(prefix="/transactions", tags=["Transactions"])

TRANSFER_FEE_PAISA = 0  # Free transfers (can set e.g. 500 = Rs. 5)


def _audit(db, user_id, action, description, request, entity_id=None):
    log = AuditLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        action=action,
        description=description,
        entity_id=entity_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(log)


@router.post("/transfer", response_model=TransactionResponse)
async def transfer_funds(
    body: TransferRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Transfer funds between accounts. Atomic: both debit and credit happen
    in the same DB transaction. Fails entirely if anything goes wrong.
    """
    amount_paisa = int(body.amount_npr * 100)

    # Find sender's primary active account
    sender_result = await db.execute(
        select(Account).where(
            Account.user_id == current_user.id,
            Account.status == AccountStatus.ACTIVE,
        )
    )
    sender = sender_result.scalars().first()
    if not sender:
        raise HTTPException(status_code=404, detail="No active sender account found")

    # Find receiver by account number
    receiver_result = await db.execute(
        select(Account).where(
            Account.account_number == body.receiver_account_number,
            Account.status == AccountStatus.ACTIVE,
        )
    )
    receiver = receiver_result.scalar_one_or_none()
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver account not found or inactive")

    if sender.id == receiver.id:
        raise HTTPException(status_code=400, detail="Cannot transfer to the same account")

    total_debit = amount_paisa + TRANSFER_FEE_PAISA
    if not sender.can_debit(total_debit):
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient funds. Available: Rs. {sender.balance_npr:.2f}",
        )

    # Check daily limit
    if total_debit > sender.daily_transfer_limit_paisa:
        raise HTTPException(
            status_code=400,
            detail=f"Amount exceeds daily transfer limit of Rs. {sender.daily_transfer_limit_paisa / 100:.2f}",
        )

    # ─── Atomic transfer ─────────────────────────────────────────────────────
    sender.balance_paisa -= total_debit
    receiver.balance_paisa += amount_paisa

    txn = Transaction(
        id=str(uuid.uuid4()),
        reference=generate_transaction_ref(),
        sender_account_id=sender.id,
        receiver_account_id=receiver.id,
        transaction_type=TransactionType.TRANSFER,
        status=TransactionStatus.COMPLETED,
        amount_paisa=amount_paisa,
        fee_paisa=TRANSFER_FEE_PAISA,
        description=body.description,
        sender_balance_after_paisa=sender.balance_paisa,
        receiver_balance_after_paisa=receiver.balance_paisa,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        completed_at=datetime.now(timezone.utc),
    )
    db.add(txn)
    _audit(
        db, current_user.id, "TRANSFER",
        f"Transferred Rs. {body.amount_npr} to {body.receiver_account_number}",
        request, entity_id=txn.id,
    )

    await db.commit()
    await db.refresh(txn)
    return txn


@router.post("/deposit", response_model=TransactionResponse)
async def deposit(
    body: DepositRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),  # Only admins/tellers can deposit
):
    """Deposit funds into an account (teller/admin operation)."""
    amount_paisa = int(body.amount_npr * 100)

    result = await db.execute(select(Account).where(Account.id == body.account_id))
    account = result.scalar_one_or_none()
    if not account or account.status != AccountStatus.ACTIVE:
        raise HTTPException(status_code=404, detail="Account not found or inactive")

    account.balance_paisa += amount_paisa

    txn = Transaction(
        id=str(uuid.uuid4()),
        reference=generate_transaction_ref(),
        receiver_account_id=account.id,
        transaction_type=TransactionType.DEPOSIT,
        status=TransactionStatus.COMPLETED,
        amount_paisa=amount_paisa,
        description=body.description or "Cash deposit",
        receiver_balance_after_paisa=account.balance_paisa,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)
    return txn


@router.get("", response_model=list[TransactionResponse])
async def list_transactions(
    account_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List transactions for the current user's accounts."""
    # Get user's account IDs
    acc_result = await db.execute(
        select(Account.id).where(Account.user_id == current_user.id)
    )
    user_account_ids = [r for r in acc_result.scalars().all()]

    if account_id and account_id not in user_account_ids:
        raise HTTPException(status_code=403, detail="Not your account")

    ids_to_query = [account_id] if account_id else user_account_ids

    from sqlalchemy import or_
    result = await db.execute(
        select(Transaction)
        .where(
            or_(
                Transaction.sender_account_id.in_(ids_to_query),
                Transaction.receiver_account_id.in_(ids_to_query),
            )
        )
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Verify ownership
    acc_result = await db.execute(
        select(Account.id).where(Account.user_id == current_user.id)
    )
    user_acc_ids = set(acc_result.scalars().all())
    if txn.sender_account_id not in user_acc_ids and txn.receiver_account_id not in user_acc_ids:
        raise HTTPException(status_code=403, detail="Access denied")

    return txn

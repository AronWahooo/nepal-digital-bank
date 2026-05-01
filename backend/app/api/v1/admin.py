from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.loan import Loan, LoanStatus
from app.models.audit_log import AuditLog
from app.api.v1.deps import require_admin

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard")
async def admin_dashboard(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Bank-wide statistics for admin dashboard."""
    total_users = (await db.execute(select(func.count(User.id)))).scalar()
    total_accounts = (await db.execute(select(func.count(Account.id)))).scalar()
    total_transactions = (await db.execute(select(func.count(Transaction.id)))).scalar()
    total_deposits_paisa = (
        await db.execute(select(func.sum(Account.balance_paisa)))
    ).scalar() or 0
    pending_loans = (
        await db.execute(
            select(func.count(Loan.id)).where(Loan.status == LoanStatus.PENDING)
        )
    ).scalar()

    return {
        "total_users": total_users,
        "total_accounts": total_accounts,
        "total_transactions": total_transactions,
        "total_deposits_npr": total_deposits_paisa / 100,
        "pending_loans": pending_loans,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/users")
async def list_users(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "phone": u.phone,
            "role": u.role,
            "is_active": u.is_active,
            "is_kyc_verified": u.is_kyc_verified,
            "mfa_enabled": u.mfa_enabled,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.post("/users/{user_id}/kyc-verify")
async def verify_kyc(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_kyc_verified = True
    return {"message": f"KYC verified for {user.full_name}"}


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Cannot suspend an admin")
    user.is_active = False
    return {"message": f"User {user.full_name} suspended"}


@router.get("/audit-logs")
async def get_audit_logs(
    limit: int = 100,
    offset: int = 0,
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    result = await db.execute(query)
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "action": l.action,
            "description": l.description,
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]

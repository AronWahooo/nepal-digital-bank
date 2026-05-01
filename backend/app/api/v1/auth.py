from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import uuid

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password, validate_password_strength,
    create_access_token, create_refresh_token, decode_token,
    generate_totp_secret, verify_totp, get_totp_qr_code,
    generate_otp, send_sms_otp,
)
from app.core.redis_client import (
    check_login_attempts, increment_login_attempts, clear_login_attempts,
    store_otp, verify_otp_from_store, store_mfa_session, verify_mfa_session,
)
from app.models.user import User, UserRole
from app.models.audit_log import AuditLog
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse,
    VerifyOTPRequest, VerifyTOTPRequest, EnableMFAResponse,
    RefreshRequest, ChangePasswordRequest,
)
from app.api.v1.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


def audit(db, user_id, action, description, request: Request, entity_id=None):
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


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Check password strength
    ok, msg = validate_password_strength(body.password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Check phone uniqueness
    existing_phone = await db.execute(select(User).where(User.phone == body.phone))
    if existing_phone.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Phone number already registered")

    user = User(
        id=str(uuid.uuid4()),
        full_name=body.full_name,
        email=body.email,
        phone=body.phone,
        hashed_password=hash_password(body.password),
        role=UserRole.CUSTOMER,
    )
    db.add(user)

    # Send phone verification OTP
    otp = generate_otp()
    await store_otp(body.phone, otp)
    send_sms_otp(body.phone, otp)

    audit(db, user.id, "REGISTER", f"New user registered: {body.email}", request)
    await db.commit()

    return {
        "message": "Registration successful. Please verify your phone number.",
        "user_id": user.id,
        "requires_phone_verification": True,
    }


@router.post("/verify-phone")
async def verify_phone(
    body: VerifyOTPRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == body.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    valid = await verify_otp_from_store(user.phone, body.otp)
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    user.phone_verified = True
    audit(db, user.id, "PHONE_VERIFIED", "Phone number verified", request)
    return {"message": "Phone verified successfully"}


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else "unknown"

    # Rate limiting
    is_locked, remaining = await check_login_attempts(ip)
    if is_locked:
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Account locked for 15 minutes.",
        )

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        await increment_login_attempts(ip)
        raise HTTPException(status_code=401, detail=f"Invalid credentials. {remaining - 1} attempts remaining.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account suspended. Contact support.")

    await clear_login_attempts(ip)

    # If MFA enabled → require OTP step
    if user.mfa_enabled:
        # Send SMS OTP
        otp = generate_otp()
        await store_otp(user.phone, otp)
        send_sms_otp(user.phone, otp)
        await store_mfa_session(user.id)

        audit(db, user.id, "LOGIN_MFA_REQUIRED", "Login step 1 passed, MFA required", request)
        return {
            "mfa_required": True,
            "user_id": user.id,
            "message": "OTP sent to your registered phone number",
        }

    # No MFA — issue tokens directly
    user.last_login = datetime.now(timezone.utc)
    access = create_access_token({"sub": user.id, "role": user.role})
    refresh = create_refresh_token({"sub": user.id})

    audit(db, user.id, "LOGIN_SUCCESS", "Successful login", request)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user_id=user.id,
        full_name=user.full_name,
        role=user.role,
    )


@router.post("/verify-mfa-otp", response_model=TokenResponse)
async def verify_mfa_otp(
    body: VerifyOTPRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Step 2 of MFA login: verify SMS OTP."""
    result = await db.execute(select(User).where(User.id == body.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate MFA session still active
    if not await verify_mfa_session(user.id):
        raise HTTPException(status_code=400, detail="MFA session expired. Please login again.")

    valid = await verify_otp_from_store(user.phone, body.otp)
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    user.last_login = datetime.now(timezone.utc)
    access = create_access_token({"sub": user.id, "role": user.role})
    refresh = create_refresh_token({"sub": user.id})

    audit(db, user.id, "LOGIN_MFA_SUCCESS", "MFA login successful", request)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user_id=user.id,
        full_name=user.full_name,
        role=user.role,
    )


@router.post("/enable-totp", response_model=EnableMFAResponse)
async def enable_totp(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate TOTP secret and QR code for Google Authenticator setup."""
    secret = generate_totp_secret()
    current_user.totp_secret = secret
    await db.commit()

    qr = get_totp_qr_code(secret, current_user.email)
    return EnableMFAResponse(
        totp_secret=secret,
        qr_code_base64=qr,
        message="Scan this QR code with Google Authenticator, then call /confirm-totp",
    )


@router.post("/confirm-totp")
async def confirm_totp(
    body: VerifyTOTPRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Confirm TOTP setup and enable MFA."""
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="TOTP not set up yet")

    if not verify_totp(current_user.totp_secret, body.totp_code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    current_user.mfa_enabled = True
    await db.commit()
    return {"message": "MFA enabled successfully"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = decode_token(body.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    access = create_access_token({"sub": user.id, "role": user.role})
    new_refresh = create_refresh_token({"sub": user.id})

    return TokenResponse(
        access_token=access,
        refresh_token=new_refresh,
        user_id=user.id,
        full_name=user.full_name,
        role=user.role,
    )


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    ok, msg = validate_password_strength(body.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    current_user.hashed_password = hash_password(body.new_password)
    audit(db, current_user.id, "PASSWORD_CHANGED", "Password changed", request)
    return {"message": "Password changed successfully"}

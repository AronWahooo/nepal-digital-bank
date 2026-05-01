from datetime import datetime, timedelta, timezone
from typing import Optional
import pyotp
import qrcode
import io
import base64
import secrets
import requests

from passlib.context import CryptContext
from jose import jwt, JWTError
from cryptography.fernet import Fernet

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
fernet = Fernet(settings.ENCRYPTION_KEY.encode())


# ─── Password ────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Enforce strong password rules for banking."""
    if len(password) < 10:
        return False, "Password must be at least 10 characters"
    if not any(c.isupper() for c in password):
        return False, "Password must contain an uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain a lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain a digit"
    if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password):
        return False, "Password must contain a special character"
    return True, "OK"


# ─── JWT Tokens ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise ValueError("Invalid or expired token")


# ─── TOTP / MFA ───────────────────────────────────────────────────────────────

def generate_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(secret: str, token: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(token, valid_window=1)


def get_totp_qr_code(secret: str, email: str) -> str:
    """Return base64 PNG of QR code for Google Authenticator."""
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=email, issuer_name="Nepal Digital Bank")
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ─── SMS OTP (Sparrow SMS — Nepal) ───────────────────────────────────────────

def generate_otp(length: int = 6) -> str:
    return "".join([str(secrets.randbelow(10)) for _ in range(length)])


def send_sms_otp(phone: str, otp: str) -> bool:
    """Send OTP via Sparrow SMS (Nepal's top SMS gateway)."""
    if not settings.SPARROW_SMS_TOKEN:
        print(f"[DEV] SMS OTP for {phone}: {otp}")
        return True
    try:
        resp = requests.post(
            settings.SPARROW_SMS_URL,
            json={
                "token": settings.SPARROW_SMS_TOKEN,
                "from": settings.SPARROW_SMS_FROM,
                "to": phone,
                "text": f"Your Nepal Digital Bank OTP is: {otp}. Valid for 5 minutes. Do not share.",
            },
            timeout=10,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"SMS send failed: {e}")
        return False


# ─── AES-256 Field Encryption (for card numbers, PAN) ────────────────────────

def encrypt_field(value: str) -> str:
    return fernet.encrypt(value.encode()).decode()


def decrypt_field(encrypted: str) -> str:
    return fernet.decrypt(encrypted.encode()).decode()


# ─── Account Number Generator ────────────────────────────────────────────────

def generate_account_number() -> str:
    """Generate a 16-digit account number (Nepal bank format)."""
    prefix = "NDB"
    number = "".join([str(secrets.randbelow(10)) for _ in range(13)])
    return f"{prefix}{number}"


def generate_transaction_ref() -> str:
    return f"TXN{secrets.token_hex(8).upper()}"

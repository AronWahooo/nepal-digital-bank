from pydantic import BaseModel, EmailStr, field_validator
import re


class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    password: str

    @field_validator("phone")
    @classmethod
    def validate_nepal_phone(cls, v: str) -> str:
        # Nepal phone: 98XXXXXXXX or +977-98XXXXXXXX
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if cleaned.startswith("+977"):
            cleaned = cleaned[4:]
        if not re.match(r"^9[78]\d{8}$", cleaned):
            raise ValueError("Invalid Nepal phone number (e.g., 9841234567)")
        return cleaned

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v.strip()) < 3:
            raise ValueError("Full name must be at least 3 characters")
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyOTPRequest(BaseModel):
    user_id: str
    otp: str


class VerifyTOTPRequest(BaseModel):
    user_id: str
    totp_code: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    full_name: str
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class EnableMFAResponse(BaseModel):
    totp_secret: str
    qr_code_base64: str
    message: str


class SendOTPRequest(BaseModel):
    phone: str

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Nepal Digital Bank"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Database
    DATABASE_URL: str  # postgresql+asyncpg://user:pass@host/dbname

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Security
    SECRET_KEY: str  # openssl rand -hex 32
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Encryption key for sensitive fields (Fernet)
    ENCRYPTION_KEY: str  # Fernet.generate_key().decode()

    # Sparrow SMS (Nepal)
    SPARROW_SMS_TOKEN: str = ""
    SPARROW_SMS_FROM: str = "NepalBank"
    SPARROW_SMS_URL: str = "https://api.sparrowsms.com/v2/sms/"

    # Rate limiting
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15

    # CORS — set your frontend domain
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    # Admin
    ADMIN_EMAIL: str = "admin@nepalbank.com"
    ADMIN_PASSWORD: str = "ChangeMe123!"  # Override via env var

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

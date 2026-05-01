import redis.asyncio as aioredis
from app.core.config import settings

_redis_client = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


# ─── OTP Storage ─────────────────────────────────────────────────────────────

OTP_TTL = 300  # 5 minutes


async def store_otp(phone: str, otp: str):
    r = await get_redis()
    await r.setex(f"otp:{phone}", OTP_TTL, otp)


async def verify_otp_from_store(phone: str, otp: str) -> bool:
    r = await get_redis()
    stored = await r.get(f"otp:{phone}")
    if stored and stored == otp:
        await r.delete(f"otp:{phone}")
        return True
    return False


# ─── Login Rate Limiting ──────────────────────────────────────────────────────

async def check_login_attempts(identifier: str) -> tuple[bool, int]:
    """Returns (is_locked, attempts_remaining)."""
    from app.core.config import settings
    r = await get_redis()
    key = f"login_attempts:{identifier}"
    attempts = await r.get(key)
    attempts = int(attempts) if attempts else 0
    if attempts >= settings.MAX_LOGIN_ATTEMPTS:
        return True, 0
    return False, settings.MAX_LOGIN_ATTEMPTS - attempts


async def increment_login_attempts(identifier: str):
    from app.core.config import settings
    r = await get_redis()
    key = f"login_attempts:{identifier}"
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, settings.LOCKOUT_MINUTES * 60)
    await pipe.execute()


async def clear_login_attempts(identifier: str):
    r = await get_redis()
    await r.delete(f"login_attempts:{identifier}")


# ─── Refresh Token Blocklist ──────────────────────────────────────────────────

async def blacklist_token(jti: str, ttl: int = 60 * 60 * 24 * 8):
    r = await get_redis()
    await r.setex(f"blacklist:{jti}", ttl, "1")


async def is_token_blacklisted(jti: str) -> bool:
    r = await get_redis()
    return bool(await r.get(f"blacklist:{jti}"))


# ─── Session / MFA State ─────────────────────────────────────────────────────

async def store_mfa_session(user_id: str, ttl: int = 300):
    """Store a pending MFA state (login step 1 passed, awaiting OTP)."""
    r = await get_redis()
    await r.setex(f"mfa_pending:{user_id}", ttl, "1")


async def verify_mfa_session(user_id: str) -> bool:
    r = await get_redis()
    exists = await r.get(f"mfa_pending:{user_id}")
    if exists:
        await r.delete(f"mfa_pending:{user_id}")
        return True
    return False

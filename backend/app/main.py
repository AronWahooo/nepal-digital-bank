from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time

from app.core.config import settings
from app.core.database import init_db
from app.api.v1 import auth, accounts, transactions, loans, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"🏦 {settings.APP_NAME} starting up...")
    await init_db()
    print("✅ Database initialized")
    yield
    # Shutdown
    print("🔴 Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## Nepal Digital Bank API

A production-grade digital banking backend built for Nepal.

### Features
- 🔐 JWT authentication with MFA (TOTP + SMS OTP via Sparrow SMS)
- 🏦 Multi-account management (savings, current, FD)
- 💸 Atomic fund transfers with full audit trail
- 🏗️ Loan management (apply, approve, disburse)
- 📊 Admin dashboard with bank-wide statistics
- 🔒 AES-256 field encryption, bcrypt passwords, rate limiting

### Security
All endpoints except `/auth/register` and `/auth/login` require a Bearer token.
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── CORS ────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

# ─── Request timing middleware ────────────────────────────────────────────────

@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{(time.time() - start) * 1000:.1f}ms"
    return response


# ─── Global error handler ─────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # In production, don't expose internal errors
    if settings.DEBUG:
        raise exc
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."},
    )


# ─── Routers ─────────────────────────────────────────────────────────────────

app.include_router(auth.router, prefix="/api/v1")
app.include_router(accounts.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(loans.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


# ─── Health check (Render uses this) ─────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/", tags=["Health"])
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "docs": "/docs",
        "version": settings.APP_VERSION,
    }

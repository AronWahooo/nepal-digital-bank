# 🏦 Nepal Digital Bank

A production-grade digital banking backend built with FastAPI, PostgreSQL, Redis, and Docker — designed for Nepal.

## ✨ Features

| Feature | Details |
|---|---|
| Authentication | JWT access + refresh tokens, bcrypt (cost 12) |
| MFA | TOTP (Google Authenticator) + SMS OTP via Sparrow SMS |
| Accounts | Savings, current, fixed deposit (up to 3 per user) |
| Transfers | Atomic fund transfers with full audit trail |
| Loans | Application → approval → disbursement workflow |
| Security | AES-256 field encryption, rate limiting, audit logs |
| Admin | KYC verification, user management, bank-wide stats |
| Deploy | Render.com with PostgreSQL + Redis (free tier) |

## 🚀 Deploy to Render.com (5 minutes)

### Step 1: Push to GitHub
```bash
git init
git add .
git commit -m "Initial Nepal Digital Bank setup"
git remote add origin https://github.com/YOUR_USERNAME/nepal-digital-bank.git
git push -u origin main
```

### Step 2: Deploy on Render
1. Go to [render.com](https://render.com) → New → Blueprint
2. Connect your GitHub repo
3. Render reads `render.yaml` and creates:
   - Web service (FastAPI API)
   - PostgreSQL database
   - Redis instance
   - Static site (frontend)

### Step 3: Set Secret Environment Variables
In the Render dashboard, set these manually (they're marked `sync: false`):
- `SPARROW_SMS_TOKEN` — from [sparrowsms.com](https://sparrowsms.com)
- `ADMIN_PASSWORD` — strong password for admin account

### Step 4: Done! 🎉
Your API will be live at `https://nepal-digital-bank-api.onrender.com`
- API docs: `/docs`
- Health: `/health`

---

## 🐳 Run Locally with Docker

```bash
# 1. Generate an encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Copy this key

# 2. Set it in docker-compose.yml ENCRYPTION_KEY env var

# 3. Start everything
docker-compose up --build

# API: http://localhost:8000/docs
# Frontend: http://localhost:80
```

## 🔧 Local Dev (without Docker)

```bash
cd backend

# Create virtual env
python3.12 -m venv venv
source venv/bin/activate

# Install deps
pip install -r requirements.txt

# Copy and fill env vars
cp .env.example .env
# Edit .env with your values

# Run
uvicorn app.main:app --reload --port 8000
```

## 📋 API Endpoints

### Auth (`/api/v1/auth`)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/register` | Register new customer |
| POST | `/verify-phone` | Verify phone with SMS OTP |
| POST | `/login` | Login (returns tokens or triggers MFA) |
| POST | `/verify-mfa-otp` | Step 2 of MFA: verify SMS OTP |
| POST | `/enable-totp` | Set up Google Authenticator |
| POST | `/confirm-totp` | Confirm TOTP setup |
| POST | `/refresh` | Refresh access token |
| POST | `/change-password` | Change password |

### Accounts (`/api/v1/accounts`)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/accounts` | Create new account |
| GET | `/accounts` | List my accounts |
| GET | `/accounts/{id}` | Get account details |
| GET | `/accounts/{id}/balance` | Quick balance check |

### Transactions (`/api/v1/transactions`)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/transactions/transfer` | Transfer funds |
| POST | `/transactions/deposit` | Deposit (admin only) |
| GET | `/transactions` | List my transactions |
| GET | `/transactions/{id}` | Get transaction details |

### Loans (`/api/v1/loans`)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/loans/apply` | Apply for a loan |
| GET | `/loans` | List my loans |
| POST | `/loans/{id}/approve` | Approve loan (admin) |
| POST | `/loans/{id}/disburse` | Disburse loan (admin) |
| POST | `/loans/{id}/reject` | Reject loan (admin) |

### Admin (`/api/v1/admin`)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/admin/dashboard` | Bank statistics |
| GET | `/admin/users` | List all users |
| POST | `/admin/users/{id}/kyc-verify` | Approve KYC |
| POST | `/admin/users/{id}/suspend` | Suspend user |
| GET | `/admin/audit-logs` | View audit trail |

## 🔐 Security Architecture

```
Client → HTTPS (TLS 1.3) → Render Load Balancer → FastAPI
                                                      │
                                          ┌───────────┼────────────┐
                                          │           │            │
                                     Rate Limit   JWT Auth    Audit Log
                                     (Redis)      (Bearer)    (PostgreSQL)
                                          │           │
                                    bcrypt(12)   TOTP/OTP
                                                (Redis TTL)
```

- **Passwords**: bcrypt with cost factor 12
- **Tokens**: JWT HS256, 30min access / 7day refresh
- **MFA**: TOTP (Google Authenticator) + SMS OTP (Sparrow SMS)
- **Field encryption**: AES-256 (Fernet) for sensitive data
- **Rate limiting**: 5 failed logins → 15-min IP lockout
- **Audit**: Every login, transfer, and admin action is logged

## 🏗️ Tech Stack

- **FastAPI** 0.111 — async Python web framework
- **SQLAlchemy 2.0** — async ORM
- **Alembic** — database migrations
- **PostgreSQL 16** — ACID-compliant banking database
- **Redis 7** — OTP storage, rate limiting, sessions
- **Pydantic v2** — request/response validation
- **passlib + bcrypt** — password hashing
- **python-jose** — JWT tokens
- **pyotp** — TOTP/MFA
- **cryptography (Fernet)** — AES-256 field encryption
- **Docker + docker-compose** — containerized deployment

## 🤝 Contributing

1. Fork the repo
2. Create feature branch: `git checkout -b feature/my-feature`
3. Run tests: `pytest tests/ -v`
4. Submit PR to `main`

---

Built for Nepal 🇳🇵 — Powered by FastAPI

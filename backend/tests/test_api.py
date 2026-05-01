"""
Basic tests for Nepal Digital Bank API.
Run with: pytest tests/ -v
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_docs():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/docs")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_register_invalid_phone():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/register", json={
            "full_name": "Test User",
            "email": "test@example.com",
            "phone": "1234567890",  # Invalid Nepal phone
            "password": "Test@12345",
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_weak_password():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/register", json={
            "full_name": "Test User",
            "email": "test@example.com",
            "phone": "9841234567",
            "password": "weak",
        })
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_login_invalid_credentials():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "WrongPass123!",
        })
    assert resp.status_code == 401

import pytest


@pytest.mark.asyncio
async def test_register(client):
    resp = await client.post("/api/auth/register", json={"username": "testuser", "password": "password123", "display_name": "Test"})
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_register_duplicate(client):
    await client.post("/api/auth/register", json={"username": "dup", "password": "password123", "display_name": "Dup"})
    resp = await client.post("/api/auth/register", json={"username": "dup", "password": "password123", "display_name": "Dup"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login(client):
    await client.post("/api/auth/register", json={"username": "loginuser", "password": "password123", "display_name": "Login"})
    resp = await client.post("/api/auth/login", json={"username": "loginuser", "password": "password123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/auth/register", json={"username": "badpw", "password": "password123", "display_name": "Bad"})
    resp = await client.post("/api/auth/login", json={"username": "badpw", "password": "wrongpass"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh(client):
    reg = await client.post("/api/auth/register", json={"username": "refreshuser", "password": "password123", "display_name": "Refresh"})
    refresh_token = reg.json()["refresh_token"]

    resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()

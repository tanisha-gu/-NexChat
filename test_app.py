"""
NexChat Test Suite
Run with: pytest tests/ -v
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="function")
async def client():
    """Create a fresh test client with isolated database for each test."""
    from app.db.session import Base, get_db
    from app.main import app

    test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_db():
        async with TestSession() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


# ── Helpers ─────────────────────────────────────────────────────
async def register_and_login(client: AsyncClient, username: str, suffix: str = "") -> dict:
    """Register a user and return auth headers + user data."""
    await client.post("/api/v1/auth/register", json={
        "username": username,
        "email": f"{username}{suffix}@test.com",
        "password": "password123",
        "display_name": username.title(),
    })
    res = await client.post("/api/v1/auth/login", json={
        "username": username,
        "password": "password123",
    })
    data = res.json()
    return {
        "token": data["access_token"],
        "user": data["user"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
    }


# ── Auth Tests ───────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_register_success(client):
    res = await client.post("/api/v1/auth/register", json={
        "username": "alice",
        "email": "alice@test.com",
        "password": "password123",
        "display_name": "Alice",
    })
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["user"]["username"] == "alice"


@pytest.mark.asyncio
async def test_register_duplicate_username(client):
    body = {"username": "bob", "email": "bob@test.com", "password": "pass123", "display_name": "Bob"}
    await client.post("/api/v1/auth/register", json=body)
    res = await client.post("/api/v1/auth/register", json={**body, "email": "bob2@test.com"})
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post("/api/v1/auth/register", json={
        "username": "carol", "email": "carol@test.com",
        "password": "pass123", "display_name": "Carol",
    })
    res = await client.post("/api/v1/auth/login", json={"username": "carol", "password": "pass123"})
    assert res.status_code == 200
    assert "access_token" in res.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/register", json={
        "username": "dave", "email": "dave@test.com",
        "password": "correctpass", "display_name": "Dave",
    })
    res = await client.post("/api/v1/auth/login", json={"username": "dave", "password": "wrongpass"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client):
    auth = await register_and_login(client, "eve")
    res = await client.get("/api/v1/auth/me", headers=auth["headers"])
    assert res.status_code == 200
    assert res.json()["username"] == "eve"


@pytest.mark.asyncio
async def test_me_unauthorized(client):
    res = await client.get("/api/v1/auth/me")
    assert res.status_code in (401, 403)  # Missing bearer token


# ── Room Tests ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_create_direct_room(client):
    alice = await register_and_login(client, "alice2", "a")
    bob = await register_and_login(client, "bob2", "b")

    res = await client.post("/api/v1/rooms/direct",
        json={"target_user_id": bob["user"]["id"]},
        headers=alice["headers"],
    )
    assert res.status_code == 201
    assert res.json()["room_type"] == "direct"


@pytest.mark.asyncio
async def test_direct_room_idempotent(client):
    """Creating the same direct room twice should return the existing one."""
    alice = await register_and_login(client, "alice3", "a3")
    bob = await register_and_login(client, "bob3", "b3")

    r1 = await client.post("/api/v1/rooms/direct",
        json={"target_user_id": bob["user"]["id"]},
        headers=alice["headers"],
    )
    r2 = await client.post("/api/v1/rooms/direct",
        json={"target_user_id": bob["user"]["id"]},
        headers=alice["headers"],
    )
    assert r1.json()["id"] == r2.json()["id"]


@pytest.mark.asyncio
async def test_create_group_room(client):
    alice = await register_and_login(client, "alice4", "a4")
    res = await client.post("/api/v1/rooms/group",
        json={"name": "Test Group", "member_ids": []},
        headers=alice["headers"],
    )
    assert res.status_code == 201
    assert res.json()["room_type"] == "group"
    assert res.json()["name"] == "Test Group"


@pytest.mark.asyncio
async def test_list_rooms(client):
    alice = await register_and_login(client, "alice5", "a5")
    bob = await register_and_login(client, "bob5", "b5")
    await client.post("/api/v1/rooms/direct",
        json={"target_user_id": bob["user"]["id"]},
        headers=alice["headers"],
    )
    res = await client.get("/api/v1/rooms/", headers=alice["headers"])
    assert res.status_code == 200
    assert len(res.json()) >= 1


# ── Message Tests (via REST fallback) ─────────────────────────────
@pytest.mark.asyncio
async def test_get_messages_requires_membership(client):
    alice = await register_and_login(client, "alice6", "a6")
    bob = await register_and_login(client, "bob6", "b6")
    eve = await register_and_login(client, "eve6", "e6")

    room = await client.post("/api/v1/rooms/direct",
        json={"target_user_id": bob["user"]["id"]},
        headers=alice["headers"],
    )
    room_id = room.json()["id"]

    # Eve is not a member — should get 403
    res = await client.get(f"/api/v1/rooms/{room_id}/messages", headers=eve["headers"])
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_get_messages_pagination(client):
    alice = await register_and_login(client, "alice7", "a7")
    bob = await register_and_login(client, "bob7", "b7")

    room = await client.post("/api/v1/rooms/direct",
        json={"target_user_id": bob["user"]["id"]},
        headers=alice["headers"],
    )
    room_id = room.json()["id"]

    res = await client.get(
        f"/api/v1/rooms/{room_id}/messages?page=1&page_size=10",
        headers=alice["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert "messages" in data
    assert "total" in data
    assert "has_more" in data


# ── User Search Tests ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_search_users(client):
    alice = await register_and_login(client, "searchalice", "sa")
    await register_and_login(client, "searchbob", "sb")

    res = await client.get("/api/v1/users/search?q=searchb", headers=alice["headers"])
    assert res.status_code == 200
    usernames = [u["username"] for u in res.json()]
    assert "searchbob" in usernames
    assert "searchalice" not in usernames  # excluded self


@pytest.mark.asyncio
async def test_health_check(client):
    res = await client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

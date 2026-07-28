import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text

from app.database import get_db
from app.main import app
from app.models import Base

TEST_DB_URL = "postgresql+asyncpg://messenger:messenger@localhost:5434/messenger_test"
SYNC_DB_URL = "postgresql+psycopg2://messenger:messenger@localhost:5434/messenger_test"

sync_engine = create_engine(SYNC_DB_URL, pool_pre_ping=True)


def reset_tables():
    with sync_engine.begin() as conn:
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        Base.metadata.drop_all(conn)
        Base.metadata.create_all(conn)


@pytest_asyncio.fixture
async def client():
    reset_tables()
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    async_engine = create_async_engine(TEST_DB_URL)
    session_local = async_sessionmaker(async_engine, expire_on_commit=False)
    async with session_local() as session:
        async def override_get_db():
            yield session

        app.dependency_overrides[get_db] = override_get_db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
        app.dependency_overrides.clear()
    await async_engine.dispose()

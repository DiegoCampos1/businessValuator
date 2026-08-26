import os
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

_tmpdir = tempfile.mkdtemp(prefix="bv-test-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{Path(_tmpdir) / 'test.db'}"
os.environ["MASTER_KEY"] = Fernet.generate_key().decode()
os.environ["JWT_SECRET"] = "test-secret"
os.environ["TAVILY_API_KEY"] = "test-tavily-key"
os.environ["GOOGLE_CLIENT_ID"] = "test-client.apps.googleusercontent.com"

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import Base, async_session_factory, engine
from app.core.security import create_access_token
from app.main import app
from app.models.question import Question
from app.models.sector import Sector
from app.models.user import User
from app.seed import SEED_QUESTIONS
from app.services.sector_mapper import B3_SECTORS


@pytest_asyncio.fixture(autouse=True)
async def _db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as s:
        for name, slug in B3_SECTORS:
            s.add(Sector(name=name, slug=slug))
        await s.commit()
        sectors = (await s.execute(select(Sector))).scalars().all()
        slug_to_id = {x.slug: x.id for x in sectors}
        for sector_slug, criteria, text in SEED_QUESTIONS:
            s.add(
                Question(
                    sector_id=slug_to_id.get(sector_slug) if sector_slug else None,
                    criteria=criteria,
                    text=text,
                    is_system=True,
                    user_id=None,
                )
            )
        await s.commit()
    yield


@pytest_asyncio.fixture
async def client(_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def user_token(_db):
    async with async_session_factory() as s:
        user = User(email="test@example.com", name="Test User", google_sub="12345")
        s.add(user)
        await s.commit()
        await s.refresh(user)
        uid = user.id
    return uid, create_access_token(uid, "test@example.com")

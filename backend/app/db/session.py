from collections.abc import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy ORM models."""


def _make_sync_url(url: str) -> str:
    if url.startswith("sqlite+aiosqlite"):
        return url.replace("sqlite+aiosqlite", "sqlite", 1)
    if url.startswith("postgresql+asyncpg"):
        return url.replace("postgresql+asyncpg", "postgresql+psycopg", 1)
    return url


# Ensure parent dir exists for SQLite local database
if settings.resolved_database_url.startswith("sqlite"):
    settings.resolved_storage_root.mkdir(parents=True, exist_ok=True)

async_engine = create_async_engine(settings.resolved_database_url, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# Synchronous engine for Celery workers & Alembic migrations
sync_engine = create_engine(_make_sync_url(settings.resolved_database_url), echo=False, future=True)
SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

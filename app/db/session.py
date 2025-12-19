"""Database session management."""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def _to_async_url(url: str) -> str:
    """Convert sync DB URL to async URL."""
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[13:]
    if url.startswith("sqlite://"):
        return "sqlite+aiosqlite://" + url[9:]
    return url


def _to_sync_url(url: str) -> str:
    """Convert async DB URL to sync URL."""
    if url.startswith("sqlite+aiosqlite://"):
        return "sqlite://" + url[19:]
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url[21:]
    return url


# Async engine/session (FastAPI)
async_engine = create_async_engine(_to_async_url(settings.DATABASE_URL), pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """Async DB session for FastAPI routes."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all database tables."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Sync engine/session (Temporal worker activities)
sync_engine = create_engine(_to_sync_url(settings.DATABASE_URL), pool_pre_ping=True)
SyncSessionLocal = sessionmaker(sync_engine, autocommit=False, autoflush=False)


@contextmanager
def get_sync_db():
    """Sync DB session for worker activities."""
    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

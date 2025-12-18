"""Database configuration and session management (sync + async)."""

from __future__ import annotations

from contextlib import contextmanager, asynccontextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

try:  # optional async deps
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
except ImportError:  # pragma: no cover - only when async extras missing
    AsyncSession = None
    async_sessionmaker = None
    create_async_engine = None

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


def _build_async_url(url: str) -> str:
    """Convert sync Postgres URL to asyncpg URL if needed."""
    prefix = "postgresql://"
    async_prefix = "postgresql+asyncpg://"
    if url.startswith(async_prefix):
        return url
    if url.startswith(prefix):
        return async_prefix + url[len(prefix) :]
    return url


# Sync engine/session (FastAPI routes, scripts)
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Async engine/session (background tasks needing async pooling)
if create_async_engine and async_sessionmaker and AsyncSession:
    async_engine = create_async_engine(_build_async_url(settings.DATABASE_URL), pool_pre_ping=True)
    AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False, autoflush=False, autocommit=False)
else:  # pragma: no cover - async extras not installed
    async_engine = None
    AsyncSessionLocal = None


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context manager: commit on success, rollback on exception, always close."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_dependency() -> Generator[Session, None, None]:
    """FastAPI dependency: yield session, ensure close (no auto-commit)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:  # pragma: no cover
    """Async context manager: commit on success, rollback on exception, always close."""
    if AsyncSessionLocal is None:
        raise RuntimeError("Async session not available; install async extras.")
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_async_db_dependency() -> AsyncGenerator[AsyncSession, None]:  # pragma: no cover
    """FastAPI async dependency: yield session, ensure close (no auto-commit)."""
    if AsyncSessionLocal is None:
        raise RuntimeError("Async session not available; install async extras.")
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def init_db() -> None:
    """Create all database tables (sync metadata)."""
    Base.metadata.create_all(bind=engine)

"""Async engine and session. The schema is Alembic's job -- no create_all() here."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .settings import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

# expire_on_commit=False is required, not a tuning choice: with it on, commit()
# marks every attribute stale, so the next read is a lazy load -- and under
# asyncio a lazy load raises MissingGreenlet instead of issuing a query.
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """One transaction, for scripts and anything outside a request."""
    session = SessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db() -> AsyncIterator[AsyncSession]:
    """One transaction per request, as a dependency: `Depends(get_db)`."""
    async with get_session() as session:
        yield session

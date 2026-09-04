"""Async engine and session, plus the dependency that hands one to a route.

The schema is Alembic's job: there is deliberately no `create_all()` anywhere.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .settings import settings

# create_async_engine, not create_engine -- and the URL is unchanged, because
# psycopg 3 is an async driver too. Swapping to asyncpg would mean editing the
# URL as well as this line.
engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

# expire_on_commit=False is not optional here. With it on, commit() marks every
# attribute stale and the next read is a lazy load -- which under asyncio is not
# a slow query, it is a MissingGreenlet exception.
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """For scripts and anything outside a request."""
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
    """One transaction per request, as a dependency: `Depends(get_db)`.

    An async generator dependency, so FastAPI awaits the teardown on the same
    event loop that ran the route.
    """
    async with get_session() as session:
        yield session

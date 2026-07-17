"""Generic async SQLAlchemy engine and session helpers.

No tables/models here — those belong to domain repositories in later EPICs.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(db_path: str) -> AsyncEngine:
    """Create an async SQLite engine for ``sqlite+aiosqlite:///{db_path}``."""
    return create_async_engine(f"sqlite+aiosqlite:///{db_path}")


async def get_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Yield an ``AsyncSession`` and always close it (try/finally)."""
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()

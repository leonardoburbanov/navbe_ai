"""Tests for ``navbe.core.database``."""

from navbe.core.database import create_engine, get_session


async def test_engine_creates_connection() -> None:
    """Engine can open a connection against an in-memory SQLite DB."""
    engine = create_engine(":memory:")
    async with engine.connect() as conn:
        await conn.close()
    await engine.dispose()


async def test_get_session_closes_on_exit() -> None:
    """Session is closed even if the async generator is only partially consumed."""
    engine = create_engine(":memory:")
    gen = get_session(engine)
    session = await gen.__anext__()

    closed = False
    original_close = session.close

    async def tracking_close() -> None:
        nonlocal closed
        closed = True
        await original_close()

    session.close = tracking_close  # type: ignore[method-assign]
    await gen.aclose()
    assert closed
    await engine.dispose()

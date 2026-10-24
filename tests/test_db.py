from unittest.mock import AsyncMock, patch
import pytest
import db

@pytest.mark.asyncio
async def test_init_db():
    with patch("db.asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool

        pool = await db.init_db()

        mock_create_pool.assert_called_once_with(db.DATABASE_URL, min_size=2, max_size=10)
        assert pool == mock_pool
        assert db.pool == mock_pool

@pytest.mark.asyncio
async def test_close_db():
    mock_pool = AsyncMock()
    db.pool = mock_pool

    await db.close_db()

    mock_pool.close.assert_called_once()
    assert db.pool is None

@pytest.mark.asyncio
async def test_close_db_no_pool():
    db.pool = None

    await db.close_db()

    assert db.pool is None

@pytest.mark.asyncio
async def test_get_db():
    mock_pool = AsyncMock()
    db.pool = mock_pool

    pool = await db.get_db()

    assert pool == mock_pool

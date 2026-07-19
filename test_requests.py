import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock
import db

# Import the endpoint function
from routers.requests import update_request

@pytest.mark.asyncio
async def test_update_request_not_found():
    # Mock db.pool
    db.pool = MagicMock()
    db.pool.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await update_request(999, {}, {"id": 1, "role": "observer"})
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Request not found"

@pytest.mark.asyncio
async def test_update_request_not_authorized():
    db.pool = MagicMock()
    # The request was created by user 2
    db.pool.fetchrow = AsyncMock(return_value={"id": 10, "created_by": 2})

    # User 1 (observer, not supervisor, not author) tries to update
    with pytest.raises(HTTPException) as exc_info:
        await update_request(10, {}, {"id": 1, "role": "observer"})
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Not authorized to update this request"

@pytest.mark.asyncio
async def test_update_request_invalid_priority():
    db.pool = MagicMock()
    db.pool.fetchrow = AsyncMock(return_value={"id": 10, "created_by": 1})
    db.pool.execute = AsyncMock()

    # Author tries to set invalid priority
    with pytest.raises(HTTPException) as exc_info:
        await update_request(10, {"priority": "super-high"}, {"id": 1, "role": "observer"})
    assert exc_info.value.status_code == 400
    assert "priority" in exc_info.value.detail

@pytest.mark.asyncio
async def test_update_request_invalid_status():
    db.pool = MagicMock()
    db.pool.fetchrow = AsyncMock(return_value={"id": 10, "created_by": 1})
    db.pool.execute = AsyncMock()

    # Author tries to set invalid status
    with pytest.raises(HTTPException) as exc_info:
        await update_request(10, {"status": "invalid_status_value"}, {"id": 1, "role": "observer"})
    assert exc_info.value.status_code == 400
    assert "status" in exc_info.value.detail

@pytest.mark.asyncio
async def test_update_request_non_supervisor_set_signed():
    db.pool = MagicMock()
    db.pool.fetchrow = AsyncMock(return_value={"id": 10, "created_by": 1})
    db.pool.execute = AsyncMock()

    # Author (non-supervisor) tries to set status to signed
    with pytest.raises(HTTPException) as exc_info:
        await update_request(10, {"status": "signed"}, {"id": 1, "role": "observer"})
    assert exc_info.value.status_code == 403
    assert "approve or reject" in exc_info.value.detail

@pytest.mark.asyncio
async def test_update_request_supervisor_authorized():
    db.pool = MagicMock()
    # Request created by user 2, but supervisor (user 1) is updating
    db.pool.fetchrow = AsyncMock(return_value={"id": 10, "created_by": 2})
    db.pool.execute = AsyncMock()

    res = await update_request(10, {"title": "New Title", "status": "signed"}, {"id": 1, "role": "supervisor"})
    assert res == {"ok": True}
    db.pool.execute.assert_called_once()

@pytest.mark.asyncio
async def test_update_request_author_authorized():
    db.pool = MagicMock()
    # Request created by user 1, author (user 1, observer) is updating to pending
    db.pool.fetchrow = AsyncMock(return_value={"id": 10, "created_by": 1})
    db.pool.execute = AsyncMock()

    res = await update_request(10, {"title": "New Title", "status": "pending"}, {"id": 1, "role": "observer"})
    assert res == {"ok": True}
    db.pool.execute.assert_called_once()

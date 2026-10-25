import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError
from unittest.mock import patch, AsyncMock

from auth import get_current_user


@pytest.mark.asyncio
async def test_get_current_user_no_credentials():
    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(credentials=None)
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Not authenticated"


@pytest.mark.asyncio
@patch("auth.jwt.decode")
async def test_get_current_user_invalid_token_type(mock_decode):
    mock_decode.return_value = {"type": "refresh", "sub": "1"}
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="dummy")

    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(credentials=credentials)

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Invalid token type"


@pytest.mark.asyncio
@patch("auth.jwt.decode")
async def test_get_current_user_missing_sub(mock_decode):
    mock_decode.return_value = {"type": "access"}
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="dummy")

    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(credentials=credentials)

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Invalid token"


@pytest.mark.asyncio
@patch("auth.jwt.decode")
async def test_get_current_user_jwt_error(mock_decode):
    mock_decode.side_effect = JWTError("Invalid token")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="dummy")

    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(credentials=credentials)

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Invalid token"


@pytest.mark.asyncio
@patch("auth.jwt.decode")
@patch("auth.db.pool")
async def test_get_current_user_not_found(mock_pool, mock_decode):
    mock_decode.return_value = {"type": "access", "sub": "1"}
    mock_fetchrow = AsyncMock(return_value=None)
    mock_pool.fetchrow = mock_fetchrow
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="dummy")

    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(credentials=credentials)

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "User not found"


@pytest.mark.asyncio
@patch("auth.jwt.decode")
@patch("auth.db.pool")
async def test_get_current_user_disabled(mock_pool, mock_decode):
    mock_decode.return_value = {"type": "access", "sub": "1"}
    mock_fetchrow = AsyncMock(return_value={"id": 1, "is_active": False})
    mock_pool.fetchrow = mock_fetchrow
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="dummy")

    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(credentials=credentials)

    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "User disabled"


@pytest.mark.asyncio
@patch("auth.jwt.decode")
@patch("auth.db.pool")
async def test_get_current_user_success(mock_pool, mock_decode):
    mock_decode.return_value = {"type": "access", "sub": "1"}
    user_data = {"id": 1, "username": "test_user", "full_name": "Test User", "role": "user", "is_active": True}
    mock_fetchrow = AsyncMock(return_value=user_data)
    mock_pool.fetchrow = mock_fetchrow
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="dummy")

    user = await get_current_user(credentials=credentials)

    assert user == user_data

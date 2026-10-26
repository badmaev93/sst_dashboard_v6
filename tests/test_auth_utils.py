from datetime import UTC, datetime

from jose import jwt

from auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from config import JWT_ALGORITHM, JWT_SECRET


def test_hash_password():
    password = "mysecretpassword"
    hashed = hash_password(password)
    assert hashed != password
    assert isinstance(hashed, str)
    assert len(hashed) > 0

def test_verify_password():
    password = "mysecretpassword"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False

def test_create_access_token():
    data = {"sub": "123", "role": "user"}
    token = create_access_token(data)

    assert isinstance(token, str)

    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

    assert payload["sub"] == "123"
    assert payload["role"] == "user"
    assert payload["type"] == "access"
    assert "exp" in payload

    exp_datetime = datetime.fromtimestamp(payload["exp"], tz=UTC)
    now_datetime = datetime.now(UTC)

    assert exp_datetime > now_datetime

def test_create_refresh_token():
    data = {"sub": "123", "role": "user"}
    token = create_refresh_token(data)

    assert isinstance(token, str)

    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

    assert payload["sub"] == "123"
    assert payload["role"] == "user"
    assert payload["type"] == "refresh"
    assert "exp" in payload

    exp_datetime = datetime.fromtimestamp(payload["exp"], tz=UTC)
    now_datetime = datetime.now(UTC)

    assert exp_datetime > now_datetime

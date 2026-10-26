"""Модуль JWT аутентификации."""
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

import db
from config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from models import UserLogin

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

auth_router = APIRouter(tags=["auth"])


def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["type"] = "access"
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode["type"] = "refresh"
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(401, "Not authenticated")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(401, "Invalid token type")
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(401, "Invalid token")
    except JWTError:
        raise HTTPException(401, "Invalid token")

    user = await db.pool.fetchrow("SELECT id, username, full_name, role, is_active FROM users WHERE id = $1", int(user_id))
    if not user:
        raise HTTPException(401, "User not found")
    if not user["is_active"]:
        raise HTTPException(403, "User disabled")
    return dict(user)


def require_role(*roles):
    async def dependency(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, f"Role {user['role']} not allowed")
        return user
    return dependency


@auth_router.post("/api/auth/login")
async def login(data: UserLogin):
    user = await db.pool.fetchrow(
        "SELECT id, username, full_name, role, password_hash, is_active FROM users WHERE username = $1",
        data.username)
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    if not user["is_active"]:
        raise HTTPException(403, "Account disabled")

    token_data = {"sub": str(user["id"]), "role": user["role"]}
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"],
        }
    }


@auth_router.post("/api/auth/refresh")
async def refresh(refresh_token: str):
    try:
        payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(401, "Not a refresh token")
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(401, "Invalid refresh token")

    user = await db.pool.fetchrow("SELECT id, role, is_active FROM users WHERE id = $1", int(user_id))
    if not user or not user["is_active"]:
        raise HTTPException(401, "User not found or disabled")

    token_data = {"sub": str(user["id"]), "role": user["role"]}
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer",
    }


@auth_router.get("/api/auth/me")
async def me(user=Depends(get_current_user)):
    return user

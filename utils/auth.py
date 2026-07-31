"""
Simple email/password authentication (JWT-based, no OAuth).

Unlike PDF-LEARNER, this project uses a plain Authorization: Bearer token
instead of an httpOnly cookie. That's a deliberate simplification — it
avoids the cross-domain cookie/SameSite headaches that come from having
the frontend and backend on different domains in production (Vercel +
Render), since a Bearer token sent explicitly in a header doesn't depend
on any cookie policy at all.

Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib only, no extra
dependency like bcrypt needed).
"""

import os
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Header, HTTPException, status
from dotenv import load_dotenv

from utils.memory import get_user_by_id

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

PBKDF2_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, hex_digest = stored_hash.split("$")
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return hmac.compare_digest(dk.hex(), hex_digest)


def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def get_current_user(authorization: str | None = Header(default=None)):
    """
    FastAPI dependency. Expects header: Authorization: Bearer <token>
    Raises 401 if missing/invalid.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = authorization.removeprefix("Bearer ").strip()
    user_id = decode_access_token(token)

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


def get_optional_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    user_id = decode_access_token(token)
    if not user_id:
        return None
    return get_user_by_id(user_id)

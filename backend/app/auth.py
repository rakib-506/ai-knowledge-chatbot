"""Authentication: password hashing, JWT tokens, and user/admin checks."""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from . import database as db
from .config import SECRET_KEY, TOKEN_EXPIRE_HOURS, ADMIN_USERNAME, ADMIN_PASSWORD
from .logger import log

ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ---------- passwords (PBKDF2, built into Python) ----------
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 200_000)
    return hmac.compare_digest(digest.hex(), digest_hex)


# ---------- tokens ----------
def create_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                          detail="Please log in again.",
                          headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise error
    user = db.get_user_by_name(payload.get("sub", ""))
    if user is None:
        raise error
    return {"id": user["id"], "username": user["username"], "role": user["role"]}


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only.")
    return user


def ensure_admin_exists():
    """Create the first admin account from .env if it does not exist."""
    if db.get_user_by_name(ADMIN_USERNAME) is None:
        db.create_user(ADMIN_USERNAME, hash_password(ADMIN_PASSWORD), role="admin")
        log.info(f"Created admin account '{ADMIN_USERNAME}'")

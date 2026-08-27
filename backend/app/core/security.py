"""
Security utilities — JWT, password hashing, and token verification.
Uses passlib[bcrypt] for hashing and python-jose for JWT.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    from jose import JWTError, jwt
    JOSE_AVAILABLE = True
except ImportError:
    JOSE_AVAILABLE = False

try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    PASSLIB_AVAILABLE = True
except ImportError:
    PASSLIB_AVAILABLE = False
    pwd_context = None

from backend.app.core.config import get_settings

settings = get_settings()


def hash_password(plain: str) -> str:
    if not PASSLIB_AVAILABLE:
        raise RuntimeError("passlib[bcrypt] not installed")
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    if not PASSLIB_AVAILABLE:
        return False
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    if not JOSE_AVAILABLE:
        raise RuntimeError("python-jose not installed")
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    if not JOSE_AVAILABLE:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None

"""
Security module for authentication, authorization, password hashing, and rate limiting.
Uses OWASP-compliant PBKDF2-HMAC-SHA256 with 100,000 iterations and PyJWT for signed tokens.
"""
import os
import time
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
import jwt
from backend.app.core.config import get_settings

settings = get_settings()

# Simple in-memory rate limiting tracker per IP
# Format: ip_address -> [(timestamp1), (timestamp2), ...]
_RATE_LIMIT_STORE: Dict[str, list] = {}


def hash_password(password: str) -> str:
    """Hashes password with random 16-byte salt using PBKDF2-HMAC-SHA256."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return salt.hex() + "$" + key.hex()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain password against stored PBKDF2 hash string."""
    try:
        if not hashed_password or "$" not in hashed_password:
            return False
        salt_hex, key_hex = hashed_password.split("$")
        salt = bytes.fromhex(salt_hex)
        key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, 100000)
        return key.hex() == key_hex
    except Exception:
        return False


def create_access_token(subject: str, role: str = "USER", expires_delta: Optional[timedelta] = None) -> str:
    """Creates signed JWT token containing subject user_id, role, and expiration timestamp."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    clean_role = "ADMIN" if str(role).upper() == "ADMIN" else "USER"
    payload = {
        "sub": str(subject),
        "role": clean_role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decodes JWT token and returns payload dictionary if valid and unexpired."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except Exception:
        return None


def check_rate_limit(ip_address: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
    """
    In-memory rate limiter for login/signup endpoints.
    Returns True if request is allowed, False if rate limit exceeded.
    Disabled during pytest testing runs.
    """
    import sys
    if "pytest" in sys.modules or settings.ENVIRONMENT == "testing":
        return True

    now = time.time()
    cutoff = now - window_seconds
    
    if ip_address not in _RATE_LIMIT_STORE:
        _RATE_LIMIT_STORE[ip_address] = [now]
        return True
    
    timestamps = [t for t in _RATE_LIMIT_STORE[ip_address] if t > cutoff]
    if len(timestamps) >= max_requests:
        _RATE_LIMIT_STORE[ip_address] = timestamps
        return False
    
    timestamps.append(now)
    _RATE_LIMIT_STORE[ip_address] = timestamps
    return True

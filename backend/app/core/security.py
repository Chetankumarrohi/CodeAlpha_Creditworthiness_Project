"""
Security module for authentication, authorization, password hashing, 2FA (TOTP / Email OTP),
recovery codes, QR generation, session tokens, and rate limiting.
Uses OWASP-compliant PBKDF2-HMAC-SHA256 with 100,000 iterations and PyJWT for signed tokens.
"""
import os
import io
import time
import base64
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Tuple
import jwt
import pyotp
import qrcode

from backend.app.core.config import get_settings

settings = get_settings()

# In-memory rate limiting & cooldown tracker
# Format: key -> [timestamps] or key -> timestamp
_RATE_LIMIT_STORE: Dict[str, list] = {}
_COOLDOWN_STORE: Dict[str, float] = {}


# ─── Password Hashing & Verification ──────────────────────────────────────────

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


# ─── Single-Use Numeric OTP (Email Verification / Email 2FA) ──────────────────

def generate_numeric_otp(length: int = 6) -> str:
    """Generates a cryptographically random numeric OTP."""
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(length))


def hash_otp_code(code: str) -> str:
    """Creates a deterministic SHA-256 hash of an OTP code for safe storage."""
    return hashlib.sha256((code.strip() + settings.SECRET_KEY[:16]).encode("utf-8")).hexdigest()


def verify_otp_code(plain_code: str, hashed_code: str) -> bool:
    """Verifies a plain OTP against its stored hash."""
    return hash_otp_code(plain_code) == hashed_code


# ─── Two-Factor Authentication (TOTP Authenticator App) ───────────────────────

def generate_totp_secret() -> str:
    """Generates a random Base32 TOTP secret for authenticator apps."""
    return pyotp.random_base32()


def get_totp_uri(secret: str, user_email: str, issuer_name: str = "Nova Credit AI") -> str:
    """Returns otpauth:// URI for authenticator applications."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=user_email, issuer_name=issuer_name)


def generate_qr_code_data_url(uri: str) -> str:
    """Generates a base64 PNG data URL of the TOTP QR code."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#090A0F", back_color="#FFFFFF")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    b64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"


def verify_totp_code(secret: str, code: str) -> bool:
    """Verifies a 6-digit TOTP code against the secret (allowing 1 interval tolerance = 30s)."""
    try:
        clean_code = str(code).strip().replace(" ", "")
        totp = pyotp.TOTP(secret)
        return bool(totp.verify(clean_code, valid_window=1))
    except Exception:
        return False


# ─── Single-Use 2FA Recovery Codes ────────────────────────────────────────────

def generate_recovery_codes(count: int = 8) -> Tuple[List[str], List[str]]:
    """
    Generates single-use recovery codes formatted as 'XXXX-XXXX'.
    Returns (plaintext_codes_for_user, hashed_codes_for_db).
    """
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    plain_codes = []
    hashed_codes = []
    for _ in range(count):
        part1 = "".join(secrets.choice(alphabet) for _ in range(4))
        part2 = "".join(secrets.choice(alphabet) for _ in range(4))
        code = f"{part1}-{part2}"
        plain_codes.append(code)
        hashed_codes.append(hash_otp_code(code.replace("-", "").upper()))
    return plain_codes, hashed_codes


def hash_recovery_code(code: str) -> str:
    """Hashes a recovery code for lookup in database."""
    clean = str(code).strip().replace("-", "").replace(" ", "").upper()
    return hash_otp_code(clean)


# ─── JWT Tokens & 2FA Challenge Tokens ────────────────────────────────────────

def create_access_token(
    subject: str,
    role: str = "USER",
    expires_delta: Optional[timedelta] = None,
    session_id: Optional[str] = None,
) -> str:
    """Creates signed JWT token containing subject user_id, role, and expiration timestamp."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    clean_role = "ADMIN" if str(role).upper() == "ADMIN" else "USER"
    payload = {
        "sub": str(subject),
        "role": clean_role,
        "scope": "access",
        "session_id": session_id or secrets.token_hex(16),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_2fa_challenge_token(subject: str, user_email: str, method: str = "totp") -> str:
    """Creates a short-lived (5-minute) intermediate token for 2FA verification."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    payload = {
        "sub": str(subject),
        "email": str(user_email),
        "scope": "2fa_challenge",
        "method": method,
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


def generate_session_token() -> str:
    """Generates a secure random session identifier."""
    return secrets.token_urlsafe(32)


# ─── Anti-Abuse, Rate Limiting & Cooldowns ─────────────────────────────────────

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


def check_action_cooldown(action_key: str, cooldown_seconds: int = 45) -> Tuple[bool, int]:
    """
    Checks if an action (e.g. resend OTP) is within cooldown period.
    Returns (can_proceed: bool, seconds_remaining: int).
    """
    import sys
    if "pytest" in sys.modules or settings.ENVIRONMENT == "testing":
        return True, 0

    now = time.time()
    last_time = _COOLDOWN_STORE.get(action_key, 0.0)
    elapsed = now - last_time
    if elapsed < cooldown_seconds:
        return False, int(cooldown_seconds - elapsed)
    _COOLDOWN_STORE[action_key] = now
    return True, 0


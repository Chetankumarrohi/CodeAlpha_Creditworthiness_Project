import uuid
import pyotp
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.app.database.session import (
    init_db, SessionLocal, UserRecord, get_user_by_email,
    get_active_email_challenge, create_user
)
from backend.app.core.security import hash_recovery_code, hash_otp_code

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield


def test_signup_requires_email_verification():
    """Verify signup creates unverified account with email challenge and requires OTP."""
    email = f"signup_{uuid.uuid4().hex[:6]}@example.com"
    res = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Password123!",
        "full_name": "New Applicant"
    })
    assert res.status_code == 201
    data = res.json()
    assert data["requires_verification"] is True
    assert data["email"] == email

    # User in DB must be unverified
    db = SessionLocal()
    user = get_user_by_email(db, email)
    assert user is not None
    assert user.email_verified is False

    # Challenge must be created
    challenge = get_active_email_challenge(db, email)
    assert challenge is not None
    assert challenge.attempts_left == 5
    db.close()


def test_email_verification_success():
    """Verify valid OTP activates user and issues valid access token."""
    email = f"verify_{uuid.uuid4().hex[:6]}@example.com"
    client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Password123!",
        "full_name": "Verify Me"
    })

    # Retrieve OTP directly from DB challenge (in real life delivered via email)
    db = SessionLocal()
    challenge = get_active_email_challenge(db, email)
    assert challenge is not None
    # We can check OTP hash verification
    # For testing, let's craft a known OTP
    from backend.app.database.session import create_email_verification_challenge
    known_otp = "123456"
    create_email_verification_challenge(db, challenge.user_id, email, hash_otp_code(known_otp))
    db.close()

    res_verify = client.post("/api/v1/auth/verify-email", json={
        "email": email,
        "code": known_otp
    })
    assert res_verify.status_code == 200
    vdata = res_verify.json()
    assert "access_token" in vdata
    assert vdata["email"] == email

    # User should now be marked email_verified
    db = SessionLocal()
    user = get_user_by_email(db, email)
    assert user.email_verified is True
    db.close()


def test_email_verification_invalid_otp_decrements_attempts():
    """Verify invalid OTP code is rejected and attempts are decremented."""
    email = f"wrong_otp_{uuid.uuid4().hex[:6]}@example.com"
    client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Password123!",
        "full_name": "Wrong OTP"
    })

    res = client.post("/api/v1/auth/verify-email", json={
        "email": email,
        "code": "000000"
    })
    assert res.status_code == 400
    assert "remaining" in res.json()["detail"].lower()


def test_resend_verification_code():
    """Verify resend endpoint dispatches a new challenge."""
    email = f"resend_{uuid.uuid4().hex[:6]}@example.com"
    client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Password123!",
        "full_name": "Resend Test"
    })

    res = client.post("/api/v1/auth/resend-verification", json={"email": email})
    assert res.status_code == 200
    assert "dispatched" in res.json()["message"].lower()


def test_two_factor_enrollment_and_login_challenge():
    """Verify full 2FA lifecycle: Setup -> Confirm -> Login challenge -> Verify TOTP."""
    email = f"twofa_{uuid.uuid4().hex[:6]}@example.com"
    password = "StrongPassword2026!"

    # 1. Register & verify user
    db = SessionLocal()
    user_id = "USR-" + uuid.uuid4().hex[:8].upper()
    create_user(db, user_id, email, password, "2FA User", role="USER", email_verified=True)
    db.close()

    # 2. Login to get authenticated token
    res_login1 = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res_login1.status_code == 200
    token1 = res_login1.json()["access_token"]
    headers = {"Authorization": f"Bearer {token1}"}

    # 3. Request 2FA Setup
    res_setup = client.post("/api/v1/auth/2fa/setup", headers=headers)
    assert res_setup.status_code == 200
    setup_data = res_setup.json()
    assert "secret" in setup_data
    assert "qr_code_data_url" in setup_data
    totp_secret = setup_data["secret"]

    # 4. Generate valid TOTP code and confirm 2FA
    current_totp = pyotp.TOTP(totp_secret).now()
    res_confirm = client.post("/api/v1/auth/2fa/confirm", json={"code": current_totp}, headers=headers)
    assert res_confirm.status_code == 200
    confirm_data = res_confirm.json()
    assert "recovery_codes" in confirm_data
    assert len(confirm_data["recovery_codes"]) == 8
    recovery_codes = confirm_data["recovery_codes"]

    # 5. Subsequent login must return 2FA challenge (requires_2fa: True)
    res_login2 = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res_login2.status_code == 200
    challenge_data = res_login2.json()
    assert challenge_data["requires_2fa"] is True
    assert "temp_token" in challenge_data
    temp_token = challenge_data["temp_token"]

    # 6. Verify 2FA challenge with invalid code -> Fail
    res_2fa_bad = client.post("/api/v1/auth/2fa/verify", json={
        "temp_token": temp_token,
        "code": "000000"
    })
    assert res_2fa_bad.status_code == 400

    # 7. Verify 2FA challenge with valid TOTP -> Success
    valid_code = pyotp.TOTP(totp_secret).now()
    res_2fa_ok = client.post("/api/v1/auth/2fa/verify", json={
        "temp_token": temp_token,
        "code": valid_code
    })
    assert res_2fa_ok.status_code == 200
    assert "access_token" in res_2fa_ok.json()

    # 8. Test Recovery Code Login
    res_login3 = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    temp_token3 = res_login3.json()["temp_token"]
    rec_code = recovery_codes[0]

    res_rec = client.post("/api/v1/auth/2fa/verify", json={
        "temp_token": temp_token3,
        "code": rec_code,
        "is_recovery_code": True
    })
    assert res_rec.status_code == 200
    assert "access_token" in res_rec.json()

    # Recovery code must be single-use: reusing same code must fail
    res_login4 = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    temp_token4 = res_login4.json()["temp_token"]
    res_rec_reuse = client.post("/api/v1/auth/2fa/verify", json={
        "temp_token": temp_token4,
        "code": rec_code,
        "is_recovery_code": True
    })
    assert res_rec_reuse.status_code == 400


def test_google_oauth_authenticate_and_link():
    """Verify Google OAuth creates account and links oauth provider."""
    google_email = f"google_user_{uuid.uuid4().hex[:6]}@gmail.com"
    payload = {
        "email": google_email,
        "full_name": "Google User Test",
        "provider_user_id": f"gsub-{uuid.uuid4().hex[:8]}"
    }
    res = client.post("/api/v1/auth/google", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["email"] == google_email
    assert data["role"] == "USER"


def test_session_management_and_remote_revocation():
    """Verify active sessions listing and revocation."""
    email = f"session_{uuid.uuid4().hex[:6]}@example.com"
    db = SessionLocal()
    create_user(db, "USR-" + uuid.uuid4().hex[:8].upper(), email, "Password123!", "Session Test", email_verified=True)
    db.close()

    res_login = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Check security settings
    res_sec = client.get("/api/v1/auth/security-settings", headers=headers)
    assert res_sec.status_code == 200
    sec_data = res_sec.json()
    assert len(sec_data["active_sessions"]) >= 1

    # Revoke session
    session_id = sec_data["active_sessions"][0]["id"]
    res_revoke = client.delete(f"/api/v1/auth/sessions/{session_id}", headers=headers)
    assert res_revoke.status_code == 200

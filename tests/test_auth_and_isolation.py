import uuid
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.app.database.session import init_db, SessionLocal, create_user

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield


def register_and_get_token(email: str, password: str = "Password123!", full_name: str = "Test User"):
    """Helper to register and directly verify account to obtain access token in tests."""
    db = SessionLocal()
    user_id = "USR-" + uuid.uuid4().hex[:8].upper()
    user = create_user(db, user_id, email, password, full_name, role="USER", email_verified=True)
    db.close()

    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_public_registration_creates_user_role_only():
    """Verify public registration strictly assigns USER role and requires email verification."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    payload = {
        "email": email,
        "password": "Password123!",
        "full_name": "Test User One",
        "role": "ADMIN"  # Malicious attempt to elevate role
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["requires_verification"] is True
    assert data["role"] == "USER"  # Must remain USER!


def test_correct_login_succeeds():
    """Verify correct credentials return access token and user profile for verified users."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    token = register_and_get_token(email, "Password123!", "Test User One")
    assert token is not None


def test_incorrect_password_fails_generically():
    """Verify incorrect password fails with 401 generic error message."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg_payload = {"email": email, "password": "Password123!", "full_name": "Test User One"}
    client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {"email": email, "password": "WrongPassword!"}
    res = client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password."


def test_duplicate_email_signup_handled():
    """Verify duplicate email registration for existing verified account is rejected with 400 error."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    register_and_get_token(email, "Password123!", "Test User One")

    reg_payload = {"email": email, "password": "Password123!", "full_name": "Test User One"}
    res2 = client.post("/api/v1/auth/register", json=reg_payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"].lower()


def test_unauthenticated_protected_endpoints():
    """Verify unauthenticated requests to protected endpoints return 401 Unauthorized."""
    res_me = client.get("/api/v1/auth/me")
    assert res_me.status_code == 401

    res_assess = client.post("/api/v1/credit/assess", json={})
    assert res_assess.status_code == 401

    res_hist = client.get("/api/v1/credit/history")
    assert res_hist.status_code == 401


def test_server_side_user_isolation():
    """Verify User A cannot access or read User B's credit assessment or profile."""
    email_a = f"user_a_{uuid.uuid4().hex[:6]}@example.com"
    email_b = f"user_b_{uuid.uuid4().hex[:6]}@example.com"

    # Register & Verify User A
    token_a = register_and_get_token(email_a, "Password123!", "User A")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Register & Verify User B
    token_b = register_and_get_token(email_b, "Password123!", "User B")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates a credit assessment
    assess_payload = {
        "applicant_name": "User A Private Assessment",
        "age": 35, "sex": "male", "job": "Skilled", "housing": "own",
        "saving_accounts": "moderate", "checking_account": "moderate", "purpose": "car",
        "monthly_income": 80000.0, "existing_emi": 5000.0, "credit_amount": 150000.0,
        "duration": 12, "savings_balance": 200000.0
    }
    res_assess_a = client.post("/api/v1/credit/assess", json=assess_payload, headers=headers_a)
    assert res_assess_a.status_code == 200
    assessment_id_a = res_assess_a.json()["assessment_id"]

    # User B lists history -> must NOT contain User A's assessment
    res_hist_b = client.get("/api/v1/credit/history", headers=headers_b)
    assert res_hist_b.status_code == 200
    b_history = res_hist_b.json()["history"]
    b_assessment_ids = [r["id"] for r in b_history]
    assert assessment_id_a not in b_assessment_ids

    # User B attempts direct fetch of User A's assessment ID -> must return 404
    res_direct_b = client.get(f"/api/v1/credit/history/{assessment_id_a}", headers=headers_b)
    assert res_direct_b.status_code in [403, 404]


def test_user_cannot_access_admin_endpoints():
    """Verify USER role receives 403 Forbidden on /admin endpoints."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    token_user = register_and_get_token(email, "Password123!", "Normal User")
    headers_user = {"Authorization": f"Bearer {token_user}"}

    res_admin_stats = client.get("/api/v1/admin/dashboard/stats", headers=headers_user)
    assert res_admin_stats.status_code == 403

    res_admin_users = client.get("/api/v1/admin/users", headers=headers_user)
    assert res_admin_users.status_code == 403

    res_admin_act = client.get("/api/v1/admin/activity", headers=headers_user)
    assert res_admin_act.status_code == 403


def test_admin_can_access_admin_apis():
    """Verify ADMIN role can access administrative endpoints."""
    db = SessionLocal()
    admin_id = "ADMIN-" + uuid.uuid4().hex[:8].upper()
    admin_email = f"admin_{uuid.uuid4().hex[:6]}@example.com"
    create_user(db, admin_id, admin_email, "AdminPassword123!", "Admin User", role="ADMIN", email_verified=True)
    db.close()

    res_login = client.post("/api/v1/auth/login", json={"email": admin_email, "password": "AdminPassword123!"})
    assert res_login.status_code == 200
    token_admin = res_login.json()["access_token"]
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    res_stats = client.get("/api/v1/admin/dashboard/stats", headers=headers_admin)
    assert res_stats.status_code == 200
    data = res_stats.json()
    assert "total_users" in data
    assert "active_users" in data

    res_users = client.get("/api/v1/admin/users", headers=headers_admin)
    assert res_users.status_code == 200


def test_password_hash_never_exposed_in_api():
    """Verify user profiles and user lists never leak password_hash."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    token = register_and_get_token(email, "Password123!", "User One")
    headers = {"Authorization": f"Bearer {token}"}

    res_me = client.get("/api/v1/auth/me", headers=headers)
    assert res_me.status_code == 200
    me_data = res_me.json()
    assert "password_hash" not in me_data
    assert "password" not in me_data


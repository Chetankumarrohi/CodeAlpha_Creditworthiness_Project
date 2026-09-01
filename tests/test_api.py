import uuid
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.app.database.session import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield


def test_api_health():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"


def test_api_assessment():
    from backend.app.database.session import SessionLocal, create_user
    email = f"test_api_{uuid.uuid4().hex[:6]}@example.com"
    db = SessionLocal()
    create_user(db, f"USR-{uuid.uuid4().hex[:8].upper()}", email, "Password123!", "API Tester", email_verified=True)
    db.close()

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "applicant_name": "Test User",
        "age": 30,
        "sex": "female",
        "job": "Skilled",
        "housing": "own",
        "saving_accounts": "rich",
        "checking_account": "moderate",
        "purpose": "car",
        "monthly_income": 80000.0,
        "existing_emi": 5000.0,
        "credit_amount": 150000.0,
        "duration": 12,
        "savings_balance": 200000.0
    }
    res = client.post("/api/v1/assess", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "nova_score" in data
    assert "decision_engine" in data
    assert "assessment_id" in data

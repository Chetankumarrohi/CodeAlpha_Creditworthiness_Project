import uuid
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_api_health():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"


def test_api_assessment():
    email = f"test_api_{uuid.uuid4().hex[:6]}@example.com"
    reg = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "full_name": "API Tester"})
    token = reg.json()["access_token"]
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

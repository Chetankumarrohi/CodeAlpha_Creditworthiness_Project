"""
Unit tests for Nova Loan Intelligence Module — domain services, calculations, edge cases, and REST APIs.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.app.services.emi_service import calculate_emi
from backend.app.services.amortization_service import generate_amortization_schedule
from backend.app.services.affordability_service import evaluate_affordability
from backend.app.services.tenure_optimizer_service import optimize_tenures
from backend.app.services.prepayment_service import simulate_prepayment
from backend.app.services.loan_comparison_service import compare_loan_offers

client = TestClient(app)

# ─── 1. EMI Service Unit Tests ───────────────────────────────────────────────

def test_emi_standard_reducing_balance():
    # Principal: ₹1,000,000, 10% p.a., 36 months
    res = calculate_emi(principal=1000000, annual_rate=10.0, tenure_months=36)
    assert res["monthly_emi"] == 32267.19
    assert res["net_principal"] == 1000000.0
    assert res["total_repayment"] > 1000000.0
    assert res["total_interest"] == round(res["total_repayment"] - 1000000.0, 2)
    assert res["interest_to_principal_ratio"] > 0

def test_emi_zero_percent_interest():
    res = calculate_emi(principal=120000, annual_rate=0.0, tenure_months=12)
    assert res["monthly_emi"] == 10000.0
    assert res["total_interest"] == 0.0
    assert res["total_repayment"] == 120000.0

def test_emi_down_payment_and_processing_fees():
    # Loan 500,000, Down Payment 100,000 => Net 400,000. Processing fee 2% = 8,000
    res = calculate_emi(
        principal=500000,
        annual_rate=12.0,
        tenure_months=24,
        down_payment=100000,
        processing_fee_val=2.0,
        processing_fee_type="percentage"
    )
    assert res["gross_loan_amount"] == 500000.0
    assert res["down_payment"] == 100000.0
    assert res["net_principal"] == 400000.0
    assert res["processing_fee"] == 8000.0
    assert res["effective_total_cost"] == pytest.approx(res["net_principal"] + res["total_interest"] + 8000.0 + 100000.0, 0.01)


# ─── 2. Amortization Service Unit Tests ──────────────────────────────────────

def test_amortization_schedule_zero_balance_closing():
    res = generate_amortization_schedule(principal=500000, annual_rate=9.5, tenure_months=24)
    monthly = res["monthly_schedule"]
    yearly = res["yearly_schedule"]
    
    assert len(monthly) == 24
    assert monthly[0]["month"] == 1
    assert monthly[0]["opening_balance"] == 500000.0
    assert monthly[-1]["closing_balance"] == 0.0  # Must zero out
    assert len(yearly) == 2


# ─── 3. Affordability Service Unit Tests ────────────────────────────────────

def test_affordability_comfortable_band():
    res = evaluate_affordability(monthly_income=100000, proposed_emi=20000, existing_emi=10000)
    assert res["existing_foir"] == 10.0
    assert res["new_foir"] == 30.0
    assert res["health_code"] == "COMFORTABLE"
    assert res["badge_color"] == "success"

def test_affordability_high_burden_band():
    res = evaluate_affordability(monthly_income=50000, proposed_emi=25000, existing_emi=10000)
    assert res["new_foir"] == 70.0
    assert res["health_code"] == "HIGH_BURDEN"
    assert res["badge_color"] == "danger"


# ─── 4. Tenure Optimizer Unit Tests ─────────────────────────────────────────

def test_tenure_optimizer_matrix_tags():
    res = optimize_tenures(
        principal=1000000,
        annual_rate=9.5,
        monthly_income=80000,
        existing_fixed_obligations=15000
    )
    scenarios = res["scenarios"]
    assert len(scenarios) >= 4
    
    # Verify presence of tags
    tags = [tag for s in scenarios for tag in s["tags"]]
    assert "Lowest Total Cost" in tags
    assert "Lowest EMI" in tags
    assert "Balanced Option" in tags


# ─── 5. Prepayment Service Unit Tests ────────────────────────────────────────

def test_prepayment_reduce_tenure():
    res = simulate_prepayment(
        principal=1000000,
        annual_rate=10.0,
        tenure_months=60,
        prepayment_amount=200000,
        prepayment_month=12,
        strategy="reduce_tenure"
    )
    assert res["months_saved"] > 0
    assert res["interest_saved"] > 0
    assert res["new_tenure_months"] < 60

def test_prepayment_extra_monthly_emi():
    res = simulate_prepayment(
        principal=1000000,
        annual_rate=10.0,
        tenure_months=60,
        extra_monthly_payment=2000
    )
    assert res["months_saved"] > 0
    assert res["interest_saved"] > 0


# ─── 6. Loan Comparison Unit Tests ──────────────────────────────────────────

def test_loan_comparison_offers():
    offers = [
        {"offer_name": "Bank A", "principal": 1000000, "annual_rate": 8.5, "tenure_months": 36, "processing_fee": 1.0},
        {"offer_name": "Bank B", "principal": 1000000, "annual_rate": 10.0, "tenure_months": 48, "processing_fee": 0.5},
        {"offer_name": "Fintech C", "principal": 1000000, "annual_rate": 9.0, "tenure_months": 36, "processing_fee": 0.0}
    ]
    res = compare_loan_offers(offers=offers, monthly_income=75000)
    eval_offers = res["offers"]
    assert len(eval_offers) == 3
    assert res["highlights"]["lowest_interest_offer"] is not None


# ─── 7. REST API & User Isolation Tests ─────────────────────────────────────

def get_auth_token(email="loan_test@nova.ai"):
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "TestPassword123!",
        "full_name": "Loan Intelligence Tester"
    })
    if reg_resp.status_code == 200:
        return reg_resp.json()["access_token"]
    login_resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "TestPassword123!"
    })
    return login_resp.json()["access_token"]

def test_api_loan_calculate():
    token = get_auth_token("calc_user@nova.ai")
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post("/api/v1/loans/calculate", headers=headers, json={
        "principal": 1200000,
        "annual_rate": 9.5,
        "tenure_months": 48,
        "processing_fee_val": 1.5
    })
    assert res.status_code == 200
    data = res.json()
    assert "monthly_emi" in data
    assert "schedule" in data
    assert "nova_insight" in data

def test_api_scenario_crud_and_isolation():
    token1 = get_auth_token("user1_scen@nova.ai")
    token2 = get_auth_token("user2_scen@nova.ai")
    
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    # Save scenario as User 1
    create_res = client.post("/api/v1/loans/scenarios", headers=headers1, json={
        "scenario_name": "User 1 Home Loan Plan",
        "loan_type": "Home Loan",
        "principal": 4000000,
        "annual_rate": 8.5,
        "tenure_months": 240,
        "monthly_emi": 34713,
        "total_interest": 4331120,
        "total_repayment": 8331120,
        "effective_total_cost": 8350000,
        "foir": 38.5,
        "affordability_result": "Manageable"
    })
    assert create_res.status_code == 200
    scen_id = create_res.json()["id"]

    # List scenarios as User 1 (should contain scen_id)
    list1 = client.get("/api/v1/loans/scenarios", headers=headers1).json()["scenarios"]
    assert any(s["id"] == scen_id for s in list1)

    # List scenarios as User 2 (should NOT contain scen_id due to strict isolation)
    list2 = client.get("/api/v1/loans/scenarios", headers=headers2).json()["scenarios"]
    assert not any(s["id"] == scen_id for s in list2)

    # User 2 attempts to fetch User 1 scenario directly -> 404 Unauthorized
    get2 = client.get(f"/api/v1/loans/scenarios/{scen_id}", headers=headers2)
    assert get2.status_code == 404

    # User 2 attempts to delete User 1 scenario -> 404 Unauthorized
    del2 = client.delete(f"/api/v1/loans/scenarios/{scen_id}", headers=headers2)
    assert del2.status_code == 404

    # User 1 deletes own scenario -> 200 Success
    del1 = client.delete(f"/api/v1/loans/scenarios/{scen_id}", headers=headers1)
    assert del1.status_code == 200

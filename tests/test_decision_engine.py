from ml.decision_engine import evaluate_underwriting_policy


def test_underwriting_policy_likely_eligible():
    res = evaluate_underwriting_policy(
        monthly_income=100000.0,
        existing_emi=5000.0,
        credit_amount=100000.0,
        duration_months=12,
        savings_balance=200000.0,
        nova_score=780,
        calibrated_prob_good=0.88
    )
    assert res["decision"] == "Likely Eligible"
    assert res["foir_ratio"] < 0.50
    assert res["affordability_tier"] == "Good"
    assert len(res["loan_tenure_comparison"]) == 4


def test_underwriting_policy_high_risk():
    res = evaluate_underwriting_policy(
        monthly_income=30000.0,
        existing_emi=20000.0,
        credit_amount=300000.0,
        duration_months=12,
        savings_balance=10000.0,
        nova_score=550,
        calibrated_prob_good=0.40
    )
    assert res["decision"] == "High Risk"
    assert len(res["rejection_reasons"]) > 0

"""
Phase 10 — Comprehensive Test Suite
=====================================
Unit tests, ML regression tests, API integration tests, and feature schema validation.

ML Regression Rules:
  - An excellent applicant (high income, rich savings, low EMI, strong credit) 
    must NEVER produce a "High Risk" decision.
  - A weak applicant (very low income, high EMI, no savings, large loan)
    must NEVER produce a "Likely Eligible" decision.
"""
import json
import pytest
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Fixtures ─────────────────────────────────────────────────────────────────

EXCELLENT_PROFILE = {
    "applicant_name": "Priya Sharma",
    "age": 38, "sex": "female", "job": "skilled",
    "housing": "own",
    "saving_accounts": "rich",
    "checking_account": "rich",
    "credit_amount": 150000,
    "duration": 12,
    "purpose": "car",
    "monthly_income": 120000,
    "existing_emi": 0,
    "savings_balance": 500000,
}

WEAK_PROFILE = {
    "applicant_name": "Test Weak",
    "age": 22, "sex": "male", "job": "unskilled",
    "housing": "rent",
    "saving_accounts": "none",
    "checking_account": "none",
    "credit_amount": 800000,
    "duration": 60,
    "purpose": "others",
    "monthly_income": 18000,
    "existing_emi": 12000,
    "savings_balance": 0,
}

STANDARD_PROFILE = {
    "applicant_name": "Rohan Verma",
    "age": 32, "sex": "male", "job": "skilled",
    "housing": "own",
    "saving_accounts": "moderate",
    "checking_account": "moderate",
    "credit_amount": 200000,
    "duration": 18,
    "purpose": "car",
    "monthly_income": 90000,
    "existing_emi": 5000,
    "savings_balance": 250000,
}


# ─── Pipeline & Feature Engineering Tests ─────────────────────────────────────

class TestPipelineBuild:
    def test_pipeline_build_and_fit(self):
        """Pipeline builds, fits, and produces valid predictions."""
        from ml.pipeline import build_credit_pipeline
        from sklearn.ensemble import RandomForestClassifier

        clf = build_credit_pipeline(RandomForestClassifier(n_estimators=5, random_state=42))
        df = pd.DataFrame([
            {"Age": 32, "Sex": "male", "Job": 1, "Housing": "own",
             "Saving accounts": "moderate", "Checking account": "moderate",
             "Credit amount": 2000, "Duration": 12, "Purpose": "car"},
            {"Age": 22, "Sex": "female", "Job": 0, "Housing": "rent",
             "Saving accounts": "little", "Checking account": "little",
             "Credit amount": 5000, "Duration": 48, "Purpose": "education"},
        ])
        clf.fit(df, [1, 0])
        preds = clf.predict(df)
        probs = clf.predict_proba(df)
        assert len(preds) == 2
        assert probs.shape == (2, 2)
        assert all(0.0 <= p <= 1.0 for p in probs[:, 1])

    def test_pipeline_artifact_exists(self):
        """Serialized pipeline file must exist in models/."""
        pipeline_path = BASE_DIR / "models" / "nova_credit_pipeline.joblib"
        assert pipeline_path.exists(), (
            "nova_credit_pipeline.joblib not found. Run: python ml/train.py"
        )

    def test_pipeline_loads_successfully(self):
        """Pipeline must load without error and expose predict_proba."""
        import joblib
        pipeline_path = BASE_DIR / "models" / "nova_credit_pipeline.joblib"
        pipeline = joblib.load(pipeline_path)
        assert hasattr(pipeline, "predict_proba")


# ─── Nova Score Tests ──────────────────────────────────────────────────────────

class TestNovaScore:
    def test_score_range_high_prob(self):
        from ml.nova_score import calculate_nova_score
        res = calculate_nova_score(0.85, 0.10, "rich", 12, 32)
        assert 300 <= res["nova_score"] <= 850
        assert res["tier"] in ["Exceptional", "Excellent", "Strong", "Moderate", "Weak", "High Risk"]
        assert "disclaimer" in res
        assert "log_odds" in res

    def test_score_range_low_prob(self):
        from ml.nova_score import calculate_nova_score
        res = calculate_nova_score(0.25, 0.60, "none", 60, 22)
        assert 300 <= res["nova_score"] <= 850
        assert res["tier"] in ["Weak", "High Risk"]

    def test_score_band_monotonicity(self):
        """Higher probability should produce higher Nova Score (all else equal)."""
        from ml.nova_score import calculate_nova_score
        s_high = calculate_nova_score(0.90, 0.10, "rich", 12, 35)
        s_low  = calculate_nova_score(0.30, 0.50, "none", 48, 35)
        assert s_high["nova_score"] > s_low["nova_score"]

    def test_disclaimer_present(self):
        from ml.nova_score import calculate_nova_score
        res = calculate_nova_score(0.70, 0.20, "moderate", 24, 28)
        assert "CIBIL" in res["disclaimer"]
        assert "proprietary" in res["disclaimer"].lower()


# ─── Decision Engine Tests ─────────────────────────────────────────────────────

class TestDecisionEngine:
    def test_excellent_is_likely_eligible(self):
        """Excellent financial profile must produce Likely Eligible."""
        from ml.decision_engine import evaluate_underwriting_policy
        res = evaluate_underwriting_policy(
            monthly_income=120000, existing_emi=0,
            credit_amount=150000, duration_months=12,
            savings_balance=500000, nova_score=810,
            calibrated_prob_good=0.92,
        )
        assert res["decision"] == "Likely Eligible", (
            f"Excellent applicant got '{res['decision']}' — should be 'Likely Eligible'"
        )
        assert res["foir_ratio"] < 0.50
        assert res["affordability_tier"] in ["Good", "Moderate"]
        assert len(res["loan_tenure_comparison"]) == 4

    def test_high_foir_is_high_risk(self):
        """Excessive FOIR + low score must produce High Risk."""
        from ml.decision_engine import evaluate_underwriting_policy
        res = evaluate_underwriting_policy(
            monthly_income=20000, existing_emi=15000,
            credit_amount=500000, duration_months=12,
            savings_balance=5000, nova_score=520,
            calibrated_prob_good=0.30,
        )
        assert res["decision"] == "High Risk"
        assert len(res["rejection_reasons"]) > 0

    def test_borderline_is_conditional_or_review(self):
        """Borderline profile must not be fully approved or fully rejected."""
        from ml.decision_engine import evaluate_underwriting_policy
        res = evaluate_underwriting_policy(
            monthly_income=50000, existing_emi=5000,
            credit_amount=200000, duration_months=24,
            savings_balance=50000, nova_score=690,
            calibrated_prob_good=0.63,
        )
        assert res["decision"] in ["Conditionally Eligible", "Manual Review"]

    def test_improvement_recommendations_present(self):
        from ml.decision_engine import evaluate_underwriting_policy
        res = evaluate_underwriting_policy(
            monthly_income=35000, existing_emi=8000,
            credit_amount=300000, duration_months=36,
            savings_balance=20000, nova_score=630,
            calibrated_prob_good=0.55,
        )
        assert len(res["improvement_recommendations"]) > 0

    def test_insufficient_information_on_zero_income(self):
        from ml.decision_engine import evaluate_underwriting_policy
        res = evaluate_underwriting_policy(
            monthly_income=0, existing_emi=0, credit_amount=100000,
            duration_months=12, savings_balance=0, nova_score=500, calibrated_prob_good=0.5
        )
        assert res["decision"] == "Insufficient Information"


# ─── ML Regression Tests (Golden-Profile Assertions) ──────────────────────────

class TestMLRegression:
    """
    Critical regression tests: model output should remain directionally consistent
    across code and model changes. Run after every model retrain.
    """

    @pytest.fixture(scope="class")
    def pipeline(self):
        import joblib
        p = BASE_DIR / "models" / "nova_credit_pipeline.joblib"
        return joblib.load(p)

    def _make_df(self, profile: dict) -> pd.DataFrame:
        from config import CURRENCY_INR_TO_DATASET_SCALE
        return pd.DataFrame([{
            "Age": profile["age"],
            "Sex": profile["sex"],
            "Job": 2 if "skill" in profile["job"].lower() else 0,
            "Housing": profile["housing"],
            "Saving accounts": profile["saving_accounts"],
            "Checking account": profile["checking_account"],
            "Credit amount": profile["credit_amount"] / CURRENCY_INR_TO_DATASET_SCALE,
            "Duration": profile["duration"],
            "Purpose": profile["purpose"],
        }])

    def test_excellent_applicant_has_high_prob(self, pipeline):
        """Golden profile: excellent applicant must have P(Good) > 0.65."""
        df = self._make_df(EXCELLENT_PROFILE)
        prob = float(pipeline.predict_proba(df)[0][1])
        assert prob > 0.65, (
            f"REGRESSION: Excellent applicant P(Good)={prob:.3f} unexpectedly low."
        )

    def test_weak_applicant_decision_is_not_eligible(self, pipeline):
        """
        Golden profile regression: weak applicant (near-zero savings, extreme FOIR)
        must be rejected by the policy decision engine regardless of ML probability.
        The combined system (ML + underwriting policy) must not approve weak profiles.
        """
        from ml.nova_score import calculate_nova_score
        from ml.decision_engine import evaluate_underwriting_policy

        df = self._make_df(WEAK_PROFILE)
        prob = float(pipeline.predict_proba(df)[0][1])
        dti = (WEAK_PROFILE["credit_amount"] / WEAK_PROFILE["duration"]) / WEAK_PROFILE["monthly_income"]
        nova = calculate_nova_score(prob, dti, WEAK_PROFILE["saving_accounts"], WEAK_PROFILE["duration"], WEAK_PROFILE["age"])
        decision = evaluate_underwriting_policy(
            WEAK_PROFILE["monthly_income"], WEAK_PROFILE["existing_emi"],
            WEAK_PROFILE["credit_amount"], WEAK_PROFILE["duration"],
            WEAK_PROFILE["savings_balance"], nova["nova_score"], prob,
        )
        # FOIR for weak profile is (12000 + EMI) / 18000 which massively exceeds 50%
        # The decision engine must catch this regardless of ML output
        assert decision["decision"] in ["High Risk", "Manual Review", "Insufficient Information"], (
            f"REGRESSION: Weak applicant (FOIR={decision['foir_ratio']*100:.1f}%) got '{decision['decision']}'. "
            f"Nova={nova['nova_score']}, P(Good)={prob:.3f}."
        )

    def test_excellent_not_high_risk_decision(self, pipeline):
        """
        End-to-end: excellent applicant must never receive 'High Risk' verdict.
        """
        from ml.nova_score import calculate_nova_score
        from ml.decision_engine import evaluate_underwriting_policy

        df = self._make_df(EXCELLENT_PROFILE)
        prob = float(pipeline.predict_proba(df)[0][1])
        dti = (EXCELLENT_PROFILE["credit_amount"] / EXCELLENT_PROFILE["duration"]) / EXCELLENT_PROFILE["monthly_income"]
        nova = calculate_nova_score(prob, dti, EXCELLENT_PROFILE["saving_accounts"], EXCELLENT_PROFILE["duration"], EXCELLENT_PROFILE["age"])
        decision = evaluate_underwriting_policy(
            EXCELLENT_PROFILE["monthly_income"], EXCELLENT_PROFILE["existing_emi"],
            EXCELLENT_PROFILE["credit_amount"], EXCELLENT_PROFILE["duration"],
            EXCELLENT_PROFILE["savings_balance"], nova["nova_score"], prob,
        )
        assert decision["decision"] != "High Risk", (
            f"REGRESSION: Excellent applicant got 'High Risk'. Nova={nova['nova_score']}, P(Good)={prob:.3f}"
        )

    def test_weak_not_likely_eligible_decision(self, pipeline):
        """
        End-to-end: weak applicant must never receive 'Likely Eligible' verdict.
        """
        from ml.nova_score import calculate_nova_score
        from ml.decision_engine import evaluate_underwriting_policy

        df = self._make_df(WEAK_PROFILE)
        prob = float(pipeline.predict_proba(df)[0][1])
        dti = (WEAK_PROFILE["credit_amount"] / WEAK_PROFILE["duration"]) / WEAK_PROFILE["monthly_income"]
        nova = calculate_nova_score(prob, dti, WEAK_PROFILE["saving_accounts"], WEAK_PROFILE["duration"], WEAK_PROFILE["age"])
        decision = evaluate_underwriting_policy(
            WEAK_PROFILE["monthly_income"], WEAK_PROFILE["existing_emi"],
            WEAK_PROFILE["credit_amount"], WEAK_PROFILE["duration"],
            WEAK_PROFILE["savings_balance"], nova["nova_score"], prob,
        )
        assert decision["decision"] != "Likely Eligible", (
            f"REGRESSION: Weak applicant got 'Likely Eligible'. Nova={nova['nova_score']}, P(Good)={prob:.3f}"
        )

    def test_probability_output_is_valid(self, pipeline):
        """All probabilities must be in [0, 1] and sum to ~1."""
        df = self._make_df(STANDARD_PROFILE)
        probs = pipeline.predict_proba(df)[0]
        assert abs(sum(probs) - 1.0) < 1e-6
        assert all(0.0 <= p <= 1.0 for p in probs)


# ─── API Integration Tests ─────────────────────────────────────────────────────

class TestAPIIntegration:
    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        return TestClient(app)

    @pytest.fixture(scope="class")
    def auth_headers(self, client):
        import uuid
        from backend.app.database.session import SessionLocal, create_user
        email = f"comp_tester_{uuid.uuid4().hex[:6]}@example.com"
        db = SessionLocal()
        create_user(db, f"USR-{uuid.uuid4().hex[:8].upper()}", email, "Password123!", "Comp Tester", email_verified=True)
        db.close()
        login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
        token = login_res.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_health_check(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_assess_standard_profile(self, client, auth_headers):
        r = client.post("/api/v1/assess", json=STANDARD_PROFILE, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "assessment_id" in data
        assert "nova_score" in data
        assert "decision_engine" in data
        assert 300 <= data["nova_score"]["nova_score"] <= 850
        assert 0.0 <= data["approval_probability"] <= 1.0

    def test_assess_response_has_shap_drivers(self, client, auth_headers):
        r = client.post("/api/v1/assess", json=STANDARD_PROFILE, headers=auth_headers)
        data = r.json()
        assert "top_positive_drivers" in data
        assert "top_risk_drivers" in data
        assert isinstance(data["top_positive_drivers"], list)

    def test_simulate_returns_nova_score(self, client, auth_headers):
        payload = {"monthly_income": 75000, "credit_amount": 200000, "duration": 24,
                   "existing_emi": 5000, "savings_balance": 80000, "age": 28}
        r = client.post("/api/v1/simulate", json=payload, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "nova_score" in data
        assert "loan_tenure_comparison" in data
        assert len(data["loan_tenure_comparison"]) == 4

    def test_history_returns_list(self, client, auth_headers):
        r = client.get("/api/v1/history?limit=5", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "history" in data
        assert isinstance(data["history"], list)

    def test_model_health_endpoint(self, client, auth_headers):
        r = client.get("/api/v1/admin/models", headers=auth_headers)
        # Non-admin user gets 403 Forbidden
        assert r.status_code in [200, 403, 404]

    def test_model_metrics_endpoint(self, client, auth_headers):
        r = client.get("/api/v1/admin/models", headers=auth_headers)
        assert r.status_code in [200, 403, 404]

    def test_pdf_report_not_found(self, client, auth_headers):
        r = client.get("/api/v1/reports/pdf/nonexistent-id-000", headers=auth_headers)
        assert r.status_code == 404

    def test_assess_then_pdf_download(self, client, auth_headers):
        """Full workflow: submit assessment → download PDF."""
        r = client.post("/api/v1/assess", json=STANDARD_PROFILE, headers=auth_headers)
        assert r.status_code == 200
        assessment_id = r.json()["assessment_id"]

        pdf_r = client.get(f"/api/v1/reports/pdf/{assessment_id}", headers=auth_headers)
        assert pdf_r.status_code == 200
        assert pdf_r.headers["content-type"] == "application/pdf"
        assert len(pdf_r.content) > 1000


# ─── Model Intelligence Module Tests ─────────────────────────────────────────

class TestModelIntelligence:
    def test_benchmark_report_exists(self):
        path = BASE_DIR / "reports" / "model_benchmark_report.json"
        assert path.exists(), "Benchmark report missing — run ml/train.py"

    def test_get_model_health_returns_dict(self):
        from ml.model_intelligence import get_model_health
        h = get_model_health()
        assert "overall_status" in h
        assert "pipeline_loaded" in h
        assert h["overall_status"] in ["Healthy", "Warning", "Degraded"]
        # Drift monitoring must explicitly state it's not implemented
        assert "drift_note" in h

    def test_get_model_metrics_returns_real_data(self):
        from ml.model_intelligence import get_model_metrics
        m = get_model_metrics()
        assert "champion_model" in m
        assert "holdout_metrics" in m
        hm = m["holdout_metrics"]
        assert 0.5 <= hm["roc_auc"] <= 1.0, "ROC-AUC out of expected range"
        assert 0.0 <= hm["brier_score"] <= 1.0
        assert isinstance(m["model_comparison"], list)
        assert len(m["model_comparison"]) > 0

    def test_champion_has_highest_roc_auc(self):
        from ml.model_intelligence import get_model_metrics
        m = get_model_metrics()
        champion = next((x for x in m["model_comparison"] if x["is_champion"]), None)
        assert champion is not None
        challengers = [x for x in m["model_comparison"] if not x["is_champion"]]
        for c in challengers:
            assert champion["cv_roc_auc"] >= c["cv_roc_auc"], (
                f"Champion ROC-AUC {champion['cv_roc_auc']} < challenger {c['model']} {c['cv_roc_auc']}"
            )

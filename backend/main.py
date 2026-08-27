import sys
import uuid
import joblib
import pandas as pd
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import PIPELINE_FILE, BENCHMARK_REPORT_FILE, CURRENCY_INR_TO_DATASET_SCALE
FRONTEND_DIR = BASE_DIR / "frontend"
from ml.nova_score import calculate_nova_score
from ml.decision_engine import evaluate_underwriting_policy
from ml.explainer import CreditExplainer
from ml.model_intelligence import get_model_health, get_model_metrics
from backend.schemas import AssessmentRequest, SimulationRequest, LoanEmiRequest
from backend.database import save_assessment, get_assessment, get_assessment_history
from backend.pdf_generator import generate_credit_pdf

app = FastAPI(
    title="Nova Credit AI Enterprise REST API",
    version="2.2.0",
    description="Production API for Credit Assessment, Nova Score, Underwriting Engine, What-If Simulator, and PDF Reports."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Pipeline & Explainer
pipeline = None
explainer = None
if PIPELINE_FILE.exists():
    try:
        pipeline = joblib.load(PIPELINE_FILE)
        explainer = CreditExplainer(pipeline)
    except Exception as e:
        print(f"⚠️ Could not load pipeline: {e}")


@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "pipeline_loaded": pipeline is not None,
        "api_version": "2.2.0",
        "artifact": str(PIPELINE_FILE.name)
    }


@app.post("/api/v1/assess")
def perform_credit_assessment(req: AssessmentRequest):
    raw_dict = req.model_dump()
    
    # Calculate DTI
    monthly_payment = req.credit_amount / max(1, req.duration)
    dti = monthly_payment / max(1.0, req.monthly_income)

    # ML Calibrated Probability Prediction
    df_row = pd.DataFrame([{
        "Age": req.age,
        "Sex": req.sex.lower(),
        "Job": 2 if "high" in req.job.lower() or "manag" in req.job.lower() else (1 if "skill" in req.job.lower() else 0),
        "Housing": req.housing.lower(),
        "Saving accounts": req.saving_accounts.lower(),
        "Checking account": req.checking_account.lower(),
        "Credit amount": req.credit_amount / CURRENCY_INR_TO_DATASET_SCALE,
        "Duration": req.duration,
        "Purpose": req.purpose.lower()
    }])

    if pipeline:
        prob_good = float(pipeline.predict_proba(df_row)[0][1])
    else:
        score = 0.50
        score += 0.15 if dti < 0.15 else (-0.10 if dti > 0.40 else 0.0)
        prob_good = float(score)

    # Proprietary Nova Credit Score Engine (Log-Odds Formulated)
    nova_info = calculate_nova_score(
        calibrated_prob_good=prob_good,
        dti=dti,
        savings_standing=req.saving_accounts,
        duration_months=req.duration,
        age=req.age
    )

    # Underwriting Policy Decision Engine
    decision_info = evaluate_underwriting_policy(
        monthly_income=req.monthly_income,
        existing_emi=req.existing_emi,
        credit_amount=req.credit_amount,
        duration_months=req.duration,
        savings_balance=req.savings_balance,
        nova_score=nova_info["nova_score"],
        calibrated_prob_good=prob_good
    )

    # SHAP Local Explanations & Feature Drivers
    if explainer:
        shap_explanation = explainer.explain_instance(df_row)
        drivers = shap_explanation.get("all_drivers", [])
        top_positive_drivers = shap_explanation.get("top_positive_drivers", [])
        top_risk_drivers = shap_explanation.get("top_risk_drivers", [])
    else:
        drivers = [
            {"feature": "Savings Reserve Standing", "shap_value": 0.18, "direction": "Positive", "description": "↑ Strong savings reserve position"},
            {"feature": "Checking Account Health", "shap_value": 0.12, "direction": "Positive", "description": "↑ Positive checking standing"},
            {"feature": "Requested Credit Amount", "shap_value": -0.15, "direction": "Negative", "description": "↓ Elevated credit burden"},
            {"feature": "Loan Tenure (Months)", "shap_value": -0.08, "direction": "Negative", "description": "↓ Extended repayment duration"}
        ]
        top_positive_drivers = [d for d in drivers if d["direction"] == "Positive"]
        top_risk_drivers = [d for d in drivers if d["direction"] == "Negative"]

    assessment_id = str(uuid.uuid4())
    result = {
        "assessment_id": assessment_id,
        "applicant_name": req.applicant_name,
        "approval_probability": round(prob_good, 4),
        "approval_percentage": round(prob_good * 100, 1),
        "nova_score": nova_info,
        "decision_engine": decision_info,
        "drivers": drivers,
        "top_positive_drivers": top_positive_drivers,
        "top_risk_drivers": top_risk_drivers
    }

    # Save assessment to SQLite database
    try:
        save_assessment(assessment_id, req.applicant_name, raw_dict, result)
    except Exception as e:
        print(f"⚠️ DB Save warning: {e}")

    return result


@app.post("/api/v1/simulate")
def simulate_what_if(req: SimulationRequest):
    monthly_payment = req.credit_amount / max(1, req.duration)
    dti = monthly_payment / max(1.0, req.monthly_income)
    
    if pipeline:
        df_row = pd.DataFrame([{
            "Age": req.age,
            "Sex": "male",
            "Job": 2,
            "Housing": "own",
            "Saving accounts": "moderate",
            "Checking account": "moderate",
            "Credit amount": req.credit_amount / CURRENCY_INR_TO_DATASET_SCALE,
            "Duration": req.duration,
            "Purpose": "car"
        }])
        prob_good = float(pipeline.predict_proba(df_row)[0][1])
    else:
        prob_good = 0.50 + (0.20 if dti < 0.20 else (-0.15 if dti > 0.40 else 0.0))
        prob_good += (0.15 if req.savings_balance >= (monthly_payment * 3) else 0.0)
        prob_good = float(min(0.95, max(0.05, prob_good)))

    nova_info = calculate_nova_score(prob_good, dti, "moderate", req.duration, req.age)
    decision_info = evaluate_underwriting_policy(
        req.monthly_income, req.existing_emi, req.credit_amount, req.duration, req.savings_balance, nova_info["nova_score"], prob_good
    )

    return {
        "approval_percentage": round(prob_good * 100, 1),
        "nova_score": nova_info,
        "decision_engine": decision_info,
        "loan_tenure_comparison": decision_info.get("loan_tenure_comparison", []),
        "improvement_recommendations": decision_info.get("improvement_recommendations", [])
    }


@app.get("/api/v1/history")
def fetch_history(limit: int = 25):
    history = get_assessment_history(limit=limit)
    return {"history": history, "total_records": len(history)}


@app.get("/api/v1/reports/pdf/{assessment_id}")
def download_pdf_report(assessment_id: str):
    assessment_data = get_assessment(assessment_id)
    if not assessment_data:
        raise HTTPException(status_code=404, detail="Assessment ID not found")
    
    pdf_bytes = generate_credit_pdf(assessment_data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Nova_Credit_Report_{assessment_id[:8]}.pdf"}
    )


# ─── Model Intelligence Routes ────────────────────────────────────────────────
@app.get("/api/v1/models/health")
def model_health():
    return get_model_health()


@app.get("/api/v1/models/metrics")
def model_metrics():
    return get_model_metrics()


# Serve Static Web Client & Assets
FRONTEND_PATH = BASE_DIR / "frontend"
if FRONTEND_PATH.exists():
    @app.get("/", response_class=HTMLResponse)
    def read_root():
        return FileResponse(FRONTEND_PATH / "index.html")

    app.mount("/", StaticFiles(directory=str(FRONTEND_PATH), html=True), name="frontend")


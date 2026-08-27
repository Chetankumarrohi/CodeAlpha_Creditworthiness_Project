"""
Production FastAPI application — backend/app/main.py

Architecture:
  /api/v1/health               - service health
  /api/v1/credit/*             - credit assessment, simulation, history
  /api/v1/loans/*              - EMI, affordability
  /api/v1/models/health        - model operational health
  /api/v1/models/metrics       - real ML benchmark metrics
"""
import sys
import uuid
import logging
import joblib
import pandas as pd
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.core.config import get_settings
from backend.app.database.session import (
    init_db, get_db, save_assessment_orm,
    log_audit_event, get_assessment_by_id, get_history
)
from backend.schemas import AssessmentRequest, SimulationRequest
from backend.pdf_generator import generate_credit_pdf
from ml.nova_score import calculate_nova_score
from ml.decision_engine import evaluate_underwriting_policy
from ml.explainer import CreditExplainer
from ml.model_intelligence import get_model_health, get_model_metrics

settings = get_settings()
logger = logging.getLogger("nova_credit")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

FRONTEND_DIR = BASE_DIR / "frontend"

# ─── Application lifespan ──────────────────────────────────────────────────
pipeline = None
explainer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline, explainer
    init_db()
    pipeline_path = BASE_DIR / settings.PIPELINE_FILE
    if pipeline_path.exists():
        try:
            pipeline = joblib.load(pipeline_path)
            explainer = CreditExplainer(pipeline)
            logger.info(f"✅ Nova pipeline loaded from {pipeline_path.name}")
        except Exception as e:
            logger.error(f"❌ Pipeline load failed: {e}")
    else:
        logger.warning(f"⚠️  Pipeline not found at {pipeline_path}. ML predictions will use fallback.")
    yield
    logger.info("Nova Credit API shutting down.")


app = FastAPI(
    title="Nova Credit AI — Production API",
    version=settings.APP_VERSION,
    description="Institutional credit risk, underwriting, and financial intelligence platform.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Helpers ──────────────────────────────────────────────────────────────
def build_df_row(req) -> pd.DataFrame:
    job_map = {"skilled": 2, "highly skilled": 3, "unskilled": 1, "unemployed": 0}
    job_val = job_map.get(req.job.lower(), 2)
    return pd.DataFrame([{
        "Age": req.age,
        "Sex": req.sex.lower(),
        "Job": job_val,
        "Housing": req.housing.lower(),
        "Saving accounts": req.saving_accounts.lower(),
        "Checking account": req.checking_account.lower(),
        "Credit amount": req.credit_amount / settings.CURRENCY_SCALE,
        "Duration": req.duration,
        "Purpose": req.purpose.lower(),
    }])

def predict_prob(df_row: pd.DataFrame) -> float:
    if pipeline:
        return float(pipeline.predict_proba(df_row)[0][1])
    return 0.65  # safe fallback when pipeline absent


# ─── Health ───────────────────────────────────────────────────────────────
@app.get("/api/v1/health")
def health():
    return {
        "status": "healthy",
        "pipeline_loaded": pipeline is not None,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


# ─── Credit Assessment ────────────────────────────────────────────────────
@app.post("/api/v1/credit/assess")
@app.post("/api/v1/assess")          # backward-compat alias
def credit_assess(req: AssessmentRequest, db: Session = Depends(get_db)):
    raw = req.model_dump()
    df_row = build_df_row(req)
    prob_good = predict_prob(df_row)
    dti = (req.credit_amount / max(1, req.duration)) / max(1.0, req.monthly_income)

    nova_info = calculate_nova_score(prob_good, dti, req.saving_accounts, req.duration, req.age)
    decision_info = evaluate_underwriting_policy(
        req.monthly_income, req.existing_emi, req.credit_amount,
        req.duration, req.savings_balance, nova_info["nova_score"], prob_good,
    )

    if explainer:
        shap_out = explainer.explain_instance(df_row)
        drivers = shap_out.get("all_drivers", [])
        top_pos = shap_out.get("top_positive_drivers", [])
        top_risk = shap_out.get("top_risk_drivers", [])
    else:
        drivers, top_pos, top_risk = [], [], []

    assessment_id = str(uuid.uuid4())
    result = {
        "assessment_id": assessment_id,
        "applicant_name": req.applicant_name,
        "approval_probability": round(prob_good, 4),
        "approval_percentage": round(prob_good * 100, 1),
        "nova_score": nova_info,
        "decision_engine": decision_info,
        "drivers": drivers,
        "top_positive_drivers": top_pos,
        "top_risk_drivers": top_risk,
    }

    try:
        save_assessment_orm(db, assessment_id, req.applicant_name, raw, result)
        log_audit_event(db, "ASSESSMENT", assessment_id, req.applicant_name,
                        {"decision": decision_info.get("decision"), "nova_score": nova_info.get("nova_score")})
    except Exception as e:
        logger.warning(f"DB save failed: {e}")

    return result


# ─── Explain ─────────────────────────────────────────────────────────────
@app.post("/api/v1/credit/explain")
def credit_explain(req: AssessmentRequest):
    if not explainer:
        raise HTTPException(503, "SHAP explainer not available — pipeline not loaded.")
    df_row = build_df_row(req)
    return explainer.explain_instance(df_row)


# ─── Simulate ─────────────────────────────────────────────────────────────
@app.post("/api/v1/credit/simulate")
@app.post("/api/v1/simulate")        # backward-compat alias
def credit_simulate(req: SimulationRequest):
    dti = (req.credit_amount / max(1, req.duration)) / max(1.0, req.monthly_income)
    if pipeline:
        df_row = pd.DataFrame([{
            "Age": req.age, "Sex": "male", "Job": 2, "Housing": "own",
            "Saving accounts": "moderate", "Checking account": "moderate",
            "Credit amount": req.credit_amount / settings.CURRENCY_SCALE,
            "Duration": req.duration, "Purpose": "car",
        }])
        prob_good = float(pipeline.predict_proba(df_row)[0][1])
    else:
        prob_good = max(0.05, min(0.95, 0.55 + (0.15 if dti < 0.20 else -0.10)))

    nova_info = calculate_nova_score(prob_good, dti, "moderate", req.duration, req.age)
    decision_info = evaluate_underwriting_policy(
        req.monthly_income, req.existing_emi, req.credit_amount,
        req.duration, req.savings_balance, nova_info["nova_score"], prob_good,
    )
    return {
        "approval_percentage": round(prob_good * 100, 1),
        "nova_score": nova_info,
        "decision_engine": decision_info,
        "loan_tenure_comparison": decision_info.get("loan_tenure_comparison", []),
        "improvement_recommendations": decision_info.get("improvement_recommendations", []),
    }


# ─── History ──────────────────────────────────────────────────────────────
@app.get("/api/v1/credit/history")
@app.get("/api/v1/history")          # backward-compat alias
def credit_history(limit: int = 25, db: Session = Depends(get_db)):
    records = get_history(db, limit=limit)
    return {"history": records, "total_records": len(records)}


# ─── Loans EMI ────────────────────────────────────────────────────────────
@app.get("/api/v1/loans/emi")
def loan_emi(principal: float, annual_rate: float, tenure_years: int):
    r = annual_rate / 12 / 100
    n = tenure_years * 12
    if r > 0:
        emi = principal * r * (1 + r)**n / ((1 + r)**n - 1)
    else:
        emi = principal / n
    return {
        "monthly_emi": round(emi, 2),
        "total_interest": round(emi * n - principal, 2),
        "total_payment": round(emi * n, 2),
    }


# ─── Model Intelligence ────────────────────────────────────────────────────
@app.get("/api/v1/models/health")
def models_health():
    return get_model_health()


@app.get("/api/v1/models/metrics")
def models_metrics():
    return get_model_metrics()


# ─── PDF Reports ────────────────────────────────────────────────────────────
@app.get("/api/v1/reports/pdf/{assessment_id}")
def download_pdf(assessment_id: str, db: Session = Depends(get_db)):
    data = get_assessment_by_id(db, assessment_id)
    if not data:
        raise HTTPException(404, "Assessment not found")
    log_audit_event(db, "PDF_DOWNLOAD", assessment_id)
    pdf_bytes = generate_credit_pdf(data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Nova_Credit_{assessment_id[:8]}.pdf"},
    )


# ─── Static Frontend ────────────────────────────────────────────────────────
if FRONTEND_DIR.exists():
    @app.get("/", response_class=HTMLResponse)
    def root():
        return FileResponse(FRONTEND_DIR / "index.html")

    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

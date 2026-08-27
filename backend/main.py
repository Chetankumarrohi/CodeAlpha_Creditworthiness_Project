import os
import sys
import uuid
import logging
import joblib
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends, Request, Response, Header, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.core.config import get_settings
from backend.app.core.security import (
    create_access_token, decode_access_token, verify_password, check_rate_limit
)
from backend.app.database.session import (
    init_db, get_db, UserRecord,
    get_user_by_email, get_user_by_id, create_user, update_user_last_login,
    update_user_password, update_user_profile, toggle_user_status, get_all_users, count_users,
    get_financial_profile, save_or_update_financial_profile,
    save_assessment_orm, get_assessment_by_id, get_history, count_assessments,
    save_loan_simulation, get_loan_simulations, save_report_record, get_user_reports,
    log_activity, get_activity_logs, get_system_stats
)
from backend.schemas import (
    AssessmentRequest, SimulationRequest, LoanEmiRequest,
    UserLoginRequest, UserRegisterRequest, AuthTokenResponse, UserResponse,
    UserProfileUpdateRequest, PasswordChangeRequest, ForgotPasswordRequest, ResetPasswordRequest,
    UserStatusUpdateRequest, FinancialProfileRequest, UserDetailAdminResponse
)
from backend.pdf_generator import generate_credit_pdf
from ml.nova_score import calculate_nova_score
from ml.decision_engine import evaluate_underwriting_policy
from ml.explainer import CreditExplainer
from ml.model_intelligence import get_model_health, get_model_metrics

settings = get_settings()
logger = logging.getLogger("nova_credit")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

FRONTEND_DIR = BASE_DIR / "frontend"

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
            logger.info(f"✅ Nova ML pipeline loaded from {pipeline_path.name}")
        except Exception as e:
            logger.error(f"❌ Pipeline load failed: {e}")
    else:
        logger.warning(f"⚠️  Pipeline file not found at {pipeline_path}.")
    yield
    logger.info("Nova Credit API shutting down.")


app = FastAPI(
    title="Nova Credit AI — Institutional API",
    version=settings.APP_VERSION,
    description="Multi-user institutional credit intelligence, ML risk decisioning, and administrative console API.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Auth Dependencies & RBAC Guards ───────────────────────────────────────────

def get_current_user_optional(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> Optional[UserRecord]:
    """Resolves authenticated user from Bearer JWT token, returning None if missing/invalid."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    user = get_user_by_id(db, payload["sub"])
    if not user or not user.is_active:
        return None
    return user


def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> UserRecord:
    """Mandatory authentication guard. Returns authenticated UserRecord or raises 401."""
    user = get_current_user_optional(authorization=authorization, db=db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(current_user: UserRecord = Depends(get_current_user)) -> UserRecord:
    """RBAC Guard. Enforces ADMIN role or raises 403 Forbidden."""
    if current_user.role.upper() != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrative access required.",
        )
    return current_user


def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "127.0.0.1"


# ─── Authentication Routes ────────────────────────────────────────────────────

@app.post("/api/v1/auth/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(req: UserRegisterRequest, request: Request, db: Session = Depends(get_db)):
    # Rate limit signups per IP
    ip = get_client_ip(request)
    if not check_rate_limit(ip, max_requests=10, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many registration attempts. Please try again later.")

    existing = get_user_by_email(db, req.email)
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email address already exists.")

    # Strictly assign USER role for public signups (cannot be elevated via payload)
    user_id = "USR-" + uuid.uuid4().hex[:8].upper()
    user = create_user(
        db=db,
        user_id=user_id,
        email=req.email,
        password_plain=req.password,
        full_name=req.full_name,
        role="USER"
    )

    update_user_last_login(db, user.id)
    log_activity(db, "account_created", user_id=user.id, user_email=user.email, resource_type="user", resource_id=user.id, ip_address=ip)
    log_activity(db, "login_success", user_id=user.id, user_email=user.email, resource_type="session", ip_address=ip)

    token = create_access_token(subject=user.id, role=user.role)
    return AuthTokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


@app.post("/api/v1/auth/login", response_model=AuthTokenResponse)
def login_user(req: UserLoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    if not check_rate_limit(ip, max_requests=15, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many login attempts. Please wait 60 seconds.")

    user = get_user_by_email(db, req.email)
    if not user or not verify_password(req.password, user.password_hash) or not user.is_active:
        log_activity(db, "login_failed", user_email=req.email, ip_address=ip, details={"reason": "invalid_credentials"})
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    update_user_last_login(db, user.id)
    log_activity(db, "login_success", user_id=user.id, user_email=user.email, resource_type="session", ip_address=ip)

    token = create_access_token(subject=user.id, role=user.role)
    return AuthTokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


@app.post("/api/v1/auth/logout")
def logout_user(request: Request, current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    log_activity(db, "logout", user_id=current_user.id, user_email=current_user.email, ip_address=get_client_ip(request))
    return {"message": "Successfully logged out session."}


@app.get("/api/v1/auth/me", response_model=UserResponse)
def get_me(current_user: UserRecord = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        email_verified=current_user.email_verified,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
    )


@app.post("/api/v1/auth/forgot-password")
def forgot_password(req: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    user = get_user_by_email(db, req.email)
    if user:
        log_activity(db, "password_reset_requested", user_id=user.id, user_email=user.email, ip_address=get_client_ip(request))
    # Return generic success response to prevent user enumeration
    return {"message": "If an account with that email exists, password reset instructions have been dispatched."}


@app.post("/api/v1/auth/reset-password")
def reset_password(req: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    user = get_user_by_email(db, req.email)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid password reset token or request.")
    update_user_password(db, user.id, req.new_password)
    log_activity(db, "password_changed", user_id=user.id, user_email=user.email, ip_address=get_client_ip(request))
    return {"message": "Password reset successful. Please sign in with your new password."}


# ─── User Profile & Settings Endpoints ────────────────────────────────────────

@app.get("/api/v1/user/profile")
def get_profile(current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    financial_prof = get_financial_profile(db, current_user.id)
    return {
        "user": UserResponse(
            id=current_user.id,
            email=current_user.email,
            full_name=current_user.full_name,
            role=current_user.role,
            is_active=current_user.is_active,
            email_verified=current_user.email_verified,
            created_at=current_user.created_at,
            last_login_at=current_user.last_login_at,
        ),
        "financial_profile": {
            "monthly_income": financial_prof.monthly_income if financial_prof else 50000.0,
            "existing_emi": financial_prof.existing_emi if financial_prof else 0.0,
            "savings_balance": financial_prof.savings_balance if financial_prof else 100000.0,
            "housing_type": financial_prof.housing_type if financial_prof else "own",
            "employment_status": financial_prof.employment_status if financial_prof else "skilled",
            "credit_purpose": financial_prof.credit_purpose if financial_prof else "personal",
        } if financial_prof else None
    }


@app.post("/api/v1/user/profile")
def update_profile(req: UserProfileUpdateRequest, request: Request, current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    updated_user = update_user_profile(db, current_user.id, full_name=req.full_name)
    log_activity(db, "profile_updated", user_id=current_user.id, user_email=current_user.email, ip_address=get_client_ip(request))
    return {"message": "Profile updated successfully.", "user": updated_user}


@app.post("/api/v1/user/password")
def change_password(req: PasswordChangeRequest, request: Request, current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password incorrect.")
    update_user_password(db, current_user.id, req.new_password)
    log_activity(db, "password_changed", user_id=current_user.id, user_email=current_user.email, ip_address=get_client_ip(request))
    return {"message": "Password changed successfully."}


@app.post("/api/v1/user/financial-profile")
def update_user_financial_profile(req: FinancialProfileRequest, request: Request, current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    prof = save_or_update_financial_profile(db, current_user.id, req.model_dump())
    log_activity(db, "profile_updated", user_id=current_user.id, user_email=current_user.email, details={"section": "financial"}, ip_address=get_client_ip(request))
    return {"message": "Financial profile updated.", "financial_profile": prof}


# ─── Credit Assessment Endpoints (User Isolated) ──────────────────────────────

def build_df_row(req: AssessmentRequest) -> pd.DataFrame:
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
    return 0.68


@app.post("/api/v1/credit/assess")
@app.post("/api/v1/assess")
def credit_assess(
    req: AssessmentRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
):
    """Submits credit assessment and records under authenticated user's isolated account."""
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

    assessment_id = "ASS-" + uuid.uuid4().hex[:8].upper()
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

    # Save under current_user.id
    save_assessment_orm(db, assessment_id, req.applicant_name, raw, result, user_id=current_user.id)
    save_or_update_financial_profile(db, current_user.id, {
        "monthly_income": req.monthly_income,
        "existing_emi": req.existing_emi,
        "savings_balance": req.savings_balance,
        "housing_type": req.housing,
        "employment_status": req.job,
        "credit_purpose": req.purpose,
    })

    log_activity(
        db,
        "credit_assessment_created",
        user_id=current_user.id,
        user_email=current_user.email,
        resource_type="credit_assessment",
        resource_id=assessment_id,
        details={"nova_score": nova_info["nova_score"], "decision": decision_info["decision"]},
        ip_address=get_client_ip(request)
    )

    return result


@app.get("/api/v1/credit/history")
@app.get("/api/v1/history")
def credit_history(
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
):
    """Returns assessment history. Regular users receive ONLY their personal assessments; Admins see all."""
    is_admin = (current_user.role.upper() == "ADMIN")
    records = get_history(db, user_id=current_user.id, is_admin=is_admin, limit=limit, offset=offset, search=search)
    return {
        "history": records,
        "total_records": len(records),
        "user_id": current_user.id,
        "is_admin": is_admin
    }


@app.get("/api/v1/credit/history/{assessment_id}")
def credit_history_detail(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
):
    """Retrieves specific assessment payload. Enforces server-side ownership validation."""
    is_admin = (current_user.role.upper() == "ADMIN")
    record = get_assessment_by_id(db, assessment_id, user_id=current_user.id, is_admin=is_admin)
    if not record:
        raise HTTPException(status_code=404, detail="Credit assessment record not found or access denied.")
    return record


@app.post("/api/v1/credit/explain")
def credit_explain(req: AssessmentRequest, current_user: UserRecord = Depends(get_current_user)):
    if not explainer:
        raise HTTPException(status_code=503, detail="SHAP explainer model unavailable.")
    df_row = build_df_row(req)
    return explainer.explain_instance(df_row)


# ─── Loan Simulations & Calculations ─────────────────────────────────────────

@app.post("/api/v1/credit/simulate")
@app.post("/api/v1/simulate")
def credit_simulate(
    req: SimulationRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
):
    """Runs What-If credit simulation and records in user simulation history."""
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
    output = {
        "approval_percentage": round(prob_good * 100, 1),
        "nova_score": nova_info,
        "decision_engine": decision_info,
        "loan_tenure_comparison": decision_info.get("loan_tenure_comparison", []),
        "improvement_recommendations": decision_info.get("improvement_recommendations", []),
    }

    sim_record = save_loan_simulation(db, current_user.id, req.model_dump(), output)
    log_activity(
        db,
        "what_if_simulation_run",
        user_id=current_user.id,
        user_email=current_user.email,
        resource_type="simulation",
        resource_id=sim_record.id,
        ip_address=get_client_ip(request)
    )

    return output


@app.get("/api/v1/simulations")
def list_simulations(db: Session = Depends(get_db), current_user: UserRecord = Depends(get_current_user)):
    is_admin = (current_user.role.upper() == "ADMIN")
    sims = get_loan_simulations(db, user_id=current_user.id, is_admin=is_admin, limit=50)
    return {"simulations": sims}


@app.post("/api/v1/loans/calculate")
def calculate_loan_amortization(req: LoanEmiRequest, current_user: UserRecord = Depends(get_current_user)):
    P = req.principal
    r = (req.annual_rate / 100) / 12
    n = req.tenure_years * 12

    if r == 0:
        emi = P / n
    else:
        emi = P * r * ((1 + r) ** n) / (((1 + r) ** n) - 1)

    total_payment = emi * n
    total_interest = total_payment - P

    schedule = []
    balance = P
    for month in range(1, min(n + 1, 361)):
        interest_part = balance * r
        principal_part = emi - interest_part
        balance = max(0.0, balance - principal_part)
        schedule.append({
            "month": month,
            "emi": round(emi, 2),
            "principal_paid": round(principal_part, 2),
            "interest_paid": round(interest_part, 2),
            "remaining_balance": round(balance, 2),
        })

    return {
        "monthly_emi": round(emi, 2),
        "total_payment": round(total_payment, 2),
        "total_interest": round(total_interest, 2),
        "principal": P,
        "tenure_months": n,
        "schedule": schedule
    }


@app.get("/api/v1/reports/pdf/{assessment_id}")
def download_pdf(
    assessment_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
):
    """Generates institutional PDF report. Validates user ownership or admin privilege."""
    is_admin = (current_user.role.upper() == "ADMIN")
    data = get_assessment_by_id(db, assessment_id, user_id=current_user.id, is_admin=is_admin)
    if not data:
        raise HTTPException(status_code=404, detail="Assessment not found or access denied.")

    applicant_name = data.get("applicant_name", "Applicant")
    save_report_record(db, current_user.id, assessment_id, applicant_name, "PDF_ASSESSMENT")
    log_activity(
        db,
        "report_generated",
        user_id=current_user.id,
        user_email=current_user.email,
        resource_type="pdf_report",
        resource_id=assessment_id,
        ip_address=get_client_ip(request)
    )

    pdf_bytes = generate_credit_pdf(data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Nova_Credit_{assessment_id[:8]}.pdf"},
    )


# ─── Admin Console Endpoints (Strictly Protected by require_admin) ─────────────

@app.get("/api/v1/admin/dashboard/stats")
def admin_dashboard_stats(db: Session = Depends(get_db), admin: UserRecord = Depends(require_admin)):
    """Returns high-level system metrics, user signups, and activity stats for Admin Console."""
    return get_system_stats(db)


@app.get("/api/v1/admin/users")
def admin_list_users(
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    admin: UserRecord = Depends(require_admin)
):
    """Lists registered users with pagination, search, and role filters."""
    users = get_all_users(db, search=search, role=role, limit=limit, offset=offset)
    total = count_users(db)
    return {
        "users": [
            UserResponse(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                role=u.role,
                is_active=u.is_active,
                email_verified=u.email_verified,
                created_at=u.created_at,
                last_login_at=u.last_login_at,
            )
            for u in users
        ],
        "total": total,
        "limit": limit,
        "offset": offset
    }


@app.get("/api/v1/admin/users/{user_id}", response_model=UserDetailAdminResponse)
def admin_get_user_detail(
    user_id: str,
    db: Session = Depends(get_db),
    admin: UserRecord = Depends(require_admin)
):
    """Detailed drill-down inspector view for a specific user (does NOT expose password hash)."""
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    financial_prof = get_financial_profile(db, user_id)
    assessments = get_history(db, user_id=user_id, is_admin=True, limit=10)
    simulations = get_loan_simulations(db, user_id=user_id, is_admin=True, limit=10)
    reports = get_user_reports(db, user_id=user_id, is_admin=True, limit=10)
    activities = get_activity_logs(db, user_id=user_id, limit=20)

    return UserDetailAdminResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            email_verified=user.email_verified,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        ),
        financial_profile={
            "monthly_income": financial_prof.monthly_income,
            "existing_emi": financial_prof.existing_emi,
            "savings_balance": financial_prof.savings_balance,
            "housing_type": financial_prof.housing_type,
            "employment_status": financial_prof.employment_status,
            "credit_purpose": financial_prof.credit_purpose,
        } if financial_prof else None,
        assessment_count=count_assessments(db, user_id=user_id),
        simulation_count=len(simulations),
        report_count=len(reports),
        recent_assessments=assessments,
        recent_simulations=simulations,
        recent_activities=activities,
    )


@app.put("/api/v1/admin/users/{user_id}/status")
def admin_update_user_status(
    user_id: str,
    req: UserStatusUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: UserRecord = Depends(require_admin)
):
    """Activates or deactivates a user account."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own administrative account.")
    updated = toggle_user_status(db, user_id, req.is_active)
    if not updated:
        raise HTTPException(status_code=404, detail="User account not found.")

    action_label = "user_activated" if req.is_active else "user_deactivated"
    log_activity(
        db,
        action_label,
        user_id=admin.id,
        user_email=admin.email,
        resource_type="user",
        resource_id=user_id,
        ip_address=get_client_ip(request)
    )
    return {"message": f"User status updated to {'Active' if req.is_active else 'Deactivated'}.", "is_active": updated.is_active}


@app.get("/api/v1/admin/activity")
def admin_activity_logs(
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    admin: UserRecord = Depends(require_admin)
):
    """System-wide audit trail for administrative inspection."""
    logs = get_activity_logs(db, user_id=user_id, action=action, limit=limit, offset=offset)
    return {"activity_logs": logs, "limit": limit, "offset": offset}


@app.get("/api/v1/admin/assessments")
def admin_list_assessments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin: UserRecord = Depends(require_admin)
):
    """Returns global credit assessment log across all users."""
    records = get_history(db, is_admin=True, limit=limit, offset=offset, search=search)
    total = count_assessments(db)
    return {"assessments": records, "total": total}


@app.get("/api/v1/admin/models")
def admin_model_diagnostics(admin: UserRecord = Depends(require_admin)):
    """Returns champion ML model diagnostics, health metrics, and ROC parameters."""
    return {
        "health": get_model_health(),
        "metrics": get_model_metrics()
    }


# ─── System Health ─────────────────────────────────────────────────────────

@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── SPA Client Router & Static Files ─────────────────────────────────────────

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static_assets")

    @app.get("/{full_path:path}", response_class=HTMLResponse)
    def spa_router(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        # Serve exact static file if exists in frontend directory (e.g. styles.css, app.js)
        target_file = FRONTEND_DIR / full_path
        if full_path and target_file.exists() and target_file.is_file():
            return FileResponse(target_file)
        # Default to index.html for client-side SPA routing (/login, /app/*, /admin/*)
        return FileResponse(FRONTEND_DIR / "index.html")

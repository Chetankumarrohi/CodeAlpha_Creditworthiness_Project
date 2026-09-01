import os
import sys
import uuid
import secrets
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
    create_access_token, decode_access_token, verify_password, check_rate_limit,
    generate_numeric_otp, hash_otp_code, verify_otp_code,
    generate_totp_secret, get_totp_uri, generate_qr_code_data_url, verify_totp_code,
    generate_recovery_codes, hash_recovery_code, create_2fa_challenge_token,
    generate_session_token, check_action_cooldown
)
from backend.app.database.session import (
    init_db, get_db, UserRecord,
    get_user_by_email, get_user_by_id, create_user, update_user_last_login,
    update_user_password, update_user_profile, toggle_user_status, get_all_users, count_users,
    get_financial_profile, save_or_update_financial_profile,
    save_assessment_orm, get_assessment_by_id, get_history, count_assessments,
    save_loan_simulation, get_loan_simulations, save_report_record, get_user_reports,
    log_activity, get_activity_logs, get_system_stats,
    save_loan_scenario, get_user_loan_scenarios, get_loan_scenario_by_id, delete_loan_scenario,
    create_email_verification_challenge, get_active_email_challenge, mark_user_email_verified,
    record_login_failure, is_account_locked, set_user_totp_secret, enable_user_2fa, disable_user_2fa,
    save_user_recovery_codes, verify_and_consume_recovery_code,
    create_password_reset_token, verify_and_consume_password_reset_token,
    get_oauth_account, link_oauth_account,
    create_user_session, get_active_sessions, revoke_user_session, revoke_all_user_sessions
)
from backend.schemas import (
    AssessmentRequest, SimulationRequest, LoanEmiRequest, LoanAffordabilityRequest,
    TenureOptimizeRequest, LoanPrepaymentRequest, LoanCompareRequest, LoanScenarioCreateRequest,
    UserLoginRequest, UserRegisterRequest, EmailVerifyRequest, ResendVerificationRequest,
    TwoFactorVerifyRequest, TwoFactorSetupResponse, TwoFactorConfirmRequest, TwoFactorDisableRequest,
    GoogleAuthRequest, GoogleAuthUrlResponse, UserSessionResponse, SecuritySettingsResponse,
    AuthTokenResponse, UserResponse,
    UserProfileUpdateRequest, PasswordChangeRequest, ForgotPasswordRequest, ResetPasswordRequest,
    UserStatusUpdateRequest, FinancialProfileRequest, UserDetailAdminResponse
)
from backend.app.services.emi_service import calculate_emi
from backend.app.services.amortization_service import generate_amortization_schedule
from backend.app.services.affordability_service import evaluate_affordability
from backend.app.services.tenure_optimizer_service import optimize_tenures
from backend.app.services.prepayment_service import simulate_prepayment
from backend.app.services.loan_comparison_service import compare_loan_offers
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
    if not payload or "sub" not in payload or payload.get("scope") != "access":
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


def get_device_info(request: Request) -> str:
    ua = request.headers.get("user-agent", "Web Browser")
    if "Mobile" in ua:
        return "Mobile Device"
    elif "Macintosh" in ua:
        return "macOS Desktop"
    elif "Windows" in ua:
        return "Windows Desktop"
    elif "Linux" in ua:
        return "Linux Desktop"
    return "Web Browser"


# ─── Authentication Routes ────────────────────────────────────────────────────

@app.post("/api/v1/auth/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(req: UserRegisterRequest, request: Request, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    if not check_rate_limit(ip, max_requests=8, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many registration attempts from this IP. Please wait.")

    clean_email = req.email.lower().strip()
    existing = get_user_by_email(db, clean_email)
    
    if existing:
        if existing.email_verified:
            raise HTTPException(status_code=400, detail="An account with this email address already exists.")
        # If user exists but is unverified, regenerate verification code and guide them to verify
        user = existing
    else:
        # Strictly assign USER role for public signups (cannot be elevated via payload)
        user_id = "USR-" + uuid.uuid4().hex[:8].upper()
        user = create_user(
            db=db,
            user_id=user_id,
            email=clean_email,
            password_plain=req.password,
            full_name=req.full_name,
            role="USER",
            email_verified=False
        )

    # Generate single-use 6-digit numeric verification OTP
    otp = generate_numeric_otp(6)
    code_hash = hash_otp_code(otp)
    create_email_verification_challenge(db, user_id=user.id, email=user.email, code_hash=code_hash, expiry_minutes=10)

    # Log for development/testing visibility
    logger.info(f"📧 [Email Verification OTP] Code for {user.email}: {otp}")
    log_activity(db, "signup_initiated", user_id=user.id, user_email=user.email, resource_type="user", ip_address=ip)

    return AuthTokenResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        requires_verification=True,
        message=f"A 6-digit verification code has been dispatched to {user.email}."
    )


@app.post("/api/v1/auth/verify-email", response_model=AuthTokenResponse)
def verify_email(req: EmailVerifyRequest, request: Request, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    clean_email = req.email.lower().strip()
    user = get_user_by_email(db, clean_email)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or verification challenge.")

    challenge = get_active_email_challenge(db, clean_email)
    if not challenge:
        raise HTTPException(status_code=400, detail="That code is invalid or has expired. Please request a new code.")

    if not verify_otp_code(req.code, challenge.code_hash):
        challenge.attempts_left -= 1
        if challenge.attempts_left <= 0:
            challenge.consumed = True
        db.commit()
        raise HTTPException(status_code=400, detail=f"Invalid verification code. {max(0, challenge.attempts_left)} attempt(s) remaining.")

    # Mark challenge consumed and activate user
    challenge.consumed = True
    mark_user_email_verified(db, user.id)
    update_user_last_login(db, user.id)

    # Create user session
    session_token = generate_session_token()
    create_user_session(db, user.id, session_token=session_token, device_info=get_device_info(request), ip_address=ip)

    log_activity(db, "email_verified", user_id=user.id, user_email=user.email, ip_address=ip)
    log_activity(db, "login_success", user_id=user.id, user_email=user.email, resource_type="session", ip_address=ip)

    token = create_access_token(subject=user.id, role=user.role, session_id=session_token)
    return AuthTokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        message="Email successfully verified. Welcome to Nova Credit AI!"
    )


@app.post("/api/v1/auth/resend-verification")
def resend_verification_code(req: ResendVerificationRequest, request: Request, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    clean_email = req.email.lower().strip()
    user = get_user_by_email(db, clean_email)
    if not user:
        # Return generic success to avoid user enumeration
        return {"message": "If an unverified account exists, a new code has been sent."}

    if user.email_verified:
        return {"message": "Email is already verified. Please sign in directly."}

    # Enforce 45s cooldown
    can_resend, remaining_secs = check_action_cooldown(f"resend_otp_{clean_email}", cooldown_seconds=45)
    if not can_resend:
        raise HTTPException(status_code=429, detail=f"Please wait {remaining_secs}s before requesting a new code.")

    otp = generate_numeric_otp(6)
    code_hash = hash_otp_code(otp)
    create_email_verification_challenge(db, user_id=user.id, email=user.email, code_hash=code_hash, expiry_minutes=10)

    logger.info(f"📧 [Resent Email OTP] Code for {user.email}: {otp}")
    log_activity(db, "verification_code_resent", user_id=user.id, user_email=user.email, ip_address=ip)
    return {"message": "A new 6-digit verification code has been dispatched."}


@app.post("/api/v1/auth/login", response_model=AuthTokenResponse)
def login_user(req: UserLoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    if not check_rate_limit(ip, max_requests=15, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many login attempts. Please wait 60 seconds.")

    user = get_user_by_email(db, req.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    # Check account lockout
    locked, remaining_mins = is_account_locked(user)
    if locked:
        raise HTTPException(
            status_code=423,
            detail=f"Account temporarily locked due to repeated failed attempts. Please retry in {remaining_mins} minute(s)."
        )

    if not verify_password(req.password, user.password_hash):
        attempts, lock_iso = record_login_failure(db, user, max_attempts=5, lock_minutes=15)
        log_activity(db, "login_failed", user_id=user.id, user_email=user.email, ip_address=ip, details={"reason": "invalid_password", "attempts": attempts})
        if lock_iso:
            raise HTTPException(status_code=423, detail="Too many failed login attempts. Account locked for 15 minutes.")
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated. Please contact support.")

    # If email is not yet verified, require OTP verification before issuing full session
    if not user.email_verified:
        otp = generate_numeric_otp(6)
        code_hash = hash_otp_code(otp)
        create_email_verification_challenge(db, user_id=user.id, email=user.email, code_hash=code_hash, expiry_minutes=10)
        logger.info(f"📧 [Email Verification OTP] Code for {user.email}: {otp}")
        return AuthTokenResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            requires_verification=True,
            message="Please verify your email address to activate your account."
        )

    # If Two-Factor Authentication is enabled, issue a short-lived 2FA challenge token
    if user.two_factor_enabled:
        temp_token = create_2fa_challenge_token(user.id, user.email, user.two_factor_method or "totp")
        log_activity(db, "2fa_challenge_issued", user_id=user.id, user_email=user.email, ip_address=ip)
        return AuthTokenResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            requires_2fa=True,
            temp_token=temp_token,
            two_factor_method=user.two_factor_method or "totp",
            message="Two-step verification required."
        )

    # Standard Login Success
    update_user_last_login(db, user.id)
    session_token = generate_session_token()
    create_user_session(db, user.id, session_token=session_token, device_info=get_device_info(request), ip_address=ip)

    log_activity(db, "login_success", user_id=user.id, user_email=user.email, resource_type="session", ip_address=ip)

    token = create_access_token(subject=user.id, role=user.role, session_id=session_token)
    return AuthTokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


@app.post("/api/v1/auth/2fa/verify", response_model=AuthTokenResponse)
def verify_two_factor(req: TwoFactorVerifyRequest, request: Request, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    payload = decode_access_token(req.temp_token)
    if not payload or payload.get("scope") != "2fa_challenge" or "sub" not in payload:
        raise HTTPException(status_code=401, detail="2FA challenge session has expired. Please sign in again.")

    user = get_user_by_id(db, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User account invalid or deactivated.")

    # 1. Recovery code branch
    if req.is_recovery_code or "-" in req.code:
        code_h = hash_recovery_code(req.code)
        if not verify_and_consume_recovery_code(db, user.id, code_h):
            log_activity(db, "2fa_recovery_code_failed", user_id=user.id, user_email=user.email, ip_address=ip)
            raise HTTPException(status_code=400, detail="Invalid or previously consumed recovery code.")
        log_activity(db, "2fa_recovery_code_used", user_id=user.id, user_email=user.email, ip_address=ip)
    else:
        # 2. Standard TOTP Authenticator code branch
        if not user.totp_secret or not verify_totp_code(user.totp_secret, req.code):
            log_activity(db, "2fa_totp_failed", user_id=user.id, user_email=user.email, ip_address=ip)
            raise HTTPException(status_code=400, detail="That code is invalid. Check your authenticator app.")

    # 2FA Succeeded: Issue Full Session
    update_user_last_login(db, user.id)
    session_token = generate_session_token()
    create_user_session(db, user.id, session_token=session_token, device_info=get_device_info(request), ip_address=ip)

    log_activity(db, "2fa_login_success", user_id=user.id, user_email=user.email, resource_type="session", ip_address=ip)
    token = create_access_token(subject=user.id, role=user.role, session_id=session_token)

    return AuthTokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        message="Authentication complete."
    )


@app.get("/api/v1/auth/google/url", response_model=GoogleAuthUrlResponse)
def get_google_auth_url():
    state = secrets.token_urlsafe(16)
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id=GOOGLE_CLIENT_ID&"
        f"response_type=code&"
        f"scope=openid%20email%20profile&"
        f"redirect_uri=http://localhost:8085/api/v1/auth/google/callback&"
        f"state={state}"
    )
    return GoogleAuthUrlResponse(auth_url=auth_url, state=state)


@app.post("/api/v1/auth/google", response_model=AuthTokenResponse)
def google_authenticate(req: GoogleAuthRequest, request: Request, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    if not req.email:
        raise HTTPException(status_code=400, detail="Google authentication failed to provide a valid email.")

    clean_email = req.email.lower().strip()
    provider_sub = req.provider_user_id or f"google-sub-{uuid.uuid4().hex[:8]}"
    
    # Check if account exists
    user = get_user_by_email(db, clean_email)
    if not user:
        user_id = "USR-" + uuid.uuid4().hex[:8].upper()
        user = create_user(
            db=db,
            user_id=user_id,
            email=clean_email,
            password_plain=secrets.token_urlsafe(24),
            full_name=req.full_name or clean_email.split("@")[0].capitalize(),
            role="USER",
            email_verified=True
        )
        log_activity(db, "google_account_created", user_id=user.id, user_email=user.email, ip_address=ip)
    else:
        # Ensure email is marked verified since verified by Google Identity
        if not user.email_verified:
            mark_user_email_verified(db, user.id)

    # Link OAuth account record
    link_oauth_account(db, user_id=user.id, provider="google", provider_user_id=provider_sub, provider_email=clean_email)

    # If user has 2FA enabled on Nova, enforce Nova 2FA after Google OAuth
    if user.two_factor_enabled:
        temp_token = create_2fa_challenge_token(user.id, user.email, user.two_factor_method or "totp")
        log_activity(db, "google_login_2fa_required", user_id=user.id, user_email=user.email, ip_address=ip)
        return AuthTokenResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            requires_2fa=True,
            temp_token=temp_token,
            two_factor_method=user.two_factor_method or "totp",
            message="Two-step verification required."
        )

    update_user_last_login(db, user.id)
    session_token = generate_session_token()
    create_user_session(db, user.id, session_token=session_token, device_info=get_device_info(request), ip_address=ip)

    log_activity(db, "google_login_success", user_id=user.id, user_email=user.email, ip_address=ip)
    token = create_access_token(subject=user.id, role=user.role, session_id=session_token)

    return AuthTokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        message="Successfully authenticated with Google."
    )


# ─── 2FA Management Endpoints ─────────────────────────────────────────────────

@app.post("/api/v1/auth/2fa/setup", response_model=TwoFactorSetupResponse)
def setup_two_factor(current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    secret = generate_totp_secret()
    set_user_totp_secret(db, current_user.id, secret)
    uri = get_totp_uri(secret, current_user.email, issuer_name="Nova Credit AI")
    qr_data_url = generate_qr_code_data_url(uri)
    return TwoFactorSetupResponse(
        secret=secret,
        otpauth_uri=uri,
        qr_code_data_url=qr_data_url
    )


@app.post("/api/v1/auth/2fa/confirm")
def confirm_two_factor(req: TwoFactorConfirmRequest, request: Request, current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="Two-factor enrollment not initiated. Run setup first.")

    if not verify_totp_code(current_user.totp_secret, req.code):
        raise HTTPException(status_code=400, detail="Invalid verification code. Check the time on your authenticator app.")

    enable_user_2fa(db, current_user.id, method="totp")
    plain_codes, hashed_codes = generate_recovery_codes(count=8)
    save_user_recovery_codes(db, current_user.id, hashed_codes)

    log_activity(db, "2fa_enabled", user_id=current_user.id, user_email=current_user.email, ip_address=get_client_ip(request))

    return {
        "message": "Two-factor authentication successfully enabled.",
        "recovery_codes": plain_codes
    }


@app.post("/api/v1/auth/2fa/disable")
def disable_two_factor(req: TwoFactorDisableRequest, request: Request, current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.two_factor_enabled:
        return {"message": "Two-factor authentication is already disabled."}

    # Verify either current password or valid TOTP code
    is_valid = False
    if req.password and verify_password(req.password, current_user.password_hash):
        is_valid = True
    elif req.code and current_user.totp_secret and verify_totp_code(current_user.totp_secret, req.code):
        is_valid = True

    if not is_valid:
        raise HTTPException(status_code=400, detail="Current password or authenticator code required to disable 2FA.")

    disable_user_2fa(db, current_user.id)
    log_activity(db, "2fa_disabled", user_id=current_user.id, user_email=current_user.email, ip_address=get_client_ip(request))
    return {"message": "Two-factor authentication has been disabled."}


# ─── Sessions & Security Settings Endpoints ───────────────────────────────────

@app.get("/api/v1/auth/security-settings", response_model=SecuritySettingsResponse)
def get_security_settings(
    authorization: Optional[str] = Header(None),
    current_user: UserRecord = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sessions = get_active_sessions(db, current_user.id)
    current_sess_id = None
    if authorization and authorization.startswith("Bearer "):
        token_payload = decode_access_token(authorization.split(" ")[1])
        if token_payload:
            current_sess_id = token_payload.get("session_id")

    google_linked = bool(get_oauth_account(db, "google", current_user.id) or any(oa.provider == "google" for oa in current_user.oauth_accounts))
    
    session_responses = [
        UserSessionResponse(
            id=s.id,
            device_info=s.device_info,
            ip_address=s.ip_address,
            last_active_at=s.last_active_at,
            expires_at=s.expires_at,
            is_current=(s.session_token == current_sess_id or s.id == current_sess_id)
        )
        for s in sessions
    ]

    return SecuritySettingsResponse(
        two_factor_enabled=current_user.two_factor_enabled,
        two_factor_method=current_user.two_factor_method,
        has_google_linked=google_linked,
        active_sessions=session_responses
    )


@app.get("/api/v1/auth/sessions", response_model=List[UserSessionResponse])
def list_sessions(current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = get_active_sessions(db, current_user.id)
    return [
        UserSessionResponse(
            id=s.id,
            device_info=s.device_info,
            ip_address=s.ip_address,
            last_active_at=s.last_active_at,
            expires_at=s.expires_at,
            is_current=False
        )
        for s in sessions
    ]


@app.delete("/api/v1/auth/sessions/{session_id}")
def revoke_session(session_id: str, request: Request, current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    success = revoke_user_session(db, current_user.id, session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found.")
    log_activity(db, "session_revoked", user_id=current_user.id, user_email=current_user.email, resource_id=session_id, ip_address=get_client_ip(request))
    return {"message": "Session revoked."}


@app.post("/api/v1/auth/logout-all")
def logout_all_sessions(request: Request, current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    revoke_all_user_sessions(db, current_user.id)
    log_activity(db, "all_sessions_revoked", user_id=current_user.id, user_email=current_user.email, ip_address=get_client_ip(request))
    return {"message": "All active sessions have been terminated."}


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
        two_factor_enabled=current_user.two_factor_enabled,
        two_factor_method=current_user.two_factor_method,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
    )


@app.post("/api/v1/auth/forgot-password")
def forgot_password(req: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    user = get_user_by_email(db, req.email)
    if user:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hash_otp_code(raw_token)
        create_password_reset_token(db, user.id, token_hash=token_hash, expiry_minutes=30)
        logger.info(f"🔑 [Password Reset Token] For {user.email}: {raw_token}")
        log_activity(db, "password_reset_requested", user_id=user.id, user_email=user.email, ip_address=get_client_ip(request))
    return {"message": "If an account with that email exists, password reset instructions have been dispatched."}


@app.post("/api/v1/auth/reset-password")
def reset_password(req: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    user = get_user_by_email(db, req.email)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid password reset request.")

    token_hash = hash_otp_code(req.reset_token)
    if not verify_and_consume_password_reset_token(db, user.id, token_hash):
        raise HTTPException(status_code=400, detail="Password reset token is invalid or has expired.")

    update_user_password(db, user.id, req.new_password)
    revoke_all_user_sessions(db, user.id)
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
    tenure_m = req.tenure_months or (req.tenure_years * 12 if req.tenure_years else 36)
    
    result = generate_amortization_schedule(
        principal=req.principal,
        annual_rate=req.annual_rate,
        tenure_months=tenure_m,
        down_payment=req.down_payment or 0.0,
        processing_fee_val=req.processing_fee_val or 0.0,
        processing_fee_type=req.processing_fee_type or "percentage"
    )
    
    summary = result["summary"]
    
    insight_text = (
        f"Your requested {summary['tenure_months']}-month loan of ₹{summary['net_principal']:,.0f} at {summary['annual_rate']}% p.a. "
        f"results in a monthly EMI of ₹{summary['monthly_emi']:,.0f}. Over the full term, total interest is ₹{summary['total_interest']:,.0f} "
        f"({summary['interest_to_principal_ratio']:.1f}% of net principal), with an effective total borrowing cost of ₹{summary['effective_total_cost']:,.0f}."
    )
    
    return {
        "monthly_emi": summary["monthly_emi"],
        "total_payment": summary["total_repayment"],
        "total_interest": summary["total_interest"],
        "principal": summary["net_principal"],
        "gross_loan_amount": summary["gross_loan_amount"],
        "down_payment": summary["down_payment"],
        "net_principal": summary["net_principal"],
        "tenure_months": summary["tenure_months"],
        "processing_fee": summary["processing_fee"],
        "effective_total_cost": summary["effective_total_cost"],
        "interest_to_principal_ratio": summary["interest_to_principal_ratio"],
        "start_date": summary["start_date"],
        "end_date": summary["end_date"],
        "schedule": result["monthly_schedule"],
        "yearly_schedule": result["yearly_schedule"],
        "nova_insight": insight_text
    }


@app.post("/api/v1/loans/affordability")
def check_loan_affordability(
    req: LoanAffordabilityRequest,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
):
    inc = req.monthly_income
    ex_emi = req.existing_emi
    
    # Auto-load financial profile if income or existing EMI is not specified
    if inc == 0.0:
        fp = get_financial_profile(db, current_user.id)
        if fp:
            inc = fp.monthly_income
            if ex_emi == 0.0:
                ex_emi = fp.existing_emi
                
    result = evaluate_affordability(
        monthly_income=inc,
        proposed_emi=req.proposed_emi,
        existing_emi=ex_emi,
        housing_rent=req.housing_rent or 0.0,
        other_fixed_obligations=req.other_fixed_obligations or 0.0,
        essential_expenses=req.essential_expenses or 0.0,
        dependents=req.dependents or 0
    )
    return result


@app.post("/api/v1/loans/optimize-tenure")
def optimize_loan_tenure(
    req: TenureOptimizeRequest,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
):
    inc = req.monthly_income or 0.0
    ex_fix = req.existing_fixed_obligations or 0.0
    
    if inc == 0.0:
        fp = get_financial_profile(db, current_user.id)
        if fp:
            inc = fp.monthly_income
            if ex_fix == 0.0:
                ex_fix = fp.existing_emi

    result = optimize_tenures(
        principal=req.principal,
        annual_rate=req.annual_rate,
        down_payment=req.down_payment or 0.0,
        processing_fee_val=req.processing_fee_val or 0.0,
        processing_fee_type=req.processing_fee_type or "percentage",
        monthly_income=inc,
        existing_fixed_obligations=ex_fix,
        target_tenure_months=req.target_tenure_months or 36
    )
    return result


@app.post("/api/v1/loans/prepayment")
def calculate_prepayment_simulation(
    req: LoanPrepaymentRequest,
    current_user: UserRecord = Depends(get_current_user)
):
    result = simulate_prepayment(
        principal=req.principal,
        annual_rate=req.annual_rate,
        tenure_months=req.tenure_months,
        prepayment_amount=req.prepayment_amount or 0.0,
        prepayment_month=req.prepayment_month or 12,
        strategy=req.strategy or "reduce_tenure",
        extra_monthly_payment=req.extra_monthly_payment or 0.0,
        start_date_str=req.start_date
    )
    return result


@app.post("/api/v1/loans/compare")
def compare_offers(
    req: LoanCompareRequest,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
):
    inc = req.monthly_income or 0.0
    ex_fix = req.existing_fixed_obligations or 0.0
    
    if inc == 0.0:
        fp = get_financial_profile(db, current_user.id)
        if fp:
            inc = fp.monthly_income
            if ex_fix == 0.0:
                ex_fix = fp.existing_emi

    raw_offers = [o.model_dump() for o in req.offers]
    result = compare_loan_offers(
        offers=raw_offers,
        monthly_income=inc,
        existing_fixed_obligations=ex_fix
    )
    return result


@app.get("/api/v1/loans/scenarios")
def list_user_scenarios(
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
):
    is_admin = (current_user.role.upper() == "ADMIN")
    scenarios = get_user_loan_scenarios(db, user_id=current_user.id, is_admin=is_admin, limit=50)
    return {"scenarios": scenarios}


@app.post("/api/v1/loans/scenarios")
def save_user_scenario(
    req: LoanScenarioCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
):
    data = req.model_dump()
    saved = save_loan_scenario(db, user_id=current_user.id, scenario_data=data)
    
    log_activity(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="SAVE_LOAN_SCENARIO",
        resource_type="LOAN_SCENARIO",
        resource_id=saved["id"],
        details={"scenario_name": saved["scenario_name"], "principal": saved["principal"], "emi": saved["monthly_emi"]},
        ip_address=get_client_ip(request)
    )
    return saved


@app.get("/api/v1/loans/scenarios/{scenario_id}")
def get_single_scenario(
    scenario_id: str,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
):
    is_admin = (current_user.role.upper() == "ADMIN")
    scen = get_loan_scenario_by_id(db, scenario_id=scenario_id, user_id=current_user.id, is_admin=is_admin)
    if not scen:
        raise HTTPException(status_code=404, detail="Loan scenario not found or unauthorized.")
    return scen


@app.delete("/api/v1/loans/scenarios/{scenario_id}")
def delete_single_scenario(
    scenario_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user)
):
    is_admin = (current_user.role.upper() == "ADMIN")
    success = delete_loan_scenario(db, scenario_id=scenario_id, user_id=current_user.id, is_admin=is_admin)
    if not success:
        raise HTTPException(status_code=404, detail="Loan scenario not found or unauthorized.")
        
    log_activity(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DELETE_LOAN_SCENARIO",
        resource_type="LOAN_SCENARIO",
        resource_id=scenario_id,
        ip_address=get_client_ip(request)
    )
    return {"message": "Scenario deleted successfully.", "id": scenario_id}



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

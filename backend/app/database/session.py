"""
SQLAlchemy database session and ORM models — SQLite (dev) / PostgreSQL (prod).
Implements multi-tenant user isolation, role-based access control (RBAC),
financial profiles, credit assessments, loan simulations, report tracking, and activity audit logging.
"""
import os
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean, Text, ForeignKey, desc
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from backend.app.core.config import get_settings
from backend.app.core.security import hash_password

settings = get_settings()

# Ensure directory for SQLite DB exists if using file path
if "sqlite" in settings.DATABASE_URL:
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    if "./" in db_path:
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─── ORM Models ───────────────────────────────────────────────────────────────

class UserRecord(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(32), default="USER", nullable=False)   # "USER" | "ADMIN"
    is_active = Column(Boolean, default=True, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(String(64), nullable=True)
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    two_factor_method = Column(String(32), default="totp", nullable=False)  # "totp" | "email_otp"
    totp_secret = Column(String(255), nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(String(64), nullable=True)
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)
    last_login_at = Column(String(64), nullable=True)

    # Relationships
    assessments = relationship("CreditAssessmentRecord", back_populates="user", cascade="all, delete-orphan")
    financial_profile = relationship("FinancialProfileRecord", back_populates="user", uselist=False, cascade="all, delete-orphan")
    simulations = relationship("LoanSimulationRecord", back_populates="user", cascade="all, delete-orphan")
    loan_scenarios = relationship("LoanScenarioRecord", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("ReportRecord", back_populates="user", cascade="all, delete-orphan")
    activities = relationship("ActivityLog", back_populates="user", cascade="all, delete-orphan")
    recovery_codes = relationship("TwoFactorRecoveryCode", back_populates="user", cascade="all, delete-orphan")
    oauth_accounts = relationship("OAuthAccount", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")


class EmailVerificationChallenge(Base):
    __tablename__ = "email_verification_challenges"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    code_hash = Column(String(255), nullable=False)
    expires_at = Column(String(64), nullable=False)
    attempts_left = Column(Integer, default=5, nullable=False)
    resend_cooldown_until = Column(String(64), nullable=False)
    consumed = Column(Boolean, default=False, nullable=False)
    created_at = Column(String(64), nullable=False)


class TwoFactorRecoveryCode(Base):
    __tablename__ = "two_factor_recovery_codes"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash = Column(String(255), nullable=False, index=True)
    used = Column(Boolean, default=False, nullable=False)
    used_at = Column(String(64), nullable=True)
    created_at = Column(String(64), nullable=False)

    user = relationship("UserRecord", back_populates="recovery_codes")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, index=True)
    expires_at = Column(String(64), nullable=False)
    consumed = Column(Boolean, default=False, nullable=False)
    created_at = Column(String(64), nullable=False)


class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(64), nullable=False, index=True)  # e.g. "google"
    provider_user_id = Column(String(255), nullable=False, index=True)
    provider_email = Column(String(255), nullable=False)
    created_at = Column(String(64), nullable=False)

    user = relationship("UserRecord", back_populates="oauth_accounts")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token = Column(String(255), unique=True, index=True, nullable=False)
    device_info = Column(String(255), default="Web Browser", nullable=False)
    ip_address = Column(String(64), default="127.0.0.1", nullable=False)
    last_active_at = Column(String(64), nullable=False)
    expires_at = Column(String(64), nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(String(64), nullable=False)

    user = relationship("UserRecord", back_populates="sessions")


class FinancialProfileRecord(Base):
    __tablename__ = "financial_profiles"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    monthly_income = Column(Float, default=50000.0, nullable=False)
    existing_emi = Column(Float, default=0.0, nullable=False)
    savings_balance = Column(Float, default=100000.0, nullable=False)
    housing_type = Column(String(64), default="own", nullable=False)
    employment_status = Column(String(64), default="skilled", nullable=False)
    credit_purpose = Column(String(64), default="personal", nullable=False)
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)

    user = relationship("UserRecord", back_populates="financial_profile")


class CreditAssessmentRecord(Base):
    __tablename__ = "credit_assessments"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    applicant_name = Column(String(255), nullable=False)
    applicant_age = Column(Integer, nullable=False)
    monthly_income = Column(Float, nullable=False)
    requested_loan = Column(Float, nullable=False)
    tenure_months = Column(Integer, nullable=False)
    nova_score = Column(Integer, nullable=False)
    risk_tier = Column(String(64), nullable=False)
    approval_probability = Column(Float, nullable=False)
    decision = Column(String(64), nullable=False)
    foir_ratio = Column(Float, nullable=False)
    dti_ratio = Column(Float, nullable=False)
    raw_payload = Column(Text, nullable=False)
    result_payload = Column(Text, nullable=False)
    model_version = Column(String(64), default="v2.2-CatBoost", nullable=False)
    created_at = Column(String(64), nullable=False)

    user = relationship("UserRecord", back_populates="assessments")
    reports = relationship("ReportRecord", back_populates="assessment", cascade="all, delete-orphan")


class LoanSimulationRecord(Base):
    __tablename__ = "loan_simulations"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    monthly_income = Column(Float, nullable=False)
    requested_amount = Column(Float, nullable=False)
    tenure_months = Column(Integer, nullable=False)
    simulated_nova_score = Column(Integer, nullable=False)
    simulated_approval_pct = Column(Float, nullable=False)
    decision = Column(String(64), nullable=False)
    inputs_json = Column(Text, nullable=False)
    outputs_json = Column(Text, nullable=False)
    created_at = Column(String(64), nullable=False)

    user = relationship("UserRecord", back_populates="simulations")


class LoanScenarioRecord(Base):
    __tablename__ = "loan_scenarios"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_name = Column(String(255), nullable=False)
    loan_type = Column(String(64), default="Personal Loan", nullable=False)
    principal = Column(Float, nullable=False)
    annual_rate = Column(Float, nullable=False)
    tenure_months = Column(Integer, nullable=False)
    processing_fee = Column(Float, default=0.0, nullable=False)
    down_payment = Column(Float, default=0.0, nullable=False)
    monthly_emi = Column(Float, nullable=False)
    total_interest = Column(Float, nullable=False)
    total_repayment = Column(Float, nullable=False)
    effective_total_cost = Column(Float, nullable=False)
    foir = Column(Float, default=0.0, nullable=False)
    affordability_result = Column(String(64), default="Comfortable", nullable=False)
    inputs_json = Column(Text, nullable=False)
    outputs_json = Column(Text, nullable=False)
    created_at = Column(String(64), nullable=False)

    user = relationship("UserRecord", back_populates="loan_scenarios")


class ReportRecord(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assessment_id = Column(String(36), ForeignKey("credit_assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    applicant_name = Column(String(255), nullable=False)
    report_type = Column(String(64), default="PDF_ASSESSMENT", nullable=False)
    created_at = Column(String(64), nullable=False)

    user = relationship("UserRecord", back_populates="reports")
    assessment = relationship("CreditAssessmentRecord", back_populates="reports")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user_email = Column(String(255), nullable=True)
    action = Column(String(64), nullable=False, index=True)
    resource_type = Column(String(64), nullable=True)
    resource_id = Column(String(64), nullable=True)
    timestamp = Column(String(64), nullable=False, index=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)

    user = relationship("UserRecord", back_populates="activities")


# ─── Database Dependency ──────────────────────────────────────────────────────

def get_db():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Database Initialization & Bootstrap ──────────────────────────────────────

def init_db():
    """Initializes tables and optionally bootstraps the administrator account if configured via env."""
    Base.metadata.create_all(bind=engine)

    # SQLite schema auto-migration for newly added columns
    try:
        with engine.connect() as conn:
            # Check users table columns
            cursor = conn.exec_driver_sql("PRAGMA table_info(users)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            
            col_defs = [
                ("email_verified", "BOOLEAN DEFAULT 0 NOT NULL"),
                ("email_verified_at", "VARCHAR(64)"),
                ("two_factor_enabled", "BOOLEAN DEFAULT 0 NOT NULL"),
                ("two_factor_method", "VARCHAR(32) DEFAULT 'totp' NOT NULL"),
                ("totp_secret", "VARCHAR(255)"),
                ("failed_login_attempts", "INTEGER DEFAULT 0 NOT NULL"),
                ("locked_until", "VARCHAR(64)"),
            ]
            for col_name, col_type in col_defs:
                if col_name not in existing_cols:
                    conn.exec_driver_sql(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            conn.commit()
    except Exception as e:
        pass

    # Optional initial admin bootstrap from environment variables
    admin_email = getattr(settings, "ADMIN_BOOTSTRAP_EMAIL", None) or os.getenv("ADMIN_BOOTSTRAP_EMAIL")
    admin_password = getattr(settings, "ADMIN_BOOTSTRAP_PASSWORD", None) or os.getenv("ADMIN_BOOTSTRAP_PASSWORD")

    if admin_email and admin_password:
        db = SessionLocal()
        try:
            admin_user = db.query(UserRecord).filter(UserRecord.email == admin_email.lower().strip()).first()
            if not admin_user:
                now_str = datetime.now(timezone.utc).isoformat()
                admin_record = UserRecord(
                    id="ADMIN-" + uuid.uuid4().hex[:8].upper(),
                    email=admin_email.lower().strip(),
                    password_hash=hash_password(admin_password),
                    full_name="System Administrator",
                    role="ADMIN",
                    is_active=True,
                    email_verified=True,
                    created_at=now_str,
                    updated_at=now_str,
                )
                db.add(admin_record)
                db.commit()
        except Exception as e:
            db.rollback()
        finally:
            db.close()


# ─── User Repository Helpers ──────────────────────────────────────────────────

def get_user_by_email(db: Session, email: str) -> Optional[UserRecord]:
    if not email:
        return None
    return db.query(UserRecord).filter(UserRecord.email == email.lower().strip()).first()


def get_user_by_id(db: Session, user_id: str) -> Optional[UserRecord]:
    if not user_id:
        return None
    return db.query(UserRecord).filter(UserRecord.id == user_id).first()


def create_user(
    db: Session,
    user_id: str,
    email: str,
    password_plain: str,
    full_name: str,
    role: str = "USER",
    email_verified: bool = False
) -> UserRecord:
    now_str = datetime.now(timezone.utc).isoformat()
    # Normalize role to uppercase
    clean_role = "ADMIN" if role.upper() == "ADMIN" else "USER"
    user = UserRecord(
        id=user_id,
        email=email.lower().strip(),
        password_hash=hash_password(password_plain),
        full_name=full_name.strip(),
        role=clean_role,
        is_active=True,
        email_verified=email_verified,
        email_verified_at=now_str if email_verified else None,
        created_at=now_str,
        updated_at=now_str,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Initialize default financial profile for user
    profile = FinancialProfileRecord(
        id="FP-" + uuid.uuid4().hex[:8].upper(),
        user_id=user.id,
        monthly_income=50000.0,
        existing_emi=0.0,
        savings_balance=100000.0,
        housing_type="own",
        employment_status="skilled",
        credit_purpose="personal",
        created_at=now_str,
        updated_at=now_str,
    )
    db.add(profile)
    db.commit()

    return user


def update_user_last_login(db: Session, user_id: str):
    user = get_user_by_id(db, user_id)
    if user:
        user.last_login_at = datetime.now(timezone.utc).isoformat()
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()


# ─── Account Lockout & Brute-Force Tracking ────────────────────────────────────

def record_login_failure(db: Session, user: UserRecord, max_attempts: int = 5, lock_minutes: int = 15) -> Tuple[int, Optional[str]]:
    """Increments failed login counter and locks account if threshold exceeded. Returns (attempts, locked_until_iso)."""
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= max_attempts:
        lock_until = datetime.now(timezone.utc) + timedelta(minutes=lock_minutes)
        user.locked_until = lock_until.isoformat()
    db.commit()
    return user.failed_login_attempts, user.locked_until


def is_account_locked(user: UserRecord) -> Tuple[bool, int]:
    """Returns (is_locked: bool, minutes_remaining: int)."""
    if not user.locked_until:
        return False, 0
    try:
        lock_time = datetime.fromisoformat(user.locked_until)
        now = datetime.now(timezone.utc)
        if now < lock_time:
            remaining = int((lock_time - now).total_seconds() / 60) + 1
            return True, remaining
    except Exception:
        pass
    return False, 0


# ─── Email Verification Challenge Operations ──────────────────────────────────

def create_email_verification_challenge(
    db: Session,
    user_id: str,
    email: str,
    code_hash: str,
    expiry_minutes: int = 10,
    cooldown_seconds: int = 45
) -> EmailVerificationChallenge:
    """Invalidates old unconsumed challenges for this email and creates a fresh one."""
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    expires_str = (now + timedelta(minutes=expiry_minutes)).isoformat()
    cooldown_str = (now + timedelta(seconds=cooldown_seconds)).isoformat()

    # Invalidate previous unconsumed challenges
    db.query(EmailVerificationChallenge).filter(
        EmailVerificationChallenge.email == email.lower().strip(),
        EmailVerificationChallenge.consumed == False
    ).update({"consumed": True})

    challenge = EmailVerificationChallenge(
        id="CHAL-" + uuid.uuid4().hex[:8].upper(),
        user_id=user_id,
        email=email.lower().strip(),
        code_hash=code_hash,
        expires_at=expires_str,
        attempts_left=5,
        resend_cooldown_until=cooldown_str,
        consumed=False,
        created_at=now_str,
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge


def get_active_email_challenge(db: Session, email: str) -> Optional[EmailVerificationChallenge]:
    now_str = datetime.now(timezone.utc).isoformat()
    return db.query(EmailVerificationChallenge).filter(
        EmailVerificationChallenge.email == email.lower().strip(),
        EmailVerificationChallenge.consumed == False,
        EmailVerificationChallenge.expires_at > now_str,
        EmailVerificationChallenge.attempts_left > 0
    ).order_by(desc(EmailVerificationChallenge.created_at)).first()


def mark_user_email_verified(db: Session, user_id: str) -> bool:
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    user.email_verified = True
    user.email_verified_at = datetime.now(timezone.utc).isoformat()
    user.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    return True


# ─── Two-Factor Authentication & Recovery Codes ───────────────────────────────

def set_user_totp_secret(db: Session, user_id: str, secret: str):
    user = get_user_by_id(db, user_id)
    if user:
        user.totp_secret = secret
        user.updated_at = datetime.now(timezone.utc).isoformat()
        db.commit()


def enable_user_2fa(db: Session, user_id: str, method: str = "totp") -> bool:
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    user.two_factor_enabled = True
    user.two_factor_method = method
    user.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    return True


def disable_user_2fa(db: Session, user_id: str) -> bool:
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    user.two_factor_enabled = False
    user.totp_secret = None
    user.updated_at = datetime.now(timezone.utc).isoformat()
    # Delete unused recovery codes
    db.query(TwoFactorRecoveryCode).filter(TwoFactorRecoveryCode.user_id == user_id).delete()
    db.commit()
    return True


def save_user_recovery_codes(db: Session, user_id: str, hashed_codes: List[str]):
    # Invalidate previous unused recovery codes
    db.query(TwoFactorRecoveryCode).filter(TwoFactorRecoveryCode.user_id == user_id).delete()
    now_str = datetime.now(timezone.utc).isoformat()
    for h in hashed_codes:
        rec = TwoFactorRecoveryCode(
            id="REC-" + uuid.uuid4().hex[:8].upper(),
            user_id=user_id,
            code_hash=h,
            used=False,
            created_at=now_str,
        )
        db.add(rec)
    db.commit()


def verify_and_consume_recovery_code(db: Session, user_id: str, code_hash: str) -> bool:
    rec = db.query(TwoFactorRecoveryCode).filter(
        TwoFactorRecoveryCode.user_id == user_id,
        TwoFactorRecoveryCode.code_hash == code_hash,
        TwoFactorRecoveryCode.used == False
    ).first()
    if not rec:
        return False
    rec.used = True
    rec.used_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    return True


# ─── Password Reset Tokens ────────────────────────────────────────────────────

def create_password_reset_token(db: Session, user_id: str, token_hash: str, expiry_minutes: int = 30) -> PasswordResetToken:
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    expires_str = (now + timedelta(minutes=expiry_minutes)).isoformat()

    # Invalidate old tokens
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user_id,
        PasswordResetToken.consumed == False
    ).update({"consumed": True})

    token_rec = PasswordResetToken(
        id="RST-" + uuid.uuid4().hex[:8].upper(),
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_str,
        consumed=False,
        created_at=now_str,
    )
    db.add(token_rec)
    db.commit()
    db.refresh(token_rec)
    return token_rec


def verify_and_consume_password_reset_token(db: Session, user_id: str, token_hash: str) -> bool:
    now_str = datetime.now(timezone.utc).isoformat()
    rec = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user_id,
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.consumed == False,
        PasswordResetToken.expires_at > now_str
    ).first()
    if not rec:
        return False
    rec.consumed = True
    db.commit()
    return True


# ─── OAuth Account Operations ─────────────────────────────────────────────────

def get_oauth_account(db: Session, provider: str, provider_user_id: str) -> Optional[OAuthAccount]:
    return db.query(OAuthAccount).filter(
        OAuthAccount.provider == provider.lower().strip(),
        OAuthAccount.provider_user_id == str(provider_user_id).strip()
    ).first()


def link_oauth_account(db: Session, user_id: str, provider: str, provider_user_id: str, provider_email: str) -> OAuthAccount:
    existing = db.query(OAuthAccount).filter(
        OAuthAccount.provider == provider.lower().strip(),
        OAuthAccount.provider_user_id == str(provider_user_id).strip()
    ).first()
    if existing:
        return existing
    now_str = datetime.now(timezone.utc).isoformat()
    oauth_acc = OAuthAccount(
        id="OA-" + uuid.uuid4().hex[:8].upper(),
        user_id=user_id,
        provider=provider.lower().strip(),
        provider_user_id=str(provider_user_id).strip(),
        provider_email=provider_email.lower().strip(),
        created_at=now_str,
    )
    db.add(oauth_acc)
    db.commit()
    db.refresh(oauth_acc)
    return oauth_acc


# ─── User Sessions & Multi-Device Management ──────────────────────────────────

def create_user_session(
    db: Session,
    user_id: str,
    session_token: str,
    device_info: str = "Web Browser",
    ip_address: str = "127.0.0.1",
    expiry_days: int = 30
) -> UserSession:
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    expires_str = (now + timedelta(days=expiry_days)).isoformat()
    session_rec = UserSession(
        id="SESS-" + uuid.uuid4().hex[:8].upper(),
        user_id=user_id,
        session_token=session_token,
        device_info=device_info,
        ip_address=ip_address,
        last_active_at=now_str,
        expires_at=expires_str,
        is_revoked=False,
        created_at=now_str,
    )
    db.add(session_rec)
    db.commit()
    db.refresh(session_rec)
    return session_rec


def get_active_sessions(db: Session, user_id: str) -> List[UserSession]:
    now_str = datetime.now(timezone.utc).isoformat()
    return db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.is_revoked == False,
        UserSession.expires_at > now_str
    ).order_by(desc(UserSession.last_active_at)).all()


def revoke_user_session(db: Session, user_id: str, session_id: str) -> bool:
    sess = db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.user_id == user_id
    ).first()
    if not sess:
        return False
    sess.is_revoked = True
    db.commit()
    return True


def revoke_all_user_sessions(db: Session, user_id: str, except_session_token: Optional[str] = None):
    q = db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.is_revoked == False
    )
    if except_session_token:
        q = q.filter(UserSession.session_token != except_session_token)
    q.update({"is_revoked": True})
    db.commit()



def update_user_password(db: Session, user_id: str, new_password_plain: str) -> bool:
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    user.password_hash = hash_password(new_password_plain)
    user.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    return True


def update_user_profile(db: Session, user_id: str, full_name: str, email: str = None) -> Optional[UserRecord]:
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    if full_name:
        user.full_name = full_name.strip()
    if email:
        user.email = email.lower().strip()
    user.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(user)
    return user


def toggle_user_status(db: Session, user_id: str, is_active: bool) -> Optional[UserRecord]:
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    user.is_active = is_active
    user.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(user)
    return user


def get_all_users(
    db: Session,
    search: Optional[str] = None,
    role: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[UserRecord]:
    query = db.query(UserRecord)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            (UserRecord.email.ilike(s)) |
            (UserRecord.full_name.ilike(s)) |
            (UserRecord.id.ilike(s))
        )
    if role:
        query = query.filter(UserRecord.role == role.upper())
    return query.order_by(desc(UserRecord.created_at)).offset(offset).limit(limit).all()


def count_users(db: Session) -> int:
    return db.query(UserRecord).count()


# ─── Financial Profile Helpers ────────────────────────────────────────────────

def get_financial_profile(db: Session, user_id: str) -> Optional[FinancialProfileRecord]:
    return db.query(FinancialProfileRecord).filter(FinancialProfileRecord.user_id == user_id).first()


def save_or_update_financial_profile(db: Session, user_id: str, data: dict) -> FinancialProfileRecord:
    profile = get_financial_profile(db, user_id)
    now_str = datetime.now(timezone.utc).isoformat()
    if not profile:
        profile = FinancialProfileRecord(
            id="FP-" + uuid.uuid4().hex[:8].upper(),
            user_id=user_id,
            monthly_income=float(data.get("monthly_income", 50000)),
            existing_emi=float(data.get("existing_emi", 0)),
            savings_balance=float(data.get("savings_balance", 100000)),
            housing_type=str(data.get("housing_type", "own")),
            employment_status=str(data.get("employment_status", "skilled")),
            credit_purpose=str(data.get("credit_purpose", "personal")),
            created_at=now_str,
            updated_at=now_str,
        )
        db.add(profile)
    else:
        if "monthly_income" in data:
            profile.monthly_income = float(data["monthly_income"])
        if "existing_emi" in data:
            profile.existing_emi = float(data["existing_emi"])
        if "savings_balance" in data:
            profile.savings_balance = float(data["savings_balance"])
        if "housing_type" in data:
            profile.housing_type = str(data["housing_type"])
        if "employment_status" in data:
            profile.employment_status = str(data["employment_status"])
        if "credit_purpose" in data:
            profile.credit_purpose = str(data["credit_purpose"])
        profile.updated_at = now_str

    db.commit()
    db.refresh(profile)
    return profile


# ─── Credit Assessment Helpers ────────────────────────────────────────────────

def save_assessment_orm(
    db: Session,
    assessment_id: str,
    applicant_name: str,
    payload: dict,
    result: dict,
    user_id: str
) -> CreditAssessmentRecord:
    now_str = datetime.now(timezone.utc).isoformat()
    record = CreditAssessmentRecord(
        id=assessment_id,
        user_id=user_id,
        applicant_name=applicant_name,
        applicant_age=int(payload.get("age", 30)),
        monthly_income=float(payload.get("monthly_income", 50000)),
        requested_loan=float(payload.get("credit_amount", 100000)),
        tenure_months=int(payload.get("duration", 12)),
        nova_score=int(result.get("nova_score", {}).get("nova_score", 700)),
        risk_tier=str(result.get("nova_score", {}).get("tier", "Strong")),
        approval_probability=float(result.get("approval_probability", 0.75)),
        decision=str(result.get("decision_engine", {}).get("decision", "Likely Eligible")),
        foir_ratio=float(result.get("decision_engine", {}).get("foir_ratio", 0.3)),
        dti_ratio=float(result.get("decision_engine", {}).get("dti_ratio", 0.2)),
        raw_payload=json.dumps(payload),
        result_payload=json.dumps(result),
        model_version="v2.2-CatBoost",
        created_at=now_str,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_assessment_by_id(
    db: Session,
    assessment_id: str,
    user_id: Optional[str] = None,
    is_admin: bool = False
) -> Optional[dict]:
    query = db.query(CreditAssessmentRecord).filter(CreditAssessmentRecord.id == assessment_id)
    if not is_admin and user_id:
        query = query.filter(CreditAssessmentRecord.user_id == user_id)
    record = query.first()
    if record:
        res = json.loads(record.result_payload)
        res["id"] = record.id
        res["user_id"] = record.user_id
        res["created_at"] = record.created_at
        return res
    return None


def get_history(
    db: Session,
    user_id: Optional[str] = None,
    is_admin: bool = False,
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None
) -> List[Dict[str, Any]]:
    query = db.query(CreditAssessmentRecord)
    if not is_admin:
        if not user_id:
            return []  # Strict isolation: Unauthenticated sessions receive empty list
        query = query.filter(CreditAssessmentRecord.user_id == user_id)
    elif user_id:
        query = query.filter(CreditAssessmentRecord.user_id == user_id)

    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            (CreditAssessmentRecord.applicant_name.ilike(s)) |
            (CreditAssessmentRecord.id.ilike(s))
        )

    rows = query.order_by(desc(CreditAssessmentRecord.created_at)).offset(offset).limit(limit).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "timestamp": r.created_at,
            "applicant_name": r.applicant_name,
            "applicant_age": r.applicant_age,
            "monthly_income": r.monthly_income,
            "requested_loan": r.requested_loan,
            "tenure_months": r.tenure_months,
            "nova_score": r.nova_score,
            "risk_tier": r.risk_tier,
            "approval_probability": round((r.approval_probability or 0.75) * 100, 1),
            "decision": r.decision,
            "foir_ratio": round((r.foir_ratio or 0.3) * 100, 1),
            "dti_ratio": round((r.dti_ratio or 0.2) * 100, 1),
            "model_version": r.model_version,
        }
        for r in rows
    ]


def count_assessments(db: Session, user_id: Optional[str] = None) -> int:
    query = db.query(CreditAssessmentRecord)
    if user_id:
        query = query.filter(CreditAssessmentRecord.user_id == user_id)
    return query.count()


# ─── Loan Simulation Helpers ──────────────────────────────────────────────────

def save_loan_simulation(db: Session, user_id: str, inputs: dict, outputs: dict) -> LoanSimulationRecord:
    now_str = datetime.now(timezone.utc).isoformat()
    record = LoanSimulationRecord(
        id="SIM-" + uuid.uuid4().hex[:8].upper(),
        user_id=user_id,
        monthly_income=float(inputs.get("monthly_income", 50000)),
        requested_amount=float(inputs.get("credit_amount", 100000)),
        tenure_months=int(inputs.get("duration", 12)),
        simulated_nova_score=int(outputs.get("nova_score", {}).get("nova_score", 700)),
        simulated_approval_pct=float(outputs.get("approval_percentage", 75.0)),
        decision=str(outputs.get("decision_engine", {}).get("decision", "Likely Eligible")),
        inputs_json=json.dumps(inputs),
        outputs_json=json.dumps(outputs),
        created_at=now_str,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_loan_simulations(
    db: Session,
    user_id: Optional[str] = None,
    is_admin: bool = False,
    limit: int = 50
) -> List[Dict[str, Any]]:
    query = db.query(LoanSimulationRecord)
    if not is_admin:
        if not user_id:
            return []
        query = query.filter(LoanSimulationRecord.user_id == user_id)
    elif user_id:
        query = query.filter(LoanSimulationRecord.user_id == user_id)

    rows = query.order_by(desc(LoanSimulationRecord.created_at)).limit(limit).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "monthly_income": r.monthly_income,
            "requested_amount": r.requested_amount,
            "tenure_months": r.tenure_months,
            "simulated_nova_score": r.simulated_nova_score,
            "simulated_approval_pct": r.simulated_approval_pct,
            "decision": r.decision,
            "inputs": json.loads(r.inputs_json),
            "outputs": json.loads(r.outputs_json),
            "created_at": r.created_at,
        }
        for r in rows
    ]


# ─── Report Helpers ───────────────────────────────────────────────────────────

def save_report_record(
    db: Session,
    user_id: str,
    assessment_id: str,
    applicant_name: str,
    report_type: str = "PDF_ASSESSMENT"
) -> ReportRecord:
    now_str = datetime.now(timezone.utc).isoformat()
    record = ReportRecord(
        id="REP-" + uuid.uuid4().hex[:8].upper(),
        user_id=user_id,
        assessment_id=assessment_id,
        applicant_name=applicant_name,
        report_type=report_type,
        created_at=now_str,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_user_reports(
    db: Session,
    user_id: Optional[str] = None,
    is_admin: bool = False,
    limit: int = 50
) -> List[Dict[str, Any]]:
    query = db.query(ReportRecord)
    if not is_admin:
        if not user_id:
            return []
        query = query.filter(ReportRecord.user_id == user_id)
    elif user_id:
        query = query.filter(ReportRecord.user_id == user_id)

    rows = query.order_by(desc(ReportRecord.created_at)).limit(limit).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "assessment_id": r.assessment_id,
            "applicant_name": r.applicant_name,
            "report_type": r.report_type,
            "created_at": r.created_at,
        }
        for r in rows
    ]


# ─── Activity Audit Logging Helpers ───────────────────────────────────────────

def log_activity(
    db: Session,
    action: str,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
):
    """
    Logs structured user or administrative activity without storing sensitive
    secrets, passwords, or full raw financial tokens.
    """
    try:
        now_str = datetime.now(timezone.utc).isoformat()
        # Ensure passwords or tokens are never logged
        safe_details = {}
        if details:
            for k, v in details.items():
                if "password" in k.lower() or "token" in k.lower() or "secret" in k.lower():
                    continue
                safe_details[k] = v

        event = ActivityLog(
            user_id=user_id,
            user_email=user_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            timestamp=now_str,
            details=json.dumps(safe_details) if safe_details else None,
            ip_address=ip_address,
        )
        db.add(event)
        db.commit()
    except Exception as e:
        db.rollback()


def get_activity_logs(
    db: Session,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    query = db.query(ActivityLog)
    if user_id:
        query = query.filter(ActivityLog.user_id == user_id)
    if action:
        query = query.filter(ActivityLog.action == action)
    
    rows = query.order_by(desc(ActivityLog.timestamp)).offset(offset).limit(limit).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "user_email": r.user_email or "system",
            "action": r.action,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "timestamp": r.timestamp,
            "details": json.loads(r.details) if r.details else {},
            "ip_address": r.ip_address,
        }
        for r in rows
    ]


def get_system_stats(db: Session) -> Dict[str, Any]:
    """Calculates operational metrics and system stats for the Admin Dashboard."""
    total_users = db.query(UserRecord).count()
    active_users = db.query(UserRecord).filter(UserRecord.is_active == True).count()
    total_assessments = db.query(CreditAssessmentRecord).count()
    total_simulations = db.query(LoanSimulationRecord).count()
    total_reports = db.query(ReportRecord).count()
    total_events = db.query(ActivityLog).count()

    # Recent signups in last 7 days (or last 5 users)
    recent_users = db.query(UserRecord).order_by(desc(UserRecord.created_at)).limit(5).all()

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_assessments": total_assessments,
        "total_simulations": total_simulations,
        "total_reports": total_reports,
        "total_activity_events": total_events,
        "recent_signups": [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at,
                "last_login_at": u.last_login_at,
            }
            for u in recent_users
        ]
    }


# ─── Loan Scenarios Repository Helpers ────────────────────────────────────────

def save_loan_scenario(db: Session, user_id: str, scenario_data: Dict[str, Any]) -> Dict[str, Any]:
    """Saves a loan intelligence scenario linked to the specified user_id."""
    now_str = datetime.now(timezone.utc).isoformat()
    scen_id = "SCEN-" + uuid.uuid4().hex[:10].upper()
    
    rec = LoanScenarioRecord(
        id=scen_id,
        user_id=user_id,
        scenario_name=scenario_data.get("scenario_name", "Saved Loan Scenario"),
        loan_type=scenario_data.get("loan_type", "Personal Loan"),
        principal=float(scenario_data.get("principal", 0.0)),
        annual_rate=float(scenario_data.get("annual_rate", 0.0)),
        tenure_months=int(scenario_data.get("tenure_months", 36)),
        processing_fee=float(scenario_data.get("processing_fee", 0.0)),
        down_payment=float(scenario_data.get("down_payment", 0.0)),
        monthly_emi=float(scenario_data.get("monthly_emi", 0.0)),
        total_interest=float(scenario_data.get("total_interest", 0.0)),
        total_repayment=float(scenario_data.get("total_repayment", 0.0)),
        effective_total_cost=float(scenario_data.get("effective_total_cost", 0.0)),
        foir=float(scenario_data.get("foir", 0.0)),
        affordability_result=scenario_data.get("affordability_result", "Comfortable"),
        inputs_json=json.dumps(scenario_data.get("inputs", {})),
        outputs_json=json.dumps(scenario_data.get("outputs", {})),
        created_at=now_str
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    return {
        "id": rec.id,
        "user_id": rec.user_id,
        "scenario_name": rec.scenario_name,
        "loan_type": rec.loan_type,
        "principal": rec.principal,
        "annual_rate": rec.annual_rate,
        "tenure_months": rec.tenure_months,
        "processing_fee": rec.processing_fee,
        "down_payment": rec.down_payment,
        "monthly_emi": rec.monthly_emi,
        "total_interest": rec.total_interest,
        "total_repayment": rec.total_repayment,
        "effective_total_cost": rec.effective_total_cost,
        "foir": rec.foir,
        "affordability_result": rec.affordability_result,
        "inputs": json.loads(rec.inputs_json),
        "outputs": json.loads(rec.outputs_json),
        "created_at": rec.created_at
    }


def get_user_loan_scenarios(db: Session, user_id: str, is_admin: bool = False, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves loan scenarios enforcing multi-tenant user isolation."""
    query = db.query(LoanScenarioRecord)
    if not is_admin:
        query = query.filter(LoanScenarioRecord.user_id == user_id)
    rows = query.order_by(desc(LoanScenarioRecord.created_at)).limit(limit).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "scenario_name": r.scenario_name,
            "loan_type": r.loan_type,
            "principal": r.principal,
            "annual_rate": r.annual_rate,
            "tenure_months": r.tenure_months,
            "processing_fee": r.processing_fee,
            "down_payment": r.down_payment,
            "monthly_emi": r.monthly_emi,
            "total_interest": r.total_interest,
            "total_repayment": r.total_repayment,
            "effective_total_cost": r.effective_total_cost,
            "foir": r.foir,
            "affordability_result": r.affordability_result,
            "inputs": json.loads(r.inputs_json) if r.inputs_json else {},
            "outputs": json.loads(r.outputs_json) if r.outputs_json else {},
            "created_at": r.created_at
        }
        for r in rows
    ]


def get_loan_scenario_by_id(db: Session, scenario_id: str, user_id: Optional[str] = None, is_admin: bool = False) -> Optional[Dict[str, Any]]:
    """Retrieves a single loan scenario by ID verifying user ownership."""
    query = db.query(LoanScenarioRecord).filter(LoanScenarioRecord.id == scenario_id)
    if user_id and not is_admin:
        query = query.filter(LoanScenarioRecord.user_id == user_id)
    r = query.first()
    if not r:
        return None
    return {
        "id": r.id,
        "user_id": r.user_id,
        "scenario_name": r.scenario_name,
        "loan_type": r.loan_type,
        "principal": r.principal,
        "annual_rate": r.annual_rate,
        "tenure_months": r.tenure_months,
        "processing_fee": r.processing_fee,
        "down_payment": r.down_payment,
        "monthly_emi": r.monthly_emi,
        "total_interest": r.total_interest,
        "total_repayment": r.total_repayment,
        "effective_total_cost": r.effective_total_cost,
        "foir": r.foir,
        "affordability_result": r.affordability_result,
        "inputs": json.loads(r.inputs_json) if r.inputs_json else {},
        "outputs": json.loads(r.outputs_json) if r.outputs_json else {},
        "created_at": r.created_at
    }


def delete_loan_scenario(db: Session, scenario_id: str, user_id: str, is_admin: bool = False) -> bool:
    """Deletes a saved scenario verifying user ownership."""
    query = db.query(LoanScenarioRecord).filter(LoanScenarioRecord.id == scenario_id)
    if not is_admin:
        query = query.filter(LoanScenarioRecord.user_id == user_id)
    rec = query.first()
    if not rec:
        return False
    db.delete(rec)
    db.commit()
    return True

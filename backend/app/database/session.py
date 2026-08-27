"""
SQLAlchemy database session and ORM base — SQLite (dev) / PostgreSQL (prod).
Includes User authentication, Role-Based Access Control (RBAC), and Private Assessment History.
"""
import json
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from backend.app.core.config import get_settings
from backend.app.core.security import hash_password

settings = get_settings()

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

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, default="user")   # 'admin' or 'user'
    created_at = Column(String, nullable=False)


class CreditAssessmentRecord(Base):
    __tablename__ = "credit_assessments"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    user_email = Column(String, nullable=True)
    timestamp = Column(String, nullable=False)
    applicant_name = Column(String, nullable=True)
    applicant_age = Column(Integer, nullable=True)
    monthly_income = Column(Float, nullable=True)
    requested_loan = Column(Float, nullable=True)
    tenure_months = Column(Integer, nullable=True)
    nova_score = Column(Integer, nullable=True)
    risk_tier = Column(String, nullable=True)
    approval_probability = Column(Float, nullable=True)
    decision = Column(String, nullable=True)
    foir_ratio = Column(Float, nullable=True)
    dti_ratio = Column(Float, nullable=True)
    raw_payload = Column(Text, nullable=False)
    result_payload = Column(Text, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String, nullable=False)
    event_type = Column(String, nullable=False)   # LOGIN | REGISTER | ASSESSMENT | SIMULATE | PDF_DOWNLOAD
    user_id = Column(String, nullable=True)
    assessment_id = Column(String, nullable=True)
    applicant_name = Column(String, nullable=True)
    details = Column(Text, nullable=True)


# ─── Initialization & Default Admin Seeding ──────────────────────────────────

def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Seed Single Default Admin User
    db = SessionLocal()
    try:
        admin_user = db.query(UserRecord).filter(UserRecord.email == "admin@novacredit.ai").first()
        if not admin_user:
            admin_record = UserRecord(
                id="admin-0001",
                email="admin@novacredit.ai",
                hashed_password=hash_password("Admin@123456"),
                full_name="System Administrator",
                role="admin",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            db.add(admin_record)
            db.commit()
    except Exception as e:
        db.rollback()
    finally:
        db.close()


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── User & Assessment Persistence Helpers ────────────────────────────────────

def get_user_by_email(db: Session, email: str) -> UserRecord | None:
    return db.query(UserRecord).filter(UserRecord.email == email.lower().strip()).first()


def get_user_by_id(db: Session, user_id: str) -> UserRecord | None:
    return db.query(UserRecord).filter(UserRecord.id == user_id).first()


def create_user(db: Session, user_id: str, email: str, password_plain: str, full_name: str, role: str = "user") -> UserRecord:
    user = UserRecord(
        id=user_id,
        email=email.lower().strip(),
        hashed_password=hash_password(password_plain),
        full_name=full_name.strip(),
        role=role,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def save_assessment_orm(db: Session, assessment_id: str, applicant_name: str,
                         payload: dict, result: dict, user_id: str = None, user_email: str = None):
    record = CreditAssessmentRecord(
        id=assessment_id,
        user_id=user_id,
        user_email=user_email,
        timestamp=datetime.now(timezone.utc).isoformat(),
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
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def log_audit_event(db: Session, event_type: str, user_id: str = None, assessment_id: str = None,
                     applicant_name: str = None, details: dict = None):
    event = AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        event_type=event_type,
        user_id=user_id,
        assessment_id=assessment_id,
        applicant_name=applicant_name,
        details=json.dumps(details) if details else None,
    )
    db.add(event)
    db.commit()


def get_assessment_by_id(db: Session, assessment_id: str) -> dict | None:
    record = db.query(CreditAssessmentRecord).filter(
        CreditAssessmentRecord.id == assessment_id
    ).first()
    if record:
        return json.loads(record.result_payload)
    return None


def get_history(db: Session, user_id: str = None, is_admin: bool = False, limit: int = 50) -> list:
    query = db.query(CreditAssessmentRecord)
    if is_admin:
        # Admin mode: view all assessments across all users
        pass
    elif user_id:
        # User mode: view ONLY assessments belonging to this specific user ID
        query = query.filter(CreditAssessmentRecord.user_id == user_id)
    else:
        # Guest mode: view ONLY unauthenticated guest assessments
        query = query.filter(CreditAssessmentRecord.user_id == None)
    
    rows = query.order_by(CreditAssessmentRecord.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id or "GUEST-SESSION",
            "user_email": r.user_email or "Guest User",
            "timestamp": r.timestamp,
            "applicant_name": r.applicant_name,
            "requested_loan": r.requested_loan,
            "nova_score": r.nova_score,
            "risk_tier": r.risk_tier,
            "approval_probability": round((r.approval_probability or 0.75) * 100, 1),
            "decision": r.decision,
            "foir_ratio": round((r.foir_ratio or 0.3) * 100, 1),
        }
        for r in rows
    ]


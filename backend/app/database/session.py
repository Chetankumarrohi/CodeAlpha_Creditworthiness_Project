"""
SQLAlchemy database session and ORM base — works with SQLite (dev) and PostgreSQL (prod).
Switch via DATABASE_URL environment variable.
"""
import json
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean, Text, DateTime
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.app.core.config import get_settings

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

class CreditAssessmentRecord(Base):
    __tablename__ = "credit_assessments"

    id = Column(String, primary_key=True, index=True)
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
    event_type = Column(String, nullable=False)   # ASSESSMENT | SIMULATE | PDF_DOWNLOAD | ERROR
    assessment_id = Column(String, nullable=True)
    applicant_name = Column(String, nullable=True)
    details = Column(Text, nullable=True)         # JSON blob


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Persistence helpers ────────────────────────────────────────────────────

def save_assessment_orm(db: Session, assessment_id: str, applicant_name: str,
                         payload: dict, result: dict):
    record = CreditAssessmentRecord(
        id=assessment_id,
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


def log_audit_event(db: Session, event_type: str, assessment_id: str = None,
                     applicant_name: str = None, details: dict = None):
    event = AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        event_type=event_type,
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


def get_history(db: Session, limit: int = 50) -> list:
    rows = (db.query(CreditAssessmentRecord)
              .order_by(CreditAssessmentRecord.timestamp.desc())
              .limit(limit)
              .all())
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp,
            "applicant_name": r.applicant_name,
            "requested_loan": r.requested_loan,
            "nova_score": r.nova_score,
            "risk_tier": r.risk_tier,
            "approval_probability": round(r.approval_probability * 100, 1),
            "decision": r.decision,
            "foir_ratio": round(r.foir_ratio * 100, 1),
        }
        for r in rows
    ]

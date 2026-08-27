import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from config import DATABASE_FILE

DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)


def init_db():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_assessments (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            applicant_name TEXT,
            applicant_age INTEGER,
            monthly_income REAL,
            requested_loan REAL,
            tenure_months INTEGER,
            nova_score INTEGER,
            risk_tier TEXT,
            approval_probability REAL,
            decision TEXT,
            foir_ratio REAL,
            dti_ratio REAL,
            raw_payload TEXT NOT NULL,
            result_payload TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def save_assessment(assessment_id: str, applicant_name: str, payload: dict, result: dict):
    init_db()
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    timestamp = datetime.now(timezone.utc).isoformat()
    
    cursor.execute("""
        INSERT INTO credit_assessments (
            id, timestamp, applicant_name, applicant_age, monthly_income, requested_loan,
            tenure_months, nova_score, risk_tier, approval_probability, decision, foir_ratio, dti_ratio, raw_payload, result_payload
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        assessment_id,
        timestamp,
        applicant_name,
        int(payload.get("age", 30)),
        float(payload.get("monthly_income", 50000)),
        float(payload.get("credit_amount", 100000)),
        int(payload.get("duration", 12)),
        int(result.get("nova_score", {}).get("nova_score", 700)),
        str(result.get("nova_score", {}).get("tier", "Strong")),
        float(result.get("approval_probability", 0.75)),
        str(result.get("decision_engine", {}).get("decision", "Likely Eligible")),
        float(result.get("decision_engine", {}).get("foir_ratio", 0.3)),
        float(result.get("decision_engine", {}).get("dti_ratio", 0.2)),
        json.dumps(payload),
        json.dumps(result)
    ))
    conn.commit()
    conn.close()


def get_assessment(assessment_id: str) -> Optional[dict]:
    init_db()
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT result_payload FROM credit_assessments WHERE id = ?;", (assessment_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None


def get_assessment_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves chronological assessment history for trend tracking."""
    init_db()
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, applicant_name, requested_loan, nova_score, risk_tier, approval_probability, decision, foir_ratio
        FROM credit_assessments
        ORDER BY timestamp DESC
        LIMIT ?;
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for r in rows:
        history.append({
            "id": r[0],
            "timestamp": r[1],
            "applicant_name": r[2],
            "requested_loan": r[3],
            "nova_score": r[4],
            "risk_tier": r[5],
            "approval_probability": round(r[6] * 100, 1),
            "decision": r[7],
            "foir_ratio": round(r[8] * 100, 1)
        })
    return history

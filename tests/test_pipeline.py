import pandas as pd
import pytest
from ml.pipeline import build_credit_pipeline
from ml.nova_score import calculate_nova_score
from sklearn.ensemble import RandomForestClassifier


def test_pipeline_build_and_fit():
    clf = RandomForestClassifier(n_estimators=10, random_state=42)
    pipeline = build_credit_pipeline(clf)
    
    df = pd.DataFrame([
        {
            "Age": 32, "Sex": "male", "Job": 1, "Housing": "own",
            "Saving accounts": "rich", "Checking account": "moderate",
            "Credit amount": 25000, "Duration": 12, "Purpose": "car"
        },
        {
            "Age": 22, "Sex": "female", "Job": 0, "Housing": "rent",
            "Saving accounts": "little", "Checking account": "little",
            "Credit amount": 50000, "Duration": 48, "Purpose": "education"
        }
    ])
    y = [1, 0]
    
    pipeline.fit(df, y)
    preds = pipeline.predict(df)
    probs = pipeline.predict_proba(df)
    
    assert len(preds) == 2
    assert probs.shape == (2, 2)


def test_nova_score_calculation():
    res = calculate_nova_score(
        calibrated_prob_good=0.85,
        dti=0.10,
        savings_standing="rich",
        duration_months=12,
        age=32
    )
    
    assert 300 <= res["nova_score"] <= 850
    assert res["tier"] in ["Exceptional", "Excellent", "Strong", "Moderate", "Weak", "High Risk"]
    assert "nova_score" in res
    assert "disclaimer" in res


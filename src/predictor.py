import os
import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"


class CreditPredictor:
    def __init__(self, models_dir=MODELS_DIR):
        self.models_dir = Path(models_dir)
        self.model_path = self.models_dir / "credit_model.pkl"
        self.scaler_path = self.models_dir / "scaler.pkl"
        self.columns_path = self.models_dir / "feature_columns.json"
        self.metadata_path = self.models_dir / "model_metadata.json"

        self.model = None
        self.scaler = None
        self.feature_columns = []
        self.metadata = {}
        self.is_ready = False

        self._load_artifacts()

    def _load_artifacts(self):
        try:
            if self.model_path.exists() and self.scaler_path.exists():
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                if self.columns_path.exists():
                    self.feature_columns = json.loads(self.columns_path.read_text())
                if self.metadata_path.exists():
                    self.metadata = json.loads(self.metadata_path.read_text())
                self.is_ready = True
        except Exception as e:
            print(f"⚠️ Warning: Could not load trained ML model: {e}")
            self.is_ready = False

    def predict(self, input_dict: dict):
        """
        Input keys expected:
        - age (int)
        - sex ('male' or 'female' / 'Male' or 'Female')
        - job ('Unskilled', 'Skilled', 'Highly Skilled', 'Management')
        - housing ('Own', 'Rent', 'Free' / 'own', 'rent', 'free')
        - saving_accounts ('none', 'little', 'moderate', 'quite rich', 'rich')
        - checking_account ('none', 'little', 'moderate', 'rich')
        - credit_amount (float)
        - duration (int)
        - purpose ('car', 'radio/TV', 'education', 'furniture/equipment', 'business', etc.)
        - monthly_income (float, default 50000)
        """
        age = int(input_dict.get("age", 30))
        sex = str(input_dict.get("sex", "male")).lower()
        job_label = input_dict.get("job", "Skilled")
        housing = str(input_dict.get("housing", "own")).lower()
        saving = str(input_dict.get("saving_accounts", "little")).lower()
        checking = str(input_dict.get("checking_account", "little")).lower()
        credit_amount = float(input_dict.get("credit_amount", 2500))
        duration = int(input_dict.get("duration", 12))
        purpose = str(input_dict.get("purpose", "car")).lower()
        income = float(input_dict.get("monthly_income", input_dict.get("income", 50000)))

        # DTI calculation
        monthly_payment = credit_amount / max(1, duration)
        dti = monthly_payment / max(1, income)

        if self.is_ready and self.feature_columns:
            # Build DataFrame matching feature engineering done in train_model.py
            saving_map = {"none": 0, "little": 1, "moderate": 2, "quite rich": 3, "rich": 4}
            checking_map = {"none": 0, "little": 1, "moderate": 2, "rich": 3}
            job_map = {"Unskilled": 0, "Skilled": 1, "Highly Skilled": 2, "Management": 3}

            savings_score = saving_map.get(saving, 1)
            checking_score = checking_map.get(checking, 1)
            job_num = job_map.get(job_label, 1)

            # Categorical age group
            age_group = "young" if age <= 25 else "early_adult" if age <= 35 else "adult" if age <= 50 else "senior"

            row = {
                "Age": age,
                "Job": job_num,
                "Credit amount": credit_amount,
                "Duration": duration,
                "Credit_per_Month": monthly_payment,
                "Log_Credit": np.log1p(credit_amount),
                "Log_Duration": np.log1p(duration),
                "Credit_to_Age": credit_amount / (age + 1e-5),
                "Savings_Score": savings_score,
                "Checking_Score": checking_score,
            }

            # Handle get_dummies column names matching feature_columns
            for col in self.feature_columns:
                if col not in row:
                    row[col] = 0

            # One-hot encodings matching train script
            if f"Sex_{sex}" in self.feature_columns:
                row[f"Sex_{sex}"] = 1
            if f"Housing_{housing}" in self.feature_columns:
                row[f"Housing_{housing}"] = 1
            if f"Saving accounts_{saving}" in self.feature_columns:
                row[f"Saving accounts_{saving}"] = 1
            if f"Checking account_{checking}" in self.feature_columns:
                row[f"Checking account_{checking}"] = 1
            if f"Purpose_{purpose}" in self.feature_columns:
                row[f"Purpose_{purpose}"] = 1
            if f"Age_Group_{age_group}" in self.feature_columns:
                row[f"Age_Group_{age_group}"] = 1

            df_row = pd.DataFrame([row])[self.feature_columns]
            scaled_row = self.scaler.transform(df_row)
            prob_good = float(self.model.predict_proba(scaled_row)[0][1])
        else:
            # High-precision fallback formula
            score = 0.50
            score += 0.15 if dti < 0.15 else (-0.10 if dti > 0.40 else 0.0)
            score += 0.10 if checking in ["moderate", "rich"] else (-0.05 if checking == "little" else -0.10)
            score += 0.08 if saving in ["moderate", "quite rich", "rich"] else 0.0
            score += 0.05 if 28 <= age <= 55 else -0.03
            prob_good = float(np.clip(score, 0.05, 0.95))

        # Convert probability of good credit into credit score (300 to 850)
        credit_score = int(round(300 + prob_good * 550))
        
        # Risk Tiers & Gen-Z Aura Badges
        if prob_good >= 0.75:
            risk_tier = "Low Risk"
            genz_vibe = "S-Tier Credit Aura 👑"
            recommendation = "Approved instantly! Maximum loan eligibility unlocked with prime interest rates."
            status_color = "#10B981" # Emerald Green
            risk_badge = "LOW-KEY RISK 🛡️"
        elif prob_good >= 0.50:
            risk_tier = "Medium Risk"
            genz_vibe = "Solid Vibe 💯"
            recommendation = "Conditional approval. Additional proof of income or collateral recommended for lowest rates."
            status_color = "#F59E0B" # Amber Gold
            risk_badge = "MODERATE RISK ⚡"
        else:
            risk_tier = "High Risk"
            genz_vibe = "Needs Work ⚠️"
            recommendation = "High risk detected. Recommend reducing requested credit amount or adding a co-signer."
            status_color = "#EF4444" # Crimson Red
            risk_badge = "HIGH-KEY RISK 🚩"

        # Key Drivers / Feature Impact Breakdown
        drivers = [
            {"factor": "Debt-to-Income (DTI)", "impact": f"{dti * 100:.1f}%", "status": "Positive" if dti < 0.25 else "Negative"},
            {"factor": "Checking Account Standing", "impact": checking.capitalize(), "status": "Positive" if checking in ["moderate", "rich"] else "Neutral"},
            {"factor": "Savings Account Reserve", "impact": saving.capitalize(), "status": "Positive" if saving in ["quite rich", "rich"] else "Neutral"},
            {"factor": "Credit Duration", "impact": f"{duration} Months", "status": "Positive" if duration <= 24 else "Negative"},
        ]

        return {
            "credit_score": credit_score,
            "approval_probability": round(prob_good, 4),
            "approval_percentage": round(prob_good * 100, 1),
            "risk_tier": risk_tier,
            "risk_badge": risk_badge,
            "genz_vibe": genz_vibe,
            "recommendation": recommendation,
            "status_color": status_color,
            "dti_ratio": round(dti, 4),
            "monthly_payment": round(monthly_payment, 2),
            "drivers": drivers,
            "is_ml_used": self.is_ready,
        }

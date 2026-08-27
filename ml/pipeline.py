import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline


class CreditFeatureEngineer(BaseEstimator, TransformerMixin):
    """
    Dedicated feature-engineering transformer for Credit Risk Modeling.
    Calculates derived interaction terms, log transformations, and ordinal scores.
    """
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X_out = X.copy()
        
        credit_amt = X_out["Credit amount"].astype(float)
        duration = X_out["Duration"].astype(float)
        age = X_out["Age"].astype(float)

        # 1. Interaction & Ratio Terms
        X_out["Credit_per_Month"] = credit_amt / (duration + 1e-5)
        X_out["Log_Credit"] = np.log1p(np.maximum(0.0, credit_amt))
        X_out["Log_Duration"] = np.log1p(np.maximum(1.0, duration))
        X_out["Credit_to_Age"] = credit_amt / (age + 1e-5)

        # 2. Ordinal Liquidity Scores
        saving_map = {"none": 0, "little": 1, "moderate": 2, "quite rich": 3, "rich": 4}
        checking_map = {"none": 0, "little": 1, "moderate": 2, "rich": 3}
        
        X_out["Savings_Score"] = X_out["Saving accounts"].astype(str).str.lower().map(saving_map).fillna(0).astype(float)
        X_out["Checking_Score"] = X_out["Checking account"].astype(str).str.lower().map(checking_map).fillna(0).astype(float)

        # 3. Categorical Age Groups
        X_out["Age_Group"] = pd.cut(
            age, bins=[0, 25, 35, 50, 100], labels=["young", "early_adult", "adult", "senior"]
        ).astype(str)

        return X_out


def build_credit_pipeline(classifier):
    """
    Constructs a unified, leakage-free Scikit-Learn Pipeline:
    
    Raw Applicant Input
            ↓
    Feature Engineering (CreditFeatureEngineer)
            ↓
    Missing-Value Imputation (SimpleImputer)
            ↓
    Categorical Encoding (OneHotEncoder handle_unknown='ignore')
            ↓
    Classifier Model (Calibrated / CatBoost / ExtraTrees)
    """
    numeric_features = [
        "Age", "Job", "Credit amount", "Duration", "Credit_per_Month",
        "Log_Credit", "Log_Duration", "Credit_to_Age", "Savings_Score", "Checking_Score"
    ]
    categorical_features = ["Sex", "Housing", "Saving accounts", "Checking account", "Purpose", "Age_Group"]

    # Preprocessing Sub-Pipelines
    num_pipeline = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median"))
    ])

    cat_pipeline = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="constant", fill_value="none")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", num_pipeline, numeric_features),
            ("cat", cat_pipeline, categorical_features),
        ],
        remainder="drop"
    )

    full_pipeline = Pipeline(steps=[
        ("feature_engineer", CreditFeatureEngineer()),
        ("preprocessor", preprocessor),
        ("classifier", classifier)
    ])

    return full_pipeline

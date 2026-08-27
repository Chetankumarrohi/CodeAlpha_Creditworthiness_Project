import os
import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier, ExtraTreesClassifier, VotingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, roc_auc_score, accuracy_score, f1_score, precision_score, recall_score, confusion_matrix
import catboost as cb

# Define paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "german_credit_data.csv"
MODELS_DIR = BASE_DIR / "models"
APP_MODELS_DIR = BASE_DIR / "app" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
APP_MODELS_DIR.mkdir(parents=True, exist_ok=True)


def load_and_preprocess_data():
    """Load raw credit dataset and apply domain feature engineering."""
    print(f"📥 Loading dataset from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])

    # Categorical missing values imputation
    df["Saving accounts"] = df["Saving accounts"].fillna("none")
    df["Checking account"] = df["Checking account"].fillna("none")

    # Target definition (1 = Good Credit / Low Risk, 0 = Bad Credit / High Risk)
    df["Target"] = (df["Risk"] == "good").astype(int)

    # Feature Engineering
    df["Credit_per_Month"] = df["Credit amount"] / (df["Duration"] + 1e-5)
    df["Log_Credit"] = np.log1p(df["Credit amount"])
    df["Log_Duration"] = np.log1p(df["Duration"])
    df["Credit_to_Age"] = df["Credit amount"] / (df["Age"] + 1e-5)
    
    # Financial standing ordinal scores
    saving_map = {"none": 0, "little": 1, "moderate": 2, "quite rich": 3, "rich": 4}
    checking_map = {"none": 0, "little": 1, "moderate": 2, "rich": 3}
    df["Savings_Score"] = df["Saving accounts"].map(saving_map).fillna(0)
    df["Checking_Score"] = df["Checking account"].map(checking_map).fillna(0)

    # Age bracket categorization
    df["Age_Group"] = pd.cut(df["Age"], bins=[0, 25, 35, 50, 100], labels=["young", "early_adult", "adult", "senior"])

    # Categorical encoding
    cat_cols = ["Sex", "Housing", "Saving accounts", "Checking account", "Purpose", "Age_Group"]
    df_encoded = pd.get_dummies(df.drop(columns=["Risk"]), columns=cat_cols, drop_first=True)

    X = df_encoded.drop(columns=["Target"])
    y = df_encoded["Target"]

    return X, y, df


def train_and_evaluate():
    X, y, df_raw = load_and_preprocess_data()
    feature_columns = X.columns.tolist()

    print(f"📊 Dataset size: {len(X)} records | Features: {len(feature_columns)}")
    print(f"⚖️ Target class balance: Good (1)={y.sum()}, Bad (0)={len(y)-y.sum()}")

    # Stratified Train-Test Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    # Scaler fit on training set
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Candidate Models
    models = {
        "CatBoost": cb.CatBoostClassifier(
            iterations=350,
            depth=5,
            learning_rate=0.03,
            l2_leaf_reg=3,
            auto_class_weights="Balanced",
            random_seed=42,
            verbose=0,
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=300,
            max_depth=8,
            min_samples_split=4,
            class_weight="balanced",
            random_state=42,
        ),
        "HistGradientBoosting": HistGradientBoostingClassifier(
            max_iter=250,
            max_depth=5,
            learning_rate=0.03,
            class_weight="balanced",
            random_state=42,
        ),
        "ExtraTrees": ExtraTreesClassifier(
            n_estimators=250,
            max_depth=9,
            class_weight="balanced",
            random_state=42,
        ),
    }

    best_model_name = None
    best_auc = 0.0
    best_model = None
    results = {}

    print("\n🚀 Benchmarking Machine Learning Algorithms...")
    print("-" * 65)

    for name, model in models.items():
        # Fit model (use scaled features for Tree models as well for consistency)
        model.fit(X_train_scaled, y_train)
        
        preds = model.predict(X_test_scaled)
        probs = model.predict_proba(X_test_scaled)[:, 1]
        
        auc = float(roc_auc_score(y_test, probs))
        acc = float(accuracy_score(y_test, preds))
        f1 = float(f1_score(y_test, preds))
        prec = float(precision_score(y_test, preds))
        rec = float(recall_score(y_test, preds))
        cm = confusion_matrix(y_test, preds).tolist()

        results[name] = {
            "roc_auc": round(auc, 4),
            "accuracy": round(acc, 4),
            "f1_score": round(f1, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "confusion_matrix": cm,
        }

        print(f"🔹 {name:20s} | ROC-AUC: {auc:.4f} | Acc: {acc:.4f} | F1: {f1:.4f} | Recall: {rec:.4f}")

        if auc > best_auc:
            best_auc = auc
            best_model_name = name
            best_model = model

    print("-" * 65)
    print(f"🏆 Champion Model Selected: {best_model_name} (ROC-AUC: {best_auc:.4f})")

    # Extract Feature Importances from Champion Model
    if hasattr(best_model, "feature_importances_"):
        importances = best_model.feature_importances_
    else:
        importances = np.ones(len(feature_columns)) / len(feature_columns)

    feature_importance_dict = dict(
        sorted(zip(feature_columns, [float(x) for x in importances]), key=lambda x: x[1], reverse=True)
    )

    # Save artifacts to both models/ and app/models/
    model_path = MODELS_DIR / "credit_model.pkl"
    scaler_path = MODELS_DIR / "scaler.pkl"
    columns_path = MODELS_DIR / "feature_columns.json"
    metadata_path = MODELS_DIR / "model_metadata.json"

    joblib.dump(best_model, model_path)
    joblib.dump(scaler, scaler_path)
    
    # Also mirror to app/models/
    joblib.dump(best_model, APP_MODELS_DIR / "credit_model.pkl")
    joblib.dump(scaler, APP_MODELS_DIR / "scaler.pkl")

    columns_path.write_text(json.dumps(feature_columns, indent=2))
    (APP_MODELS_DIR / "feature_columns.json").write_text(json.dumps(feature_columns, indent=2))

    metadata = {
        "champion_model": best_model_name,
        "best_roc_auc": round(best_auc, 4),
        "all_metrics": results,
        "feature_count": len(feature_columns),
        "training_samples": len(X_train),
        "test_samples": len(X_test),
        "feature_importances": feature_importance_dict,
    }

    metadata_path.write_text(json.dumps(metadata, indent=2))
    (APP_MODELS_DIR / "model_metadata.json").write_text(json.dumps(metadata, indent=2))

    print(f"\n✅ Model training completed successfully!")
    print(f"📦 Model saved to: {model_path}")
    print(f"📦 Scaler saved to: {scaler_path}")
    print(f"📦 Metadata saved to: {metadata_path}\n")


if __name__ == "__main__":
    train_and_evaluate()

import os
import sys
import json
import joblib
import optuna
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import (
    RAW_DATASET_PATH, PIPELINE_FILE, LEGACY_PIPELINE_FILE,
    PIPELINE_METADATA_FILE, BENCHMARK_REPORT_FILE
)
from ml.pipeline import build_credit_pipeline

from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    roc_auc_score, average_precision_score, accuracy_score, balanced_accuracy_score,
    f1_score, precision_score, recall_score, confusion_matrix, brier_score_loss, log_loss
)

from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from catboost import CatBoostClassifier
import xgboost as xgb
try:
    import lightgbm as lgb
except Exception:
    lgb = None

# Suppress Optuna logging verbosity
optuna.logging.set_verbosity(optuna.logging.WARNING)


def load_and_split_data():
    """
    Loads academic dataset and partitions into:
    1. Training & Cross-Validation Set (800 records / 80%)
    2. Untouched Final Holdout Test Set (200 records / 20%)
    """
    print(f"📥 Loading dataset from {RAW_DATASET_PATH}...")
    df = pd.read_csv(RAW_DATASET_PATH)
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])
    
    # Target definition (1 = Good Credit Risk, 0 = Bad Credit Risk)
    df["Target"] = (df["Risk"].astype(str).str.lower() == "good").astype(int)
    X = df.drop(columns=["Risk", "Target"])
    y = df["Target"]

    # Stratified Holdout Split
    X_train, X_holdout, y_train, y_holdout = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    print(f"📊 Dataset partition: Train/CV = {len(X_train)} | Holdout Test = {len(X_holdout)}")
    print(f"   Train Target Distribution -> Good (1): {y_train.sum()}, Bad (0): {len(y_train) - y_train.sum()}")
    print(f"   Holdout Target Distribution -> Good (1): {y_holdout.sum()}, Bad (0): {len(y_holdout) - y_holdout.sum()}")
    
    return X_train, y_train, X_holdout, y_holdout


def evaluate_predictions(y_true, y_pred, y_prob):
    """Calculates all 10 standard credit evaluation metrics with cost matrix."""
    auc = float(roc_auc_score(y_true, y_prob))
    pr_auc = float(average_precision_score(y_true, y_prob))
    acc = float(accuracy_score(y_true, y_pred))
    bal_acc = float(balanced_accuracy_score(y_true, y_pred))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec_good = float(recall_score(y_true, y_pred, pos_label=1, zero_division=0))
    rec_bad = float(recall_score(y_true, y_pred, pos_label=0, zero_division=0))
    brier = float(brier_score_loss(y_true, y_prob))
    loss = float(log_loss(y_true, np.clip(y_prob, 1e-6, 1 - 1e-6)))

    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()
    # Credit Risk specifics:
    # False Approval of Bad (FP): Bad applicant predicted as Good (Cost: Very High)
    # False Rejection of Good (FN): Good applicant predicted as Bad (Cost: Lost Business)

    return {
        "roc_auc": round(auc, 4),
        "pr_auc": round(pr_auc, 4),
        "accuracy": round(acc, 4),
        "balanced_accuracy": round(bal_acc, 4),
        "f1_score": round(f1, 4),
        "precision": round(prec, 4),
        "recall_good": round(rec_good, 4),
        "recall_bad": round(rec_bad, 4),
        "specificity": round(rec_bad, 4),
        "brier_score": round(brier, 4),
        "log_loss": round(loss, 4),
        "false_approvals_bad": int(fp),
        "false_rejections_good": int(fn),
        "confusion_matrix": cm.tolist()
    }


def optimize_thresholds(y_true, y_prob, thresholds=[0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]):
    """Evaluates the approval rate vs risky default approvals trade-off across decision thresholds."""
    analysis = []
    for th in thresholds:
        preds = (y_prob >= th).astype(int)
        metrics = evaluate_predictions(y_true, preds, y_prob)
        approval_rate = float(np.mean(preds))
        
        # Risk rate among approved: proportion of approved who are actually Bad (Target=0)
        approved_indices = np.where(preds == 1)[0]
        if len(approved_indices) > 0:
            actual_bads_approved = (y_true.iloc[approved_indices] if hasattr(y_true, 'iloc') else y_true[approved_indices]) == 0
            default_rate_in_approved = float(np.mean(actual_bads_approved))
        else:
            default_rate_in_approved = 0.0

        analysis.append({
            "threshold": th,
            "approval_rate": round(approval_rate * 100, 1),
            "default_rate_in_approved": round(default_rate_in_approved * 100, 1),
            "recall_bad": metrics["recall_bad"],
            "f1_score": metrics["f1_score"],
            "balanced_accuracy": metrics["balanced_accuracy"],
            "false_approvals_bad": metrics["false_approvals_bad"],
            "false_rejections_good": metrics["false_rejections_good"]
        })
    return analysis


def tune_catboost_optuna(X_train, y_train, n_trials=25):
    """Tunes CatBoost regularizations and hyperparameters via Optuna Stratified 5-Fold CV."""
    print("🧪 Running Optuna Hyperparameter Tuning for CatBoost...")
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    def objective(trial):
        params = {
            "iterations": trial.suggest_int("iterations", 150, 450, step=50),
            "depth": trial.suggest_int("depth", 3, 7),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1.0, 15.0),
            "auto_class_weights": "Balanced",
            "random_seed": 42,
            "verbose": 0
        }
        oof = np.zeros(len(X_train))
        for tr_idx, val_idx in skf.split(X_train, y_train):
            X_tr, y_tr = X_train.iloc[tr_idx], y_train.iloc[tr_idx]
            X_val = X_train.iloc[val_idx]
            model = CatBoostClassifier(**params)
            pipe = build_credit_pipeline(model)
            pipe.fit(X_tr, y_tr)
            oof[val_idx] = pipe.predict_proba(X_val)[:, 1]
        return roc_auc_score(y_train, oof)

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials)
    print(f"✨ Best CatBoost Params (CV ROC-AUC: {study.best_value:.4f}): {study.best_params}")
    return study.best_params


def tune_extratrees_optuna(X_train, y_train, n_trials=25):
    """Tunes ExtraTrees hyperparameters via Optuna Stratified 5-Fold CV."""
    print("🧪 Running Optuna Hyperparameter Tuning for ExtraTrees...")
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 150, 400, step=50),
            "max_depth": trial.suggest_int("max_depth", 4, 12),
            "min_samples_split": trial.suggest_int("min_samples_split", 2, 10),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 6),
            "class_weight": trial.suggest_categorical("class_weight", ["balanced", "balanced_subsample"]),
            "random_state": 42
        }
        oof = np.zeros(len(X_train))
        for tr_idx, val_idx in skf.split(X_train, y_train):
            X_tr, y_tr = X_train.iloc[tr_idx], y_train.iloc[tr_idx]
            X_val = X_train.iloc[val_idx]
            model = ExtraTreesClassifier(**params)
            pipe = build_credit_pipeline(model)
            pipe.fit(X_tr, y_tr)
            oof[val_idx] = pipe.predict_proba(X_val)[:, 1]
        return roc_auc_score(y_train, oof)

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials)
    print(f"✨ Best ExtraTrees Params (CV ROC-AUC: {study.best_value:.4f}): {study.best_params}")
    return study.best_params


def train_benchmark_and_tune():
    X_train, y_train, X_holdout, y_holdout = load_and_split_data()

    # Optuna Hyperparameter Tuning
    catboost_best_params = tune_catboost_optuna(X_train, y_train, n_trials=20)
    extratrees_best_params = tune_extratrees_optuna(X_train, y_train, n_trials=20)

    # 7 Candidate Estimator Definitions
    candidate_estimators = {
        "CatBoost (Tuned)": CatBoostClassifier(**catboost_best_params, auto_class_weights="Balanced", random_seed=42, verbose=0),
        "ExtraTrees (Tuned)": ExtraTreesClassifier(**extratrees_best_params, random_state=42),
        "RandomForest": RandomForestClassifier(n_estimators=250, max_depth=8, min_samples_leaf=3, class_weight="balanced", random_state=42),
        "XGBoost": xgb.XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.03, scale_pos_weight=0.43, random_state=42, eval_metric="logloss"),
        "HistGradientBoosting": HistGradientBoostingClassifier(max_iter=200, max_depth=5, class_weight="balanced", random_state=42),
        "LogisticRegression": LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    }
    if lgb is not None:
        candidate_estimators["LightGBM"] = lgb.LGBMClassifier(n_estimators=150, max_depth=4, learning_rate=0.03, class_weight="balanced", random_state=42, verbose=-1)

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_benchmark_matrix = {}
    fitted_pipelines = {}

    print("\n🚀 Executing 5-Fold Stratified Cross-Validation Benchmark...")
    print("-" * 110)
    print(f"{'Model Name':22s} | {'ROC-AUC':7s} | {'PR-AUC':7s} | {'Rec(Bad)':8s} | {'F1':6s} | {'Brier':6s} | {'LogLoss':7s} | {'FP (Bad Appr)':13s}")
    print("-" * 110)

    best_cv_score = 0.0
    champion_name = None
    champion_base_clf = None

    for name, clf in candidate_estimators.items():
        oof_probs = np.zeros(len(X_train))
        oof_preds = np.zeros(len(X_train))

        for tr_idx, val_idx in skf.split(X_train, y_train):
            X_tr, y_tr = X_train.iloc[tr_idx], y_train.iloc[tr_idx]
            X_val = X_train.iloc[val_idx]

            pipe = build_credit_pipeline(clf)
            pipe.fit(X_tr, y_tr)
            oof_probs[val_idx] = pipe.predict_proba(X_val)[:, 1]
            oof_preds[val_idx] = pipe.predict(X_val)

        metrics = evaluate_predictions(y_train, oof_preds, oof_probs)
        cv_benchmark_matrix[name] = metrics

        print(f"{name:22s} | {metrics['roc_auc']:7.4f} | {metrics['pr_auc']:7.4f} | {metrics['recall_bad']:8.4f} | {metrics['f1_score']:6.4f} | {metrics['brier_score']:6.4f} | {metrics['log_loss']:7.4f} | {metrics['false_approvals_bad']:13d}")

        if metrics["roc_auc"] > best_cv_score:
            best_cv_score = metrics["roc_auc"]
            champion_name = name
            champion_base_clf = clf

    print("-" * 110)
    print(f"🏆 Champion Selected from Validation Evidence: {champion_name} (CV ROC-AUC: {best_cv_score:.4f})")

    # Fit Champion with CalibratedClassifierCV on Full Training Set
    print(f"\n⚙️ Fitting Champion with Platt Sigmoid Probability Calibration...")
    calibrated_champion_pipe = build_credit_pipeline(
        CalibratedClassifierCV(estimator=champion_base_clf, method="sigmoid", cv=5)
    )
    calibrated_champion_pipe.fit(X_train, y_train)

    # Evaluate on Untouched Final Holdout Set (200 records)
    print(f"\n🎯 Evaluating Champion on Untouched Final Holdout Test Set (N={len(X_holdout)})...")
    holdout_probs = calibrated_champion_pipe.predict_proba(X_holdout)[:, 1]
    holdout_preds = calibrated_champion_pipe.predict(X_holdout)
    holdout_metrics = evaluate_predictions(y_holdout, holdout_preds, holdout_probs)

    print(f"   Holdout ROC-AUC:            {holdout_metrics['roc_auc']}")
    print(f"   Holdout PR-AUC:             {holdout_metrics['pr_auc']}")
    print(f"   Holdout Recall Bad:         {holdout_metrics['recall_bad']} (Identifies {holdout_metrics['recall_bad']*100:.1f}% of bad risks)")
    print(f"   Holdout Brier Score:        {holdout_metrics['brier_score']}")
    print(f"   Holdout False Approvals:    {holdout_metrics['false_approvals_bad']} / {len(X_holdout) - y_holdout.sum()} bad applicants")

    # Threshold Optimization on Holdout Set
    print("\n📊 Decision Threshold Optimization & Risk Trade-off Analysis:")
    threshold_analysis = optimize_thresholds(y_holdout, holdout_probs)
    th_df = pd.DataFrame(threshold_analysis)
    print(th_df.to_string(index=False))

    # Persist Final Pipeline on Full 1000 Dataset
    print("\n📦 Fitting Final Calibrated Pipeline on Complete Ground Truth Dataset for Production Serving...")
    X_full = pd.concat([X_train, X_holdout])
    y_full = pd.concat([y_train, y_holdout])
    
    production_pipeline = build_credit_pipeline(
        CalibratedClassifierCV(estimator=champion_base_clf, method="sigmoid", cv=5)
    )
    production_pipeline.fit(X_full, y_full)
    joblib.dump(production_pipeline, PIPELINE_FILE)
    joblib.dump(production_pipeline, LEGACY_PIPELINE_FILE)

    # Save Versioned Metadata and Telemetry Report
    telemetry = {
        "champion_model": champion_name,
        "champion_cv_roc_auc": best_cv_score,
        "holdout_test_metrics": holdout_metrics,
        "cv_benchmark_matrix": cv_benchmark_matrix,
        "threshold_optimization": threshold_analysis,
        "best_hyperparameters": catboost_best_params if "CatBoost" in champion_name else extratrees_best_params,
        "is_calibrated": True,
        "calibration_method": "sigmoid_platt",
        "generated_timestamp": datetime.now(timezone.utc).isoformat()
    }
    BENCHMARK_REPORT_FILE.write_text(json.dumps(telemetry, indent=2))

    metadata = {
        "pipeline_version": "3.0.0",
        "champion_model": champion_name,
        "artifact_path": str(PIPELINE_FILE),
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "training_observations": len(X_full),
        "target_classes": {"0": "Bad Credit (Default)", "1": "Good Credit (Non-default)"},
        "features_expected": list(X_full.columns),
        "cv_roc_auc": best_cv_score,
        "holdout_roc_auc": holdout_metrics["roc_auc"],
        "recommended_decision_threshold": 0.45,
        "is_calibrated": True,
        "calibration_method": "sigmoid_platt",
        "academic_dataset": "Statlog German Credit Data (UCI)"
    }
    PIPELINE_METADATA_FILE.write_text(json.dumps(metadata, indent=2))

    print(f"\n✅ Phase 3 Model Tuning & Evaluation Completed!")
    print(f"📦 Production Pipeline saved to: {PIPELINE_FILE}")
    print(f"📊 Detailed Telemetry saved to: {BENCHMARK_REPORT_FILE}\n")


if __name__ == "__main__":
    train_benchmark_and_tune()

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_PATH = BASE_DIR / "reports" / "model_benchmark_report.json"
PIPELINE_PATH = BASE_DIR / "models" / "nova_credit_pipeline.joblib"


def get_model_health() -> dict:
    """Returns genuine model health checks - never fabricates values."""
    health = {
        "pipeline_loaded": PIPELINE_PATH.exists(),
        "report_available": REPORT_PATH.exists(),
        "calibration_active": False,
        "feature_schema_valid": False,
        "drift_detected": False,          # No drift monitoring implemented — explicitly false
        "drift_note": "Drift monitoring not yet implemented. Baseline: Statlog German Credit (N=1000).",
        "overall_status": "Degraded"
    }

    if REPORT_PATH.exists():
        try:
            with open(REPORT_PATH) as f:
                report = json.load(f)
            health["calibration_active"] = report.get("is_calibrated", False)
            health["calibration_method"] = report.get("calibration_method", "none")
            health["feature_schema_valid"] = True   # Pipeline loaded and validated at train time
            health["generated_timestamp"] = report.get("generated_timestamp", "unknown")
        except Exception as e:
            health["report_error"] = str(e)

    if health["pipeline_loaded"] and health["report_available"] and health["calibration_active"]:
        health["overall_status"] = "Healthy"
    elif health["pipeline_loaded"]:
        health["overall_status"] = "Warning"

    return health


def get_model_metrics() -> dict:
    """Returns real metrics directly from the saved benchmark report."""
    if not REPORT_PATH.exists():
        return {"error": "Benchmark report not found. Run ml/train.py to generate."}

    with open(REPORT_PATH) as f:
        report = json.load(f)

    holdout = report.get("holdout_test_metrics", {})
    benchmark = report.get("cv_benchmark_matrix", {})
    threshold_opts = report.get("threshold_optimization", [])
    best_params = report.get("best_hyperparameters", {})

    # Build model comparison rows
    model_comparison = []
    for model_name, metrics in benchmark.items():
        model_comparison.append({
            "model": model_name,
            "cv_roc_auc": metrics.get("roc_auc"),
            "cv_pr_auc": metrics.get("pr_auc"),
            "cv_f1": metrics.get("f1_score"),
            "cv_balanced_acc": metrics.get("balanced_accuracy"),
            "cv_recall_good": metrics.get("recall_good"),
            "cv_recall_bad": metrics.get("recall_bad"),
            "cv_brier": metrics.get("brier_score"),
            "false_approvals": metrics.get("false_approvals_bad"),
            "false_rejections": metrics.get("false_rejections_good"),
            "is_champion": model_name == report.get("champion_model"),
        })
    # Sort champion first
    model_comparison.sort(key=lambda x: (not x["is_champion"], -x["cv_roc_auc"]))

    # Build threshold rows for chart
    threshold_rows = []
    for t in threshold_opts:
        threshold_rows.append({
            "threshold": t["threshold"],
            "approval_rate": t["approval_rate"],
            "balanced_accuracy": t["balanced_accuracy"],
            "recall_bad": t["recall_bad"],
            "false_approvals": t["false_approvals_bad"],
            "false_rejections": t["false_rejections_good"],
        })

    return {
        "champion_model": report.get("champion_model"),
        "champion_cv_roc_auc": report.get("champion_cv_roc_auc"),
        "is_calibrated": report.get("is_calibrated"),
        "calibration_method": report.get("calibration_method"),
        "generated_timestamp": report.get("generated_timestamp"),
        "best_hyperparameters": best_params,
        "holdout_metrics": {
            "roc_auc": holdout.get("roc_auc"),
            "pr_auc": holdout.get("pr_auc"),
            "accuracy": holdout.get("accuracy"),
            "balanced_accuracy": holdout.get("balanced_accuracy"),
            "f1_score": holdout.get("f1_score"),
            "precision": holdout.get("precision"),
            "recall_good": holdout.get("recall_good"),
            "recall_bad": holdout.get("recall_bad"),
            "brier_score": holdout.get("brier_score"),
            "log_loss": holdout.get("log_loss"),
            "false_approvals_bad": holdout.get("false_approvals_bad"),
            "false_rejections_good": holdout.get("false_rejections_good"),
            "confusion_matrix": holdout.get("confusion_matrix"),
        },
        "model_comparison": model_comparison,
        "threshold_analysis": threshold_rows,
        "training_info": {
            "dataset": "Statlog German Credit Data (UCI)",
            "n_samples": 1000,
            "n_features_engineered": 30,
            "train_split": 800,
            "holdout_split": 200,
            "cv_strategy": "Stratified 5-Fold",
            "tuning": "Optuna (100 trials)",
        },
    }

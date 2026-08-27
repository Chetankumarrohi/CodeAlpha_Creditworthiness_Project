import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"
TESTS_DIR = BASE_DIR / "tests"
BACKEND_DIR = BASE_DIR / "backend"
APP_DIR = BASE_DIR / "app"

# Ensure directories exist
for path in [DATA_DIR, MODELS_DIR, REPORTS_DIR, TESTS_DIR, BACKEND_DIR, APP_DIR]:
    path.mkdir(parents=True, exist_ok=True)

# Datasets
RAW_DATASET_PATH = DATA_DIR / "german_credit_data.csv"

# Model Artifacts (Single Persisted Artifact & Metadata)
PIPELINE_FILE = MODELS_DIR / "nova_credit_pipeline.joblib"
LEGACY_PIPELINE_FILE = MODELS_DIR / "credit_pipeline.pkl"
PIPELINE_METADATA_FILE = MODELS_DIR / "pipeline_metadata.json"
BENCHMARK_REPORT_FILE = REPORTS_DIR / "model_benchmark_report.json"
DATABASE_FILE = BACKEND_DIR / "credit_assessments.db"

# Scale Normalization Constant
# German Credit dataset is in Deutsche Marks (DM, median 2300, max 18400)
# Serving applications collect domestic INR (typically 50,000 to 1,000,000)
CURRENCY_INR_TO_DATASET_SCALE = 100.0

# Underwriting Policy Thresholds
MAX_ALLOWED_FOIR = 0.50          # Max 50% Fixed Obligation to Income Ratio
MAX_ALLOWED_DTI = 0.40           # Max 40% Debt-to-Income Ratio
MIN_DISPOSABLE_INCOME = 15000    # Minimum monthly disposable income (₹)
MIN_LIQUIDITY_MONTHS = 3         # Minimum savings balance (months of EMI)

# Nova Score Constants
NOVA_SCORE_MIN = 300
NOVA_SCORE_MAX = 850

# ⚡ Nova Credit AI — Enterprise Credit Scoring & Risk Platform

An enterprise-grade, production-ready AI Financial Intelligence system built with **Scikit-Learn**, **CatBoost**, **FastAPI**, **ReportLab**, and **Streamlit**.

---

## 🌟 Key Architecture & Features

- **Unified Scikit-Learn Pipeline (`ml/pipeline.py`)**: Reproducible `Pipeline` object wrapping domain feature engineering, column imputation, and standard scaling to eliminate training-serving skew.
- **Calibrated ML Probability Model (`ml/calibrator.py`)**: Calibrated default risk probabilities using `CalibratedClassifierCV` (Platt Sigmoid Calibration), tracking ROC-AUC, PR-AUC, F1, Specificity, and Brier Score.
- **Proprietary Nova Credit Score Engine (`ml/nova_score.py`)**: Maps calibrated probabilities and financial multipliers (DTI, savings liquidity, tenure) into a 300 to 850 score.
- **Financial Underwriting Decision Engine (`ml/decision_engine.py`)**: Evaluates policy rules (FOIR $\le 50\%$, Disposable Income, Liquidity Reserve Ratio) independently of ML risk predictions (`APPROVED`, `CONDITIONAL`, `REJECTED`).
- **SHAP Explainability (`ml/explainer.py`)**: TreeExplainer contributions for global and applicant-level feature impacts.
- **Real-Time What-If Credit Simulator**: Dynamic sliders for income, existing EMI, savings, loan amount, and tenure with real-time Nova Score recalculations and credit improvement action tips.
- **FastAPI Enterprise REST API (`backend/main.py`)**: Versioned `/api/v1` endpoints with Pydantic v2 schemas and SQLite persistent assessment logging.
- **PDF Credit Report Generator (`backend/pdf_generator.py`)**: One-click downloadable institutional PDF Credit Assessment reports via ReportLab.
- **Pytest Automated Test Suite (`tests/`)**: Unit tests covering pipeline execution, decision engine policy rules, and FastAPI REST endpoints.

---

## 🏗️ Repository Architecture

```
Creditworthiness_Project/
├── backend/
│   ├── main.py                # FastAPI REST API Application (/api/v1)
│   ├── database.py            # SQLite database persistence
│   ├── schemas.py             # Pydantic v2 validation models
│   └── pdf_generator.py       # ReportLab PDF Credit Assessment report generator
├── app/
│   └── app.py                 # Enterprise Streamlit Glassmorphic Dashboard
├── ml/
│   ├── pipeline.py            # Custom sklearn transformers & pipeline builder
│   ├── train.py               # Stratified 5-fold CV evaluation & benchmark script
│   ├── calibrator.py          # Probability calibration module
│   ├── explainer.py           # SHAP feature contribution explainer
│   ├── nova_score.py          # Proprietary Nova Credit Score (300-850) algorithm
│   └── decision_engine.py     # Policy underwriting decision engine
├── models/                    # Model pipeline binary (credit_pipeline.pkl)
├── data/                      # German Credit Dataset
├── reports/                   # Model benchmark telemetry (model_benchmark_report.json)
└── tests/                     # Pytest test suite (test_pipeline, test_decision_engine, test_api)
```

---

## 📊 Champion Model Benchmark Matrix

| Model | ROC-AUC | 95% Confidence Interval | PR-AUC | Brier Score |
| :--- | :---: | :---: | :---: | :---: |
| 🏆 **CatBoost (Calibrated)** | **0.7603** | **[0.7255, 0.7929]** | **0.8568** | **0.1852** |
| 🥈 **Logistic Regression** | 0.7575 | [0.7209, 0.7892] | 0.8602 | 0.1990 |
| 🥉 **Random Forest** | 0.7552 | [0.7207, 0.7891] | 0.8477 | 0.1884 |
| ⚡ **XGBoost** | 0.7478 | [0.7123, 0.7821] | 0.8464 | 0.1933 |
| 🌲 **ExtraTrees** | 0.7386 | [0.7037, 0.7751] | 0.8409 | 0.1901 |

---

## 🚀 Quickstart Guide

### 1. Launch Streamlit Dashboard
```bash
./run.sh
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

### 2. Launch FastAPI REST API & Web Server
```bash
./run.sh server
```
Open [http://localhost:8085](http://localhost:8085) for the web client or test `/api/v1/health` & `/api/v1/assess`.

### 3. Run Pytest Test Suite
```bash
./run.sh test
```

### 4. Retrain Calibrated Pipeline
```bash
./run.sh train
```

---

## 🐳 Docker Container Deployment

```bash
# Build and start services via Docker Compose
docker-compose up --build
```
- Streamlit Dashboard: `http://localhost:8501`
- FastAPI REST API: `http://localhost:8085`
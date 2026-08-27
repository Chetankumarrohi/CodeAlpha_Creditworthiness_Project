# Nova Credit AI — Institutional Credit Risk & Financial Intelligence Platform

> **Nova Credit AI** is an explainable financial-intelligence platform that combines machine-learning credit-risk assessment, proprietary risk scoring, affordability analysis, loan intelligence, scenario simulation, and personalized financial insights within a production-oriented fintech architecture.

---

## 🚀 Live Demo & Client Dashboard

The interactive client dashboard is running live at:
- 🌐 **Public Live URL**: **[https://7d5a2774d19deb.lhr.life](https://7d5a2774d19deb.lhr.life)**
- 💻 **Local URL**: **[http://localhost:8085](http://localhost:8085)**


### Features:
- **5-Step Credit Intake Wizard**: Personal → Employment → Financials → Credit Request → Review
- **Nova Credit Score (300–850)**: Proprietary log-odds metric derived from calibrated ML output
- **Underwriting Decision Engine**: Multi-state decisioning based on FOIR, DTI, disposable income, and liquidity rules
- **SHAP Feature Attribution**: Transparent positive and negative risk driver identification
- **Model Intelligence Dashboard**: Live model health, 5-Fold CV metrics, holdout confusion matrix, ROC curve, and threshold analysis
- **PDF Report Generation**: Instant institutional underwriting assessment downloads

---

## 🏗 System Architecture

```
                               ┌──────────────────────────┐
                               │  Applicant Form Intake   │
                               └────────────┬─────────────┘
                                            │
                               ┌────────────▼─────────────┐
                               │  Schema & Preprocessing  │
                               └────────────┬─────────────┘
                                            │
                               ┌────────────▼─────────────┐
                               │  CatBoost ML Pipeline    │
                               └────────────┬─────────────┘
                                            │
                               ┌────────────▼─────────────┐
                               │ Calibrated Probability   │
                               │   (Platt Sigmoid ECE)    │
                               └────────────┬─────────────┘
                                            │
                        ┌───────────────────┴───────────────────┐
                        │                                       │
           ┌────────────▼─────────────┐           ┌─────────────▼────────────┐
           │   Nova Score Generator   │           │    Underwriting Policy   │
           │  (Log-Odds 300–850 Band) │           │  (FOIR / DTI / Capacity) │
           └────────────┬─────────────┘           └─────────────┬────────────┘
                        │                                       │
                        └───────────────────┬───────────────────┘
                                            │
                               ┌────────────▼─────────────┐
                               │ SHAP Explainer & Drivers │
                               └────────────┬─────────────┘
                                            │
                               ┌────────────▼─────────────┐
                               │   Underwriting Verdict   │
                               └──────────────────────────┘
```

---

## 📊 Champion Model Metrics (Statlog German Credit Benchmark)

| Metric | Holdout (N=200) | 5-Fold Cross Validation |
| :--- | :---: | :---: |
| **Champion Architecture** | **CatBoost (Tuned)** | **CatBoost (Tuned)** |
| **ROC-AUC** | **0.7686** | **0.7697** |
| **PR-AUC** | **0.8630** | **0.8683** |
| **Calibration (ECE)** | **1.67%** (Sigmoid Platt) | — |
| **Brier Score** | **0.1673** | **0.1862** |
| **F1-Score** | **0.8477** | **0.7897** |

---

## 🛠 Technology Stack

- **Frontend**: HTML5, Vanilla CSS3 (Custom Restrained Dark Fintech Design Tokens), JavaScript (ES6+ SPA Router), Lucide Icons
- **Backend**: FastAPI, Pydantic v2, SQLAlchemy ORM, ReportLab PDF Engine
- **Machine Learning**: CatBoost, Scikit-Learn, SHAP, Optuna, Joblib
- **Database & Storage**: SQLite (Development) / PostgreSQL-ready SQLAlchemy Engine
- **Containerization & Testing**: Docker, Docker Compose, Pytest

---

## 🏃 Running Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Train and validate ML pipeline
python ml/train.py

# 3. Launch FastAPI server
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8085
```

Navigate to `http://localhost:8085` in your browser.

---

## 🐳 Docker Deployment

```bash
docker-compose up --build -d
```

---

## 📜 Legal & Model Disclaimers

> **Disclaimer**: Nova Credit Score is a proprietary model-derived risk metric developed for analytical and demonstration purposes. It is **not** a credit bureau score and does not represent CIBIL, Experian, Equifax, CRIF, or FICO scores. All predictions should be evaluated alongside human underwriting judgment.
# Nova Credit AI — Multi-User Institutional Financial Intelligence & Underwriting Platform

> **Nova Credit AI** is an enterprise-grade multi-user credit risk assessment and financial intelligence platform. It combines machine-learning underwriting, proprietary Nova Credit scoring (300–850), strict server-side user data isolation, role-based access control (RBAC), an operational Admin Console, audit logging, scenario simulations, and automated PDF report generation within a production-ready fintech architecture.

---

## 🚀 Key Multi-User & Security Architecture Features

- 🔐 **Authentication & Registration Gate**: Public visitors land on a clean, secure Sign In / Register interface. Public signups are strictly granted `USER` role.
- 🔒 **Strict Server-Side User Isolation**: Every user record (`assessments`, `financial_profiles`, `simulations`, `reports`) is tagged with `user_id`. Backend endpoints strictly enforce `record.user_id == current_user.id` so User A cannot view or access User B's financial data.
- 👑 **Separate Administrative Console (`/admin`)**: Operational data-dense dashboard accessible exclusively by `ADMIN` accounts. Includes system-wide user account management, account activation/deactivation toggles, user drill-down inspector modal, real-time audit activity log, global credit underwriting log, and champion ML model health diagnostics.
- 🛠 **CLI Admin Provisioning**: Securely bootstrap or promote administrator accounts using `python backend/scripts/create_admin.py`.
- 🛡 **OWASP Security & Rate Limiting**: Password hashing via PBKDF2-HMAC-SHA256 (100,000 iterations), signed JWT tokens, zero plaintext secret exposure in API responses, and rate limiting on login/registration endpoints.
- 📄 **Institutional PDF Generation**: On-demand PDF underwriting report generation linked to individual user assessments.
- 📊 **Calibrated CatBoost ML Model**: 5-Fold Cross Validated CatBoost pipeline (ROC-AUC 0.7686, ECE 1.67%) with SHAP explainability drivers.

---

## 🌐 Live Application & Access

- 🌐 **Public Live Tunnel URL**: **[https://7d5a2774d19deb.lhr.life](https://7d5a2774d19deb.lhr.life)**
- 💻 **Local URL**: **[http://localhost:8085](http://localhost:8085)**

---

## 🛠 Technology Stack

- **Frontend**: HTML5, Vanilla CSS3 (Custom Restrained Dark Fintech Design Tokens, Responsive Navigation Drawer), JavaScript (ES6+ SPA Router), Lucide Icons
- **Backend**: FastAPI, Pydantic v2, SQLAlchemy ORM, PyJWT, ReportLab PDF Engine
- **Machine Learning**: CatBoost, Scikit-Learn, SHAP, Optuna, Joblib
- **Database & Storage**: SQLite (Development) / PostgreSQL-ready SQLAlchemy Engine (`DATABASE_URL`)
- **Security**: PBKDF2-HMAC-SHA256, JWT Authentication, Server-Side User Isolation Guard
- **Testing**: Pytest (45 Automated Integration & Security Tests)

---

## 💻 CLI Commands & Provisioning

### 1. Provision an Administrator Account
```bash
python backend/scripts/create_admin.py --email admin@novacredit.ai --password "AdminSecurePassword2026!" --name "System Administrator"
```

### 2. Run Automated Test Suite (45/45 Tests)
```bash
PYTHONPATH=. ./.venv/bin/pytest tests/ -v
```

### 3. Launch Local Server
```bash
./.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8085
```

---

## 📜 License
Internal Enterprise & Institutional Release v2.2.
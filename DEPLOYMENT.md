# 🚀 Multi-User Deployment & Administration Guide — Nova Credit AI

Production deployment and administrative setup guide for **Nova Credit AI v2.2**.

---

## 1. Environment Configuration

Copy `.env.example` to `.env` and set environment variables:

```bash
cp .env.example .env
```

| Variable | Description | Default |
| :--- | :--- | :--- |
| `DATABASE_URL` | SQLAlchemy connection string | `sqlite:///./data/nova_credit.db` |
| `SECRET_KEY` | 32+ character random secret key for JWT signing | `nova-prod-secret-key-...` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token lifespan in minutes | `120` |
| `ALLOWED_ORIGINS` | CORS origins allowed to access API | `*` |
| `ADMIN_BOOTSTRAP_EMAIL` | Optional initial admin email | `admin@example.com` |
| `ADMIN_BOOTSTRAP_PASSWORD` | Optional initial admin password | `<strong_random_password>` |

---

## 2. Administrator Provisioning CLI

Provision or promote an admin account via command line:

```bash
python backend/scripts/create_admin.py --email <your_admin_email> --password "<your_secure_password>" --name "System Administrator"
```

- Public signups (`/api/v1/auth/register`) strictly assign `role = USER`.
- Administrative access to `/admin` routes requires an account created or promoted via this CLI.

---

## 3. Production Deployment

### FastAPI Application Server
```bash
./.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8085 --workers 4
```

### Docker Deployment
```bash
docker build -t novacredit:v2.2 .
docker run -d -p 8085:8085 --env-file .env novacredit:v2.2
```

---

## 4. Security & Audit Verification

Run the automated Pytest test suite covering authentication, user data isolation, and RBAC admin route protection:

```bash
PYTHONPATH=. ./.venv/bin/pytest tests/ -v
```

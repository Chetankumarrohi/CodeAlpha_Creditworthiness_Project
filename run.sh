#!/bin/bash
# 1-Click Launch Script for Nova Credit AI
set -e

echo "🚀 Starting Nova Credit AI Institutional Platform..."

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    ./.venv/bin/pip install -r requirements.txt
fi

if [ ! -f "models/nova_credit_pipeline.joblib" ]; then
    echo "Training champion ML pipeline..."
    ./.venv/bin/python ml/train.py
fi

echo "Initializing database..."
./.venv/bin/python -c "from backend.app.database.session import init_db; init_db()"

PORT=8085
echo "🌐 Server running live at: http://localhost:${PORT}"
./.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}

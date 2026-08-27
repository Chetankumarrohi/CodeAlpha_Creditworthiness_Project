#!/usr/bin/env bash
set -e

PYTHON_BIN="./.venv/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

echo "⚡ Nova Credit AI Enterprise Launcher"
echo "----------------------------------------"

if [ "$1" == "train" ]; then
    echo "🏋️ Retraining Calibrated ML Pipeline & Cross-Validation Benchmarking..."
    $PYTHON_BIN ml/train.py
elif [ "$1" == "server" ]; then
    echo "🚀 Starting Enterprise FastAPI REST API & Web Client..."
    $PYTHON_BIN -m uvicorn backend.main:app --host 0.0.0.0 --port 8085
elif [ "$1" == "test" ]; then
    echo "🧪 Running Pytest Test Suite..."
    PYTHONPATH=. $PYTHON_BIN -m pytest tests/
else
    echo "🎨 Starting Enterprise Streamlit Dashboard..."
    $PYTHON_BIN -m streamlit run app/app.py
fi

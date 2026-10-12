#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install --no-deps understat==0.1.14
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8765}"

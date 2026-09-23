#!/usr/bin/env sh
set -e
cd /app
alembic upgrade head
python -m app.seed
uvicorn app.main:app --host 0.0.0.0 --port 8000

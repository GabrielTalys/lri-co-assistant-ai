#!/usr/bin/env sh
set -e
cd /app
python -m app.worker.runner

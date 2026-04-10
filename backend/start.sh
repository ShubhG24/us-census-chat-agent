#!/usr/bin/env sh
set -e
# Run uvicorn from the backend directory (where app/ lives), regardless of CWD.
cd "$(dirname "$0")"
PORT="${PORT:-8000}"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"

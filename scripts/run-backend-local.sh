#!/usr/bin/env sh
# Local backend: use Python 3.11 or 3.12 (not 3.14 — Snowflake/pydantic wheels may fail).
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"

PY=""
for cmd in python3.12 python3.11 python3.10; do
  if command -v "$cmd" >/dev/null 2>&1; then
    PY="$cmd"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "Install Python 3.12 (e.g. brew install python@3.12) and retry."
  exit 1
fi

"$PY" -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

# Load backend/.env without breaking zsh (no export \$(grep ...))
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

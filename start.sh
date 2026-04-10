#!/usr/bin/env sh
set -e
# Delegate to backend/start.sh so deploys can use either repo root or backend/ as service root.
ROOT="$(CDPATH='' cd -- "$(dirname "$0")" && pwd)"
exec sh "$ROOT/backend/start.sh"

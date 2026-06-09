#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

exec python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8765

#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "==> Postgres (Docker)…"
docker compose up -d postgres

echo "==> Attente Postgres…"
for i in $(seq 1 40); do
  if docker compose exec -T postgres pg_isready -U audio -d audio_db >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

cd "$ROOT/backend"
python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate
pip install -q -r requirements.txt
python init_db.py
echo "==> API http://127.0.0.1:8000  (admin@local.dev / admin123)"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

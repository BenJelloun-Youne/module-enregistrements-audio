#!/usr/bin/env bash
# Lance l'API audio hors Docker (Postgres déjà démarré par scripts/run.mjs).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"

PYTHON="${AUDIO_PYTHON:-python3.12}"
PORT="${PORT:-${AUDIO_API_PORT:-8000}}"

if [[ ! -d venv ]]; then
  "$PYTHON" -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install -q -r requirements.txt
python init_db.py
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --reload

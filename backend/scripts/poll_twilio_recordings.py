#!/usr/bin/env python3
"""Cron / CLI — poll Twilio pour les nouveaux enregistrements Concentrix.

Exemples :
  python scripts/poll_twilio_recordings.py
  python scripts/poll_twilio_recordings.py --from 2026-08-01 --to 2026-08-10 --limit 20
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal  # noqa: E402
from app.services import audio_pipeline_service as pipeline  # noqa: E402
from app.services.audio_seed import ensure_audio_config_seed  # noqa: E402
from app import models_audio  # noqa: F401, E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll Twilio recordings → Concentrix pipeline")
    parser.add_argument("--from", dest="date_from", default=None)
    parser.add_argument("--to", dest="date_to", default=None)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--no-process", action="store_true", help="Ingest only, no LLM")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        ensure_audio_config_seed(db)
        result = pipeline.sync_new_recordings(
            db,
            date_from=args.date_from,
            date_to=args.date_to,
            process=not args.no_process,
            limit=args.limit,
        )
        print(result)
        return 0 if result.get("errors", 0) == 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

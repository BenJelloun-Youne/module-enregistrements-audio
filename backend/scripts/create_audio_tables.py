"""Crée uniquement les tables audio_* / reactivation_* via SQLAlchemy.

Usage (depuis la racine backend du SaaS, PYTHONPATH=. ) :

    python -c "from app.database import Base, engine; from app import models_audio; Base.metadata.create_all(bind=engine)"

Ou exécuter schema/001_audio_tables.sql.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app import models_audio  # noqa: F401, E402
from app.services.audio_seed import ensure_audio_config_seed  # noqa: E402


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print(ensure_audio_config_seed(db))
    finally:
        db.close()
    print("OK — tables audio + seed structure (prompts vides)")


if __name__ == "__main__":
    main()

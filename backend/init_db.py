"""Crée les tables + un admin (aucun autre seed métier)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from app.auth import get_password_hash
from app.database import Base, SessionLocal, engine
from app.models import User, UserRole
from app import models_audio  # noqa: F401
from app.services.audio_seed import ensure_audio_config_seed


def init_db():
    admin_email = (os.environ.get("ADMIN_EMAIL") or "admin@local.dev").strip()
    admin_password = os.environ.get("ADMIN_PASSWORD") or "admin123"

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        ensure_audio_config_seed(db)
        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin = User(
                email=admin_email,
                hashed_password=get_password_hash(admin_password),
                full_name="Admin",
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin)
            db.commit()
            print(f"Admin créé : {admin_email}")
        else:
            print(f"Admin déjà présent : {admin_email}")
    except Exception as exc:
        db.rollback()
        print(f"Erreur init : {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_db()

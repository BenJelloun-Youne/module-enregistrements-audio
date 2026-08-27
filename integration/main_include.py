"""Snippet à coller dans backend/app/main.py du SaaS cible.

Ne remplace PAS le main existant : ajoute seulement ces imports / include_router / seed.
"""

# 1) Importer les modèles pour que SQLAlchemy crée les tables audio_*
from app import models_audio  # noqa: F401

# 2) Routers du module
from app.routers import admin_enregistrements  # noqa: E402
from app.routers import webhooks_twilio  # noqa: E402
from app.routers import webhooks_reactivation  # noqa: E402

# 3) Après Base.metadata.create_all(bind=engine) :
from app.database import SessionLocal
from app.services.audio_seed import ensure_audio_config_seed

_seed_db = SessionLocal()
try:
    ensure_audio_config_seed(_seed_db)
finally:
    _seed_db.close()

# 4) Monter les routers (même préfixes que Concentrix)
app.include_router(admin_enregistrements.router)   # /api/admin/enregistrements
app.include_router(webhooks_twilio.router)         # /api/webhooks/twilio
app.include_router(webhooks_reactivation.router)   # /api/webhooks-reactivation

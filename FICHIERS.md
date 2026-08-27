# Mapping

L’instance Concentrix n’a pas été touchée.

Ce dossier est désormais une **appli complète** (BDD + auth + API + frontend),
plus les extraits métier copiés depuis Concentrix.

## Architecture fournie ici (pour le dev sans SaaS)

- `docker-compose.yml` + `Dockerfile` — Postgres + FastAPI
- `backend/app/main.py` `database.py` `auth.py` `models.py` `schemas.py`
- `backend/app/routers/auth.py` — login / me
- `backend/init_db.py` — tables + admin
- `frontend/index.html` `js/app.js` `js/auth.js` `js/sidebar-nav.js`

## Métier copié depuis Concentrix

| Source Concentrix | Package |
|-------------------|---------|
| backend/app/models_audio.py | idem |
| backend/app/routers/admin_enregistrements.py | idem |
| backend/app/routers/webhooks_twilio.py | idem |
| backend/app/routers/webhooks_reactivation.py | idem |
| backend/app/services/audio_*.py | idem |
| backend/app/services/reactivation_webhook_*.py | idem |
| frontend-static pages/js critères + enregistrements | frontend/ |

Aucun `.env` Concentrix (Twilio / OpenAI) n’est copié.

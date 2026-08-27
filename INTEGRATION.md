# Deux modes

## A. Projet autonome (recommandé si tu n’as pas de SaaS)

Le dossier **est déjà** une appli complète : Postgres + FastAPI + login + 2 pages.

```bash
docker compose up --build
# http://127.0.0.1:8000   admin@local.dev / admin123
```

Rien d’autre à installer (sauf Docker).

## B. Fusion dans un SaaS Smart Convers déjà existant

Copier seulement le métier (ne pas remplacer `main.py` / `auth.py` / `app.js`).

### Backend

```
backend/app/models_audio.py
backend/app/routers/admin_enregistrements.py
backend/app/routers/webhooks_twilio.py
backend/app/routers/webhooks_reactivation.py
backend/app/services/audio_*.py
backend/app/services/reactivation_webhook_*.py
backend/app/services/whatsapp_textmebot.py
```

Coller `integration/main_include.py` dans le `main.py` cible.

### Frontend

```
pages/enregistrements-relances.html
pages/criteres-analyse-audio.html
js/enregistrements-relances.js
js/criteres-analyse-audio.js
css/reactivation-sc.css
```

Ajouter le menu (`integration/sidebar-nav.snippet.js`) et autoriser les chemins dans `checkAuth` du SaaS.

Le SaaS doit déjà exposer `window.API` (`get/post/put/delete`) + JWT `localStorage.token`.

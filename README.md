# Enregistrements & Relances + Critères d'analyse audio

Projet **autonome** (même architecture Smart Convers / Concentrix) :

- Postgres
- FastAPI + JWT admin
- Frontend HTML/JS (login + 2 pages)
- Pipeline Twilio → OpenAI → tables `audio_*`

Le développeur n’a **besoin de rien d’autre** : BDD, auth, API, UI, SQL, Docker.

L’instance Concentrix en production **n’a pas été modifiée**.

---

## Démarrage (le plus simple)

Prérequis : Docker.

```bash
git clone <URL_DU_REPO>
cd module-enregistrements-audio
cp backend/env.example backend/.env   # optionnel, pour lancer sans Docker
docker compose up --build
```

Puis ouvrir **http://127.0.0.1:8000**

| | |
|--|--|
| Email | `admin@local.dev` |
| Mot de passe | `admin123` |

Ça crée Postgres, les tables, l’admin, et sert le frontend.

Sans Docker Compose pour le backend (Postgres seul) :

```bash
chmod +x start.sh
./start.sh
```

---

## Pages

| URL | Rôle |
|-----|------|
| `/` | Login JWT |
| `/pages/enregistrements-relances.html` | Dashboard KPI, sync Twilio, funnel relances |
| `/pages/criteres-analyse-audio.html` | Prompts LLM + critères qualité |

Après login : « Charger modèle Orange » (critères) puis « Synchroniser Twilio » (enregistrements).

Tant que les prompts `codif` sont vides, les recordings restent en `needs_prompts`.

---

## Architecture (identique Concentrix)

```
Navigateur
   │  JWT Bearer  (localStorage.token)
   ▼
FastAPI  app/main.py
   ├── /api/auth/login  /me
   ├── /api/admin/enregistrements/*     (admin JWT)
   ├── /api/webhooks/twilio/recording   (token query)
   └── /api/webhooks-reactivation       (token query)
           │
           ▼
     Postgres  audio_db
           ├── users
           ├── audio_prompt_templates
           ├── audio_criteria
           ├── audio_recordings
           ├── audio_analyses
           ├── reactivation_leads
           └── reactivation_webhook_calls
```

Pipeline :

```
Twilio Recording
  → audio_recordings (pending → downloading → analyzing → done)
  → OpenAI prompt "codif"
  → si conversation : OpenAI prompt "criteres" + règles admin
  → audio_analyses
  → GET /dashboard  → page Relances
```

---

## Tables (SQL prêt)

Fichier : `schema/001_audio_tables.sql` (idempotent).

Au runtime, `Base.metadata.create_all` + `python init_db.py` suffisent (tables + admin + seed prompts **vides**).

---

## Variables d'environnement

`backend/.env` (déjà rempli pour la démo locale).

À renseigner pour le vrai pipeline :

```
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WEBHOOK_TOKEN=
OPENAI_API_KEY=
REACTIVATION_WEBHOOK_TOKEN=
```

Webhook Twilio :

`POST http://<host>:8000/api/webhooks/twilio/recording?token=<TWILIO_WEBHOOK_TOKEN>`

---

## Arborescence

```
module-enregistrements-audio/
├── docker-compose.yml          Postgres 5433 + API 8000
├── Dockerfile
├── start.sh
├── schema/001_audio_tables.sql
├── backend/
│   ├── .env                    démo (pas les secrets Concentrix)
│   ├── requirements.txt
│   ├── init_db.py              tables + admin
│   └── app/
│       ├── main.py
│       ├── database.py         SQLAlchemy + DATABASE_URL
│       ├── models.py           User / UserRole
│       ├── models_audio.py     7 tables audio / relances
│       ├── auth.py             JWT + get_current_admin_user
│       ├── schemas.py
│       ├── routers/            auth, admin_enregistrements, webhooks
│       └── services/           pipeline, Twilio, dashboard, seed
└── frontend/
    ├── index.html              login
    ├── pages/                  2 pages métier
    ├── js/                     app.js (API+JWT), auth, sidebar, pages
    └── css/
```

---

## API admin (JWT)

Préfixe `/api/admin/enregistrements`

- `GET/PUT /config/prompts`
- `GET/POST/PUT/DELETE /config/criteria`
- `POST /config/load-orange-defaults`
- `GET /dashboard?week=all`
- `POST /sync`  `POST /ingest`  `POST /{id}/reprocess`

Détail : `integration/API.md`

---

## Fusion dans un autre SaaS Smart Convers

Si le SaaS a déjà `app/database.py`, `app/auth.py`, `app/models.py` User :

1. Copier `models_audio.py`, routers audio, services audio
2. `include_router` (voir `integration/main_include.py`)
3. Copier les 2 pages + JS + `css/reactivation-sc.css`

Ne **pas** écraser le `main.py` / `app.js` existants — seulement ajouter.

---

## Comptes / secrets

- Compte démo uniquement (`admin@local.dev` / `admin123`) — à changer en prod (`ADMIN_EMAIL` / `ADMIN_PASSWORD` / `SECRET_KEY`).
- Aucun secret Concentrix (Twilio / OpenAI) n’est dans ce dossier.

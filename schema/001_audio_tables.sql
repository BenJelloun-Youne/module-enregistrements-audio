-- =============================================================================
-- Module Enregistrements & Relances + Critères d'analyse audio
-- Postgres (JSONB). Idempotent : CREATE TABLE IF NOT EXISTS.
-- Source : concentrix/backend/app/models_audio.py + users (auth JWT)
-- =============================================================================

-- 0) Auth (même contrat Smart Convers : role admin)
DO $$ BEGIN
    CREATE TYPE userrole AS ENUM ('user', 'admin', 'client', 'broker');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR NOT NULL UNIQUE,
    hashed_password VARCHAR NOT NULL,
    full_name       VARCHAR,
    is_active       BOOLEAN DEFAULT TRUE,
    role            userrole DEFAULT 'user',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_users_id    ON users (id);
CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

-- 1) Prompts LLM paramétrables (codif / criteres)
CREATE TABLE IF NOT EXISTS audio_prompt_templates (
    id              SERIAL PRIMARY KEY,
    key             VARCHAR(64) NOT NULL UNIQUE,
    label           VARCHAR(255) NOT NULL,
    description     TEXT,
    system_prompt   TEXT NOT NULL DEFAULT '',
    user_prompt     TEXT NOT NULL DEFAULT '',
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_audio_prompt_templates_id  ON audio_prompt_templates (id);
CREATE INDEX IF NOT EXISTS ix_audio_prompt_templates_key ON audio_prompt_templates (key);

-- 2) Critères qualité évalués par le 2e prompt (injectés via {CRITERES_RULES})
CREATE TABLE IF NOT EXISTS audio_criteria (
    id              SERIAL PRIMARY KEY,
    key             VARCHAR(64) NOT NULL UNIQUE,
    label           VARCHAR(255) NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_audio_criteria_id  ON audio_criteria (id);
CREATE INDEX IF NOT EXISTS ix_audio_criteria_key ON audio_criteria (key);

-- 3) Enregistrements Twilio (1 ligne = 1 appel capté)
CREATE TABLE IF NOT EXISTS audio_recordings (
    id              SERIAL PRIMARY KEY,
    recording_sid   VARCHAR(64) NOT NULL,
    call_sid        VARCHAR(64),
    phone           VARCHAR(32),
    direction       VARCHAR(32),
    from_number     VARCHAR(32),
    to_number       VARCHAR(32),
    duration_sec    DOUBLE PRECISION,
    channels        INTEGER,
    recorded_at     TIMESTAMPTZ,
    media_url       TEXT,
    local_path      TEXT,
    status          VARCHAR(32) NOT NULL DEFAULT 'pending',
    error_message   TEXT,
    source          VARCHAR(32) NOT NULL DEFAULT 'twilio',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_audio_recording_sid UNIQUE (recording_sid)
);
CREATE INDEX IF NOT EXISTS ix_audio_recordings_id           ON audio_recordings (id);
CREATE INDEX IF NOT EXISTS ix_audio_recordings_recording_sid ON audio_recordings (recording_sid);
CREATE INDEX IF NOT EXISTS ix_audio_recordings_call_sid     ON audio_recordings (call_sid);
CREATE INDEX IF NOT EXISTS ix_audio_recordings_phone        ON audio_recordings (phone);
CREATE INDEX IF NOT EXISTS ix_audio_recordings_recorded_at  ON audio_recordings (recorded_at);
CREATE INDEX IF NOT EXISTS ix_audio_recordings_status       ON audio_recordings (status);

-- Statuts pipeline (colonne status) :
--   pending | downloading | analyzing | done | error | skipped | needs_prompts

-- 4) Résultat d'analyse OpenAI (1:1 avec audio_recordings)
CREATE TABLE IF NOT EXISTS audio_analyses (
    id                      SERIAL PRIMARY KEY,
    recording_id            INTEGER NOT NULL UNIQUE
                            REFERENCES audio_recordings(id) ON DELETE CASCADE,
    codification            VARCHAR(64),
    vente_conclue           BOOLEAN,
    score_qualite           INTEGER,
    deroule                 TEXT,
    posture                 VARCHAR(32),
    offre_proposee          BOOLEAN,
    champs_lead_redemandes  BOOLEAN,
    ton_conseiller          VARCHAR(32),
    ecoute_active           VARCHAR(32),
    closing                 VARCHAR(32),
    points_forts            JSONB,
    axes_amelioration       JSONB,
    criteres_result         JSONB,
    codif_raw               JSONB,
    tokens_json             JSONB,
    analyzed_at             TIMESTAMPTZ DEFAULT NOW(),
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_audio_analyses_id           ON audio_analyses (id);
CREATE INDEX IF NOT EXISTS ix_audio_analyses_recording_id ON audio_analyses (recording_id);
CREATE INDEX IF NOT EXISTS ix_audio_analyses_codification ON audio_analyses (codification);

-- 5) Leads réactivés (webhook JSON) — alimente l'entonnoir de la page Relances
CREATE TABLE IF NOT EXISTS reactivation_leads (
    id                      SERIAL PRIMARY KEY,
    dedupe_key              VARCHAR(128),
    source                  VARCHAR(64) NOT NULL DEFAULT 'default',
    payload                 JSONB NOT NULL,
    headers                 JSONB,
    lead_external_id        BIGINT,
    phone                   VARCHAR(32),
    campaign_external_id    BIGINT,
    supplier_external_id    BIGINT,
    status_id               INTEGER,
    received_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_reactivation_leads_id                   ON reactivation_leads (id);
CREATE INDEX IF NOT EXISTS ix_reactivation_leads_dedupe_key           ON reactivation_leads (dedupe_key);
CREATE INDEX IF NOT EXISTS ix_reactivation_leads_source               ON reactivation_leads (source);
CREATE INDEX IF NOT EXISTS ix_reactivation_leads_lead_external_id     ON reactivation_leads (lead_external_id);
CREATE INDEX IF NOT EXISTS ix_reactivation_leads_phone                ON reactivation_leads (phone);
CREATE INDEX IF NOT EXISTS ix_reactivation_leads_campaign_external_id ON reactivation_leads (campaign_external_id);
CREATE INDEX IF NOT EXISTS ix_reactivation_leads_supplier_external_id ON reactivation_leads (supplier_external_id);
CREATE INDEX IF NOT EXISTS ix_reactivation_leads_status_id            ON reactivation_leads (status_id);
CREATE INDEX IF NOT EXISTS ix_reactivation_leads_received_at          ON reactivation_leads (received_at);

-- 6) Historique de chaque POST webhook réactivation (OK / échec)
CREATE TABLE IF NOT EXISTS reactivation_webhook_calls (
    id                      SERIAL PRIMARY KEY,
    source                  VARCHAR(64) NOT NULL DEFAULT 'default',
    ok                      BOOLEAN NOT NULL DEFAULT FALSE,
    http_status             INTEGER NOT NULL DEFAULT 201,
    error                   TEXT,
    client_ip               VARCHAR(64),
    lead_external_id        BIGINT,
    campaign_external_id    BIGINT,
    stored                  INTEGER NOT NULL DEFAULT 0,
    created                 INTEGER NOT NULL DEFAULT 0,
    updated                 INTEGER NOT NULL DEFAULT 0,
    payload_preview         TEXT,
    received_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_reactivation_webhook_calls_id                   ON reactivation_webhook_calls (id);
CREATE INDEX IF NOT EXISTS ix_reactivation_webhook_calls_source               ON reactivation_webhook_calls (source);
CREATE INDEX IF NOT EXISTS ix_reactivation_webhook_calls_ok                   ON reactivation_webhook_calls (ok);
CREATE INDEX IF NOT EXISTS ix_reactivation_webhook_calls_http_status          ON reactivation_webhook_calls (http_status);
CREATE INDEX IF NOT EXISTS ix_reactivation_webhook_calls_client_ip            ON reactivation_webhook_calls (client_ip);
CREATE INDEX IF NOT EXISTS ix_reactivation_webhook_calls_lead_external_id     ON reactivation_webhook_calls (lead_external_id);
CREATE INDEX IF NOT EXISTS ix_reactivation_webhook_calls_campaign_external_id ON reactivation_webhook_calls (campaign_external_id);
CREATE INDEX IF NOT EXISTS ix_reactivation_webhook_calls_received_at          ON reactivation_webhook_calls (received_at);

-- 7) Optionnel — présent dans models_audio.py mais NON utilisé par les 2 pages
--    (gardé pour parité de schéma si le SaaS cible reprend le fichier tel quel)
CREATE TABLE IF NOT EXISTS qualification_leads (
    id                      SERIAL PRIMARY KEY,
    source                  VARCHAR(64) NOT NULL DEFAULT 'default',
    payload                 JSONB NOT NULL,
    headers                 JSONB,
    lead_external_id        BIGINT,
    phone                   VARCHAR(32),
    campaign_external_id    BIGINT,
    supplier_external_id    BIGINT,
    status_id               INTEGER,
    received_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_qualification_leads_id                   ON qualification_leads (id);
CREATE INDEX IF NOT EXISTS ix_qualification_leads_source               ON qualification_leads (source);
CREATE INDEX IF NOT EXISTS ix_qualification_leads_lead_external_id     ON qualification_leads (lead_external_id);
CREATE INDEX IF NOT EXISTS ix_qualification_leads_phone                ON qualification_leads (phone);
CREATE INDEX IF NOT EXISTS ix_qualification_leads_campaign_external_id ON qualification_leads (campaign_external_id);
CREATE INDEX IF NOT EXISTS ix_qualification_leads_supplier_external_id ON qualification_leads (supplier_external_id);
CREATE INDEX IF NOT EXISTS ix_qualification_leads_status_id            ON qualification_leads (status_id);
CREATE INDEX IF NOT EXISTS ix_qualification_leads_received_at          ON qualification_leads (received_at);

-- Seed structure (prompts/critères VIDES) — aussi fait par ensure_audio_config_seed()
INSERT INTO audio_prompt_templates (key, label, description, system_prompt, user_prompt, enabled)
VALUES
    ('codif',    'Codification appel (analyse globale)',           'Analyse complète : codif, vente, posture, offre, objections, score qualité.', '', '', TRUE),
    ('criteres', 'Évaluation critères qualité (posture / offre / champs)', 'Évalue les critères actifs. Placeholder {CRITERES_RULES}.', '', '', TRUE)
ON CONFLICT (key) DO NOTHING;

INSERT INTO audio_criteria (key, label, description, enabled, sort_order)
VALUES
    ('posture_ok',        'Posture agent (présentation marque)', '', TRUE, 10),
    ('offre_ok',          'Offre non imposée à l''accueil',      '', TRUE, 20),
    ('champs_redemandes', 'Champs lead redemandés',              '', TRUE, 30)
ON CONFLICT (key) DO NOTHING;

# Contrats API — pages ↔ backend

Base URL frontend : `/api` (voir `window.API` / `api-client.minimal.js`).
Toutes les routes admin exigent un JWT **admin**.

## Critères d'analyse audio (`criteres-analyse-audio.js`)

```
GET  /admin/enregistrements/config/prompts
PUT  /admin/enregistrements/config/prompts/{id}
     body: { system_prompt?, user_prompt?, enabled?, label?, description? }

GET  /admin/enregistrements/config/criteria
POST /admin/enregistrements/config/criteria
     body: { key, label, description?, enabled?, sort_order? }
     key : ^[a-z][a-z0-9_]{1,63}$
PUT  /admin/enregistrements/config/criteria/{id}
DELETE /admin/enregistrements/config/criteria/{id}

POST /admin/enregistrements/config/load-orange-defaults?overwrite=true
```

## Enregistrements et relances (`enregistrements-relances.js`)

```
GET  /admin/enregistrements/dashboard?week=all
GET  /admin/enregistrements/dashboard?week=YYYY-MM-DD   # lundi ISO
POST /admin/enregistrements/sync?async=true
     body: { process: true, limit: 50, date_from?, date_to? }
```

Le dashboard renvoie `{ data, view, weeks }`.
Le frontend n'utilise que `view` pour le rendu KPI + `data.reactivation.recordings`
pour le tableau brut.

### Forme de `view` (champs consommés par le JS)

- Funnel : `leadsReactives`, `called`, `joints`, `ventes`, `joinPct`, `ventePct`, `nonPris`
- KPI : `liv`, `joi`, `ven`, `joiPct`, `tvPct`, `incrJoi`, `incrTv`, `vap`
- Critères : `postureOk/postureN`, `offreOk/offreN`, `champsRedemandes/champsN`
- Prod : `nRec`, `n300`, `call300`, `p1`, `welcomeEnvoyes`, `welcomeCalled`, `welcomeVentes`
- Tableaux : `analyseRows[]`, `webhookCalls[]`

## Webhooks (pas de JWT — token statique)

Twilio form-urlencoded ou JSON Event Streams :

```
POST /api/webhooks/twilio/recording?token=$TWILIO_WEBHOOK_TOKEN
     RecordingSid=RExxx&RecordingStatus=completed
→ 200 texte "ok" immédiat, ingest + analyse en background
```

Réactivation JSON :

```
POST /api/webhooks-reactivation?token=$REACTIVATION_WEBHOOK_TOKEN
     { ...lead }  ou  { "leads": [ ... ] }
→ 201 { stored, created, updated, ids }
```

Token aussi accepté en header `X-Webhook-Token` ou `Authorization: Bearer`.

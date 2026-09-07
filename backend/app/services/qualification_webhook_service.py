"""Ingestion webhook retours qualification — JSON → table ``qualification_leads``."""
from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy.orm import Session

from app.models_audio import QualificationLead
from app.services.reactivation_webhook_service import (
    extract_lead_fields,
    iter_lead_payloads,
)

logger = logging.getLogger(__name__)


def _vente_status_ids() -> set[int]:
    """Lit QUALIFICATION_VENTE_STATUS_IDS (virgule-séparée) depuis l'env."""
    raw = os.getenv("QUALIFICATION_VENTE_STATUS_IDS", "").strip()
    if not raw:
        return set()
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


def insert_qualification_lead(
    db: Session,
    payload: Any,
    *,
    source: str,
    headers: dict[str, Any] | None,
) -> QualificationLead:
    """Toujours une nouvelle ligne : 1 POST = 1 retour qualification."""
    fields = extract_lead_fields(payload if isinstance(payload, dict) else {})
    row = QualificationLead(
        source=source or "default",
        payload=payload,
        headers=headers,
        lead_external_id=fields.get("lead_external_id"),
        phone=fields.get("phone"),
        campaign_external_id=fields.get("campaign_external_id"),
        supplier_external_id=fields.get("supplier_external_id"),
        status_id=fields.get("status_id"),
    )
    db.add(row)
    return row


def store_qualification_payloads(
    db: Session,
    body: Any,
    *,
    source: str,
    headers: dict[str, Any] | None,
) -> dict[str, Any]:
    items = iter_lead_payloads(body)
    if not items:
        return {"stored": 0, "created": 0, "ids": []}

    created = 0
    ids: list[int] = []
    for item in items:
        row = insert_qualification_lead(db, item, source=source, headers=headers)
        created += 1
        db.flush()
        ids.append(row.id)

    db.commit()
    logger.info(
        "Webhook qualification source=%s stored=%s created=%s",
        source,
        len(ids),
        created,
    )
    return {"stored": len(ids), "created": created, "ids": ids}


def get_vente_phones(db: Session) -> set[str]:
    """Retourne l'ensemble des numéros de téléphone ayant un status_id de Vente.

    Les status_id éligibles sont définis par QUALIFICATION_VENTE_STATUS_IDS (env).
    Renvoie un set vide si la variable est absente ou vide.
    """
    vente_ids = _vente_status_ids()
    if not vente_ids:
        logger.debug("QUALIFICATION_VENTE_STATUS_IDS vide — aucun comptage depuis qualification_leads")
        return set()

    rows = (
        db.query(QualificationLead.phone)
        .filter(
            QualificationLead.status_id.in_(vente_ids),
            QualificationLead.phone.isnot(None),
        )
        .all()
    )
    return {r.phone for r in rows if r.phone}

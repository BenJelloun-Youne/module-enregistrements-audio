"""Ingestion webhook leads réactivés — JSON → table ``reactivation_leads``."""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models_audio import ReactivationLead

logger = logging.getLogger(__name__)

_PHONE_KEYS = (
    "phone",
    "telephone",
    "mobile",
    "tel",
    "phoneNumber",
    "phone_number",
    "Phone",
    "Telephone",
    "msisdn",
    "numero",
    "numero_tel",
    "mobilePhone",
)
_LEAD_ID_KEYS = (
    "leadId", "lead_id", "leadID", "LeadId", "lead_external_id",
    # CRM crm.workflow.event (top-level + execution.generatedLeadDataId via sub-object lookup)
    "generatedLeadDataId",
    # Hopti sms.success
    "deliveryId",
)
_CAMPAIGN_KEYS = ("campaignId", "campaign_id", "campaignID", "CampaignId")
_SUPPLIER_KEYS = ("supplierId", "supplier_id", "brokerId", "broker_id", "SupplierId")
_STATUS_KEYS = ("statusId", "status_id", "status", "StatusId")


def _try_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _norm_phone(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    digits = re.sub(r"\D+", "", raw)
    if len(digits) < 8:
        return None
    return digits[-15:]


def _candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [payload]
    for key in ("payload", "lead", "data", "event", "Lead", "Data", "Payload"):
        sub = payload.get(key)
        if isinstance(sub, dict):
            out.append(sub)
            nested = sub.get("data")
            if isinstance(nested, dict):
                out.append(nested)
    return out


def _pick(cands: list[dict[str, Any]], keys: tuple[str, ...]) -> Any:
    for c in cands:
        for k in keys:
            if k in c and c[k] not in (None, ""):
                return c[k]
    return None


def extract_lead_fields(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    cands = _candidates(payload)

    # --- lead_external_id ---
    lead_id = _try_int(_pick(cands, _LEAD_ID_KEYS))
    if lead_id is None:
        # CRM crm.workflow.event : execution.generatedLeadDataId
        execution = payload.get("execution")
        if isinstance(execution, dict):
            lead_id = _try_int(execution.get("generatedLeadDataId"))
        # CRM : lead.dataId
        if lead_id is None:
            lead_obj = payload.get("lead")
            if isinstance(lead_obj, dict):
                lead_id = _try_int(lead_obj.get("dataId"))
    if lead_id is None and "event" not in payload:
        lead_id = _try_int(_pick(cands, ("id", "ID")))

    # --- phone ---
    phone = _norm_phone(_pick(cands, _PHONE_KEYS))
    if not phone:
        # CRM : individual.phone / individual.telephone
        individual = payload.get("individual")
        if isinstance(individual, dict):
            phone = _norm_phone(_pick([individual], _PHONE_KEYS))
    if not phone:
        inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        data = inner.get("data") if isinstance(inner, dict) else payload.get("data")
        if isinstance(data, dict):
            phone = _norm_phone(data.get("12") or data.get(12))

    # --- campaign_external_id ---
    campaign_id = _try_int(_pick(cands, _CAMPAIGN_KEYS))
    if campaign_id is None:
        # CRM : campaign.internalId
        campaign = payload.get("campaign")
        if isinstance(campaign, dict):
            campaign_id = _try_int(campaign.get("internalId"))

    return {
        "lead_external_id": lead_id,
        "phone": phone,
        "campaign_external_id": campaign_id,
        "supplier_external_id": _try_int(_pick(cands, _SUPPLIER_KEYS)),
        "status_id": _try_int(_pick(cands, _STATUS_KEYS)),
    }


def iter_lead_payloads(body: Any) -> list[Any]:
    """Accepte un lead, une liste, ou {leads|data|items: [...]}."""
    if isinstance(body, list):
        return [item for item in body if item is not None]
    if isinstance(body, dict):
        for key in ("leads", "items", "records"):
            arr = body.get(key)
            if isinstance(arr, list):
                return [item for item in arr if item is not None]
        data = body.get("data")
        if isinstance(data, list):
            return [item for item in data if item is not None]
        return [body]
    return []


def insert_reactivation_lead(
    db: Session,
    payload: Any,
    *,
    source: str,
    headers: dict[str, Any] | None,
) -> ReactivationLead:
    """Toujours une nouvelle ligne : 1 POST = 1 lead, même en doublon."""
    fields = extract_lead_fields(payload if isinstance(payload, dict) else {})
    row = ReactivationLead(
        dedupe_key=f"recv:{uuid.uuid4()}",
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


def store_reactivation_payloads(
    db: Session,
    body: Any,
    *,
    source: str,
    headers: dict[str, Any] | None,
) -> dict[str, Any]:
    items = iter_lead_payloads(body)
    if not items:
        return {"stored": 0, "created": 0, "updated": 0, "ids": []}

    created = 0
    updated = 0
    ids: list[int] = []
    for item in items:
        row = insert_reactivation_lead(db, item, source=source, headers=headers)
        created += 1
        db.flush()
        ids.append(row.id)

    db.commit()
    logger.info(
        "Webhook réactivation source=%s stored=%s created=%s updated=%s",
        source,
        len(ids),
        created,
        updated,
    )
    return {"stored": len(ids), "created": created, "updated": updated, "ids": ids}


def count_reactivation_leads(db: Session) -> int:
    return int(db.query(ReactivationLead).count() or 0)

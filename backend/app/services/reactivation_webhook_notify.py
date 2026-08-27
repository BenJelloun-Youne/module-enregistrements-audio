"""Historique + alerte WhatsApp (TextMeBot) pour le webhook réactivation."""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models_audio import ReactivationWebhookCall
from app.services.reactivation_webhook_service import extract_lead_fields
from app.services.whatsapp_textmebot import send_whatsapp_text_async

logger = logging.getLogger(__name__)


def _client_ip(request: Request) -> Optional[str]:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded[:64]
    if request.client and request.client.host:
        return str(request.client.host)[:64]
    return None


def _preview(payload: Any) -> Optional[str]:
    if payload is None:
        return None
    try:
        raw = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        raw = str(payload)
    if len(raw) > 800:
        return raw[:800] + "…"
    return raw


def list_reactivation_calls(db: Session, *, limit: int = 80) -> list[dict[str, Any]]:
    rows = (
        db.query(ReactivationWebhookCall)
        .order_by(ReactivationWebhookCall.id.desc())
        .limit(limit)
        .all()
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "ok": bool(r.ok),
                "http_status": r.http_status,
                "error": r.error,
                "source": r.source,
                "client_ip": r.client_ip,
                "lead_external_id": r.lead_external_id,
                "campaign_external_id": r.campaign_external_id,
                "stored": r.stored,
                "created": r.created,
                "updated": r.updated,
                "received_at": r.received_at.isoformat() if r.received_at else None,
            }
        )
    return out


def log_reactivation_call(
    db: Session,
    request: Request,
    *,
    source: str,
    ok: bool,
    http_status: int,
    error: Optional[str] = None,
    payload: Any = None,
    stored: int = 0,
    created: int = 0,
    updated: int = 0,
) -> ReactivationWebhookCall:
    fields = extract_lead_fields(payload) if isinstance(payload, dict) else {}
    row = ReactivationWebhookCall(
        source=source or "default",
        ok=ok,
        http_status=http_status,
        error=(str(error)[:2000] if error else None),
        client_ip=_client_ip(request),
        lead_external_id=fields.get("lead_external_id"),
        campaign_external_id=fields.get("campaign_external_id"),
        stored=stored,
        created=created,
        updated=updated,
        payload_preview=_preview(payload),
    )
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        logger.exception("Impossible d'enregistrer l'historique webhook réactivation")
        raise
    _notify_whatsapp(row, fields)
    return row


def _notify_whatsapp(row: ReactivationWebhookCall, fields: dict[str, Any]) -> None:
    lead = row.lead_external_id or "—"
    camp = row.campaign_external_id or "—"
    phone = fields.get("phone") or "—"
    if row.ok:
        text = (
            "✅ Concentrix · webhook réactivation OK\n"
            f"Lead {lead} · campagne {camp} · tél. {phone}\n"
            f"Stocké {row.stored} (créé {row.created} / maj {row.updated})"
        )
    else:
        err = row.error or "erreur"
        text = (
            "❌ Concentrix · webhook réactivation ÉCHEC\n"
            f"HTTP {row.http_status} · {err}\n"
            f"Lead {lead} · campagne {camp}"
        )
    try:
        send_whatsapp_text_async(text)
    except Exception:
        logger.exception("Alerte WhatsApp réactivation ignorée")

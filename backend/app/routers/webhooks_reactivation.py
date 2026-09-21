"""Webhook public — leads réactivés (JSON stocké en continu dans Postgres).

Protégé par token statique ``REACTIVATION_WEBHOOK_TOKEN`` :
    POST /api/webhooks-reactivation?token=...
    POST /api/webhooks-reactivation/{source}?token=...

Le token est aussi accepté en header ``X-Webhook-Token`` ou ``Authorization: Bearer``.

Accepte deux formats :

1. **Legacy JSON direct** (lead, liste, ou {leads: [...]}) → 201.
   Comportement historique inchangé.

2. **Enveloppe push Pub/Sub GCP** → 204 (ACK).
   Les subscriptions push (CRM + Hopti) pointent toutes vers cet endpoint.
   Le payload JSON est extrait de ``message.data`` (base64), stocké dans
   ``reactivation_leads``. Le routage par ``event`` dérive automatiquement
   le ``source`` (crm / hopti) si le path param /{source} n'est pas précisé.

   - ``crm.workflow.event`` (topic crm-workflow-events) : step SEND_WEBHOOK / SEND_SMS
   - ``sms.success``        (topic hopti-sms-success)   : welcome SMS accepté

Chaque POST est historisé dans ``reactivation_webhook_calls``.
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.pubsub_push_util import (
    EVENT_CRM_WORKFLOW,
    EVENT_SMS_SUCCESS,
    PubSubDecodeError,
    decode_pubsub,
    is_pubsub_envelope,
)
from app.services.reactivation_webhook_notify import log_reactivation_call
from app.services.reactivation_webhook_service import store_reactivation_payloads

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks-reactivation", tags=["webhooks-reactivation"])


def _expected_token() -> str:
    return (os.getenv("REACTIVATION_WEBHOOK_TOKEN") or "").strip()


def _provided_token(request: Request) -> str:
    q = (request.query_params.get("token") or "").strip()
    if q:
        return q
    header = (request.headers.get("x-webhook-token") or "").strip()
    if header:
        return header
    auth = (request.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def _require_token(request: Request) -> None:
    expected = _expected_token()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook non configuré",
        )
    provided = _provided_token(request)
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")


def _safe_log(db: Session, request: Request, **kwargs: Any) -> None:
    try:
        log_reactivation_call(db, request, **kwargs)
    except Exception:
        logger.exception("Historique webhook réactivation non enregistré")


def _source_from_event(event_type: str | None, path_source: str) -> str:
    """Dérive le source depuis le type d'event si le path param est absent/default."""
    if path_source and path_source != "default":
        return path_source
    if event_type == EVENT_CRM_WORKFLOW:
        return "crm"
    if event_type == EVENT_SMS_SUCCESS:
        return "hopti"
    return path_source or "default"


def _enrich_headers(request: Request, *, msg_id: str, subscription: str, publish_time: str, attributes: dict[str, str]) -> dict[str, Any]:
    headers = dict(request.headers)
    headers["pubsub_message_id"] = msg_id
    headers["pubsub_subscription"] = subscription
    headers["pubsub_publish_time"] = publish_time
    headers["pubsub_attributes"] = attributes
    return headers


async def _store(path_source: str, request: Request, db: Session) -> Response | dict[str, Any]:
    body: Any = None
    try:
        _require_token(request)
        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payload JSON invalide",
            ) from exc

        # ── Enveloppe Pub/Sub ────────────────────────────────────────────────
        if is_pubsub_envelope(body):
            try:
                msg = decode_pubsub(body)
            except PubSubDecodeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                ) from exc

            source = _source_from_event(msg.event_type, path_source)
            headers = _enrich_headers(
                request,
                msg_id=msg.message_id,
                subscription=msg.subscription,
                publish_time=msg.publish_time,
                attributes=msg.attributes,
            )

            result = store_reactivation_payloads(
                db,
                msg.payload,
                source=source,
                headers=headers,
            )
            _safe_log(
                db,
                request,
                source=source,
                ok=True,
                http_status=status.HTTP_204_NO_CONTENT,
                payload=msg.payload,
                stored=int(result.get("stored") or 0),
                created=int(result.get("created") or 0),
                updated=int(result.get("updated") or 0),
            )
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        # ── Legacy JSON direct ───────────────────────────────────────────────
        source = path_source or "default"
        result = store_reactivation_payloads(
            db,
            body,
            source=source,
            headers=dict(request.headers),
        )
        _safe_log(
            db,
            request,
            source=source,
            ok=True,
            http_status=status.HTTP_201_CREATED,
            payload=body,
            stored=int(result.get("stored") or 0),
            created=int(result.get("created") or 0),
            updated=int(result.get("updated") or 0),
        )
        return {
            "message": "Leads réactivés stockés",
            "source": source,
            **result,
        }

    except HTTPException as exc:
        _safe_log(
            db,
            request,
            source=path_source or "default",
            ok=False,
            http_status=exc.status_code,
            error=str(exc.detail),
            payload=body,
        )
        raise
    except Exception as exc:
        _safe_log(
            db,
            request,
            source=path_source or "default",
            ok=False,
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error=str(exc)[:500],
            payload=body,
        )
        raise


@router.get("")
def reactivation_webhook_alive(request: Request):
    _require_token(request)
    return {
        "status": "ok",
        "message": (
            "POST un JSON direct (lead / liste) ou une enveloppe push Pub/Sub GCP "
            "(crm.workflow.event → 204, sms.success → 204, legacy → 201)."
        ),
    }


@router.head("")
def reactivation_webhook_head(request: Request):
    """Les outils type n8n/Make sondent en HEAD avant le POST."""
    _require_token(request)
    return Response(status_code=200)


@router.post("", status_code=status.HTTP_201_CREATED)
async def receive_reactivation_default(request: Request, db: Session = Depends(get_db)):
    result = await _store(path_source="default", request=request, db=db)
    if isinstance(result, Response):
        return result
    return result


@router.post("/{source}", status_code=status.HTTP_201_CREATED)
async def receive_reactivation_with_source(
    source: str, request: Request, db: Session = Depends(get_db)
):
    result = await _store(path_source=source, request=request, db=db)
    if isinstance(result, Response):
        return result
    return result

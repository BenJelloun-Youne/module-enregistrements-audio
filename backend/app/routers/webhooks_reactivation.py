"""Webhook public — leads réactivés (JSON stocké en continu dans Postgres).

Protégé par token statique ``REACTIVATION_WEBHOOK_TOKEN`` :
    POST /api/webhooks-reactivation?token=...
    POST /api/webhooks-reactivation/{source}?token=...

Le token est aussi accepté en header ``X-Webhook-Token`` ou ``Authorization: Bearer``.
Chaque POST est historisé ; alerte WhatsApp TextMeBot si OK ou échec.
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
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


async def _store(source: str, request: Request, db: Session) -> dict[str, Any]:
    payload: Any = None
    try:
        _require_token(request)
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payload JSON invalide",
            ) from exc

        result = store_reactivation_payloads(
            db,
            payload,
            source=source or "default",
            headers=dict(request.headers),
        )
        _safe_log(
            db,
            request,
            source=source or "default",
            ok=True,
            http_status=status.HTTP_201_CREATED,
            payload=payload,
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
            source=source or "default",
            ok=False,
            http_status=exc.status_code,
            error=str(exc.detail),
            payload=payload,
        )
        raise
    except Exception as exc:
        _safe_log(
            db,
            request,
            source=source or "default",
            ok=False,
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error=str(exc)[:500],
            payload=payload,
        )
        raise


@router.get("")
def reactivation_webhook_alive(request: Request):
    _require_token(request)
    return {
        "status": "ok",
        "message": "POST un JSON (lead, liste, ou {leads: [...]}) pour le stocker.",
    }


@router.head("")
def reactivation_webhook_head(request: Request):
    """Les outils type n8n/Make sondent en HEAD avant le POST."""
    _require_token(request)
    return Response(status_code=200)


@router.post("", status_code=status.HTTP_201_CREATED)
async def receive_reactivation_default(request: Request, db: Session = Depends(get_db)):
    return await _store(source="default", request=request, db=db)


@router.post("/{source}", status_code=status.HTTP_201_CREATED)
async def receive_reactivation_with_source(
    source: str, request: Request, db: Session = Depends(get_db)
):
    return await _store(source=source, request=request, db=db)

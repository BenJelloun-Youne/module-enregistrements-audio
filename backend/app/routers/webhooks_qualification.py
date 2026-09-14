"""Webhook public — retours qualification (JSON stocké dans qualification_leads).

Protégé par token statique ``QUALIFICATION_WEBHOOK_TOKEN`` :
    POST /api/webhooks-qualification?token=...
    POST /api/webhooks-qualification/{source}?token=...

Le token est aussi accepté en header ``X-Webhook-Token`` ou ``Authorization: Bearer``.
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.qualification_webhook_service import store_qualification_payloads

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks-qualification", tags=["webhooks-qualification"])


def _expected_token() -> str:
    return (os.getenv("QUALIFICATION_WEBHOOK_TOKEN") or "").strip()


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
            detail="Webhook non configuré (QUALIFICATION_WEBHOOK_TOKEN manquant)",
        )
    provided = _provided_token(request)
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")


async def _store(source: str, request: Request, db: Session) -> dict[str, Any]:
    _require_token(request)
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload JSON invalide",
        ) from exc

    result = store_qualification_payloads(
        db,
        payload,
        source=source or "default",
        headers=dict(request.headers),
    )
    return {
        "message": "Retours qualification stockés",
        "source": source,
        **result,
    }


@router.get("")
def qualification_webhook_alive(request: Request):
    _require_token(request)
    return {
        "status": "ok",
        "message": "POST un JSON (lead, liste, ou {leads: [...]}) pour stocker les retours qualification.",
    }


@router.head("")
def qualification_webhook_head(request: Request):
    """Compatibilité n8n/Make qui sondent en HEAD avant le POST."""
    _require_token(request)
    return Response(status_code=200)


@router.post("", status_code=status.HTTP_201_CREATED)
async def receive_qualification_default(request: Request, db: Session = Depends(get_db)):
    return await _store(source="default", request=request, db=db)


@router.post("/{source}", status_code=status.HTTP_201_CREATED)
async def receive_qualification_with_source(
    source: str, request: Request, db: Session = Depends(get_db)
):
    return await _store(source=source, request=request, db=db)

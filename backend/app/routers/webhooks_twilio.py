"""Webhook Twilio → pipeline Concentrix (download MP3 + analyse OpenAI).

Twilio (TwiML / REST RecordingStatusCallback ou Event Streams) POST ici
dès qu'un enregistrement est ``completed``.

    POST /api/webhooks/twilio/recording?token=...

Réponse immédiate ``ok`` (texte). L'ingest + analyse tourne en arrière-plan.
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Request, status
from fastapi.responses import PlainTextResponse, JSONResponse

from app.database import SessionLocal
from app.services import audio_pipeline_service as pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks/twilio", tags=["webhooks-twilio"])

_FINAL_STATUSES = {"completed", "absent", ""}


def _expected_token() -> str:
    return (os.getenv("TWILIO_WEBHOOK_TOKEN") or "").strip()


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


def _require_token(request: Request) -> Optional[PlainTextResponse]:
    expected = _expected_token()
    if not expected:
        return PlainTextResponse("webhook non configuré", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    provided = _provided_token(request)
    if not provided or not hmac.compare_digest(provided, expected):
        return PlainTextResponse("forbidden", status_code=status.HTTP_403_FORBIDDEN)
    return None


def _pick_sid(data: dict[str, Any]) -> Optional[str]:
    for key in ("RecordingSid", "recording_sid", "recordingSid", "sid"):
        val = data.get(key)
        if isinstance(val, str) and val.startswith("RE") and len(val) >= 32:
            return val.strip()
    nested = data.get("data")
    if isinstance(nested, dict):
        return _pick_sid(nested)
    payload = data.get("payload")
    if isinstance(payload, dict):
        return _pick_sid(payload)
    return None


def _pick_status(data: dict[str, Any]) -> str:
    for key in ("RecordingStatus", "recording_status", "recordingStatus", "status"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().lower()
    event_type = str(data.get("type") or "").lower()
    if "recording" in event_type and "completed" in event_type:
        return "completed"
    nested = data.get("data")
    if isinstance(nested, dict):
        return _pick_status(nested)
    return ""


def _pick_call_sid(data: dict[str, Any]) -> Optional[str]:
    for key in ("CallSid", "call_sid", "callSid"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    nested = data.get("data")
    if isinstance(nested, dict):
        return _pick_call_sid(nested)
    return None


def _bg_ingest(recording_sid: str) -> None:
    db = SessionLocal()
    try:
        row = pipeline.ingest_twilio_recording_sid(db, recording_sid, process=True)
        logger.info(
            "Twilio ingest done sid=%s status=%s analysis=%s",
            recording_sid,
            getattr(row, "status", None),
            bool(getattr(row, "analysis", None)),
        )
    except Exception:
        logger.exception("Webhook Twilio ingest failed for %s", recording_sid)
    finally:
        db.close()


@router.api_route("/call-completed", methods=["GET", "HEAD", "POST"])
async def call_completed_callback(request: Request):
    """StatusCallback d'appel (TwiML). On ACK tout de suite ; l'audio arrive via /recording."""
    denied = _require_token(request)
    if denied:
        return denied
    if request.method == "HEAD":
        return PlainTextResponse("", status_code=200)
    logger.info("Twilio call-completed ACK method=%s", request.method)
    return PlainTextResponse("ok")


@router.get("/recording")
def recording_webhook_alive(request: Request):
    denied = _require_token(request)
    if denied:
        return denied
    return JSONResponse(
        {
            "status": "ok",
            "message": "POST form-urlencoded (RecordingSid + RecordingStatus=completed) ou JSON Event Streams.",
        }
    )


@router.post("/recording", response_class=PlainTextResponse)
async def recording_status_callback(request: Request, background_tasks: BackgroundTasks):
    denied = _require_token(request)
    if denied:
        return denied

    ctype = (request.headers.get("content-type") or "").lower()
    data: dict[str, Any] = {}
    if "json" in ctype:
        try:
            body = await request.json()
            if isinstance(body, dict):
                data = body
        except Exception:
            data = {}
    else:
        try:
            form = await request.form()
            data = {k: (v if isinstance(v, str) else str(v)) for k, v in form.items()}
        except Exception:
            data = {}

    recording_sid = _pick_sid(data)
    recording_status = _pick_status(data)
    call_sid = _pick_call_sid(data)

    if not recording_sid:
        return PlainTextResponse("missing RecordingSid", status_code=status.HTTP_400_BAD_REQUEST)

    if recording_status and recording_status not in _FINAL_STATUSES:
        logger.info("Twilio recording %s status=%s — ignore", recording_sid, recording_status)
        return PlainTextResponse("ignored")

    background_tasks.add_task(_bg_ingest, recording_sid)
    logger.info("Twilio recording queued: %s (call=%s status=%s)", recording_sid, call_sid, recording_status or "completed")
    return PlainTextResponse("ok")

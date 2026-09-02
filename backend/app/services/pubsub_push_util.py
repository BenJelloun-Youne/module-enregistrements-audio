"""Décode l'enveloppe push Pub/Sub GCP standard.

Format reçu (subscription push) :
    {
      "message": {
        "data": "<base64(JSON)>",
        "attributes": { "X-Hipto-Event": "sms.success", ... },
        "messageId": "...",
        "publishTime": "..."
      },
      "subscription": "projects/.../subscriptions/..."
    }
"""
from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Any

EVENT_CRM_WORKFLOW = "crm.workflow.event"
EVENT_SMS_SUCCESS = "sms.success"


class PubSubDecodeError(ValueError):
    """Enveloppe ou payload invalide — renvoyer 400 pour éviter les retries infinis GCP."""


@dataclass(frozen=True)
class PubSubMessage:
    payload: Any
    attributes: dict[str, str]
    message_id: str
    subscription: str
    publish_time: str
    event_type: str | None


def is_pubsub_envelope(body: Any) -> bool:
    """Renvoie True si body est une enveloppe push Pub/Sub GCP valide."""
    if not isinstance(body, dict):
        return False
    message = body.get("message")
    if not isinstance(message, dict):
        return False
    data = message.get("data")
    return isinstance(data, str) and bool(data.strip())


def decode_pubsub(body: dict[str, Any]) -> PubSubMessage:
    """Décode l'enveloppe et renvoie le payload JSON + métadonnées.

    Raises PubSubDecodeError si base64 ou JSON invalide (→ HTTP 400).
    """
    message = body["message"]
    try:
        raw = base64.b64decode(str(message["data"]).strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise PubSubDecodeError("message.data: base64 invalide") from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PubSubDecodeError("message.data: JSON UTF-8 invalide") from exc

    attrs_raw = message.get("attributes") or {}
    attrs: dict[str, str] = (
        {str(k): str(v) for k, v in attrs_raw.items()}
        if isinstance(attrs_raw, dict)
        else {}
    )

    # Priorité : attribut GCP > champ "event" dans le payload JSON
    event_type: str | None = (
        (attrs.get("X-Hipto-Event") or attrs.get("event") or "").strip()
        or (
            str(payload.get("event") or "").strip()
            if isinstance(payload, dict)
            else ""
        )
    ) or None

    return PubSubMessage(
        payload=payload,
        attributes=attrs,
        message_id=str(message.get("messageId") or ""),
        subscription=str(body.get("subscription") or ""),
        publish_time=str(message.get("publishTime") or ""),
        event_type=event_type,
    )

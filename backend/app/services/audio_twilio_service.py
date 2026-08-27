"""Client Twilio Recordings pour Concentrix (sans BigQuery)."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterator, Optional

import requests

logger = logging.getLogger(__name__)

TWILIO_API = "https://api.twilio.com"

try:
    from zoneinfo import ZoneInfo

    PARIS = ZoneInfo("Europe/Paris")
except Exception:  # pragma: no cover
    PARIS = timezone.utc


def twilio_credentials() -> tuple[str, str]:
    sid = (
        os.getenv("TWILIO_ACCOUNT_SID")
        or os.getenv("account_sid_ia")
        or ""
    ).strip()
    token = (
        os.getenv("TWILIO_AUTH_TOKEN")
        or os.getenv("auth_token_ia")
        or ""
    ).strip()
    if not sid or not token:
        raise RuntimeError(
            "Credentials Twilio manquants (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN)"
        )
    if not sid.startswith("AC"):
        raise RuntimeError(f"TWILIO_ACCOUNT_SID invalide (doit commencer par AC…): {sid[:8]}…")
    return sid, token


def audio_storage_dir() -> Path:
    raw = (os.getenv("AUDIO_STORAGE_DIR") or "").strip()
    if raw:
        path = Path(raw)
    else:
        path = Path(__file__).resolve().parents[2] / "data" / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def twilio_session() -> requests.Session:
    sid, token = twilio_credentials()
    s = requests.Session()
    s.auth = (sid, token)
    s.headers.update({"User-Agent": "concentrix-audio-pipeline/1.0"})
    return s


def to_paris(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        dt = parsedate_to_datetime(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(PARIS)
    except Exception:
        return None


def is_finalized(rec: dict[str, Any]) -> bool:
    dur = str(rec.get("duration"))
    return dur not in ("-1", "0", "None", "") and (rec.get("status") in (None, "completed"))


def iter_recordings(
    session: requests.Session,
    sid: str,
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Iterator[dict[str, Any]]:
    params: dict[str, Any] = {"PageSize": 200}
    if date_from:
        params["DateCreated>"] = date_from
    if date_to:
        params["DateCreated<"] = date_to
    url: Optional[str] = f"{TWILIO_API}/2010-04-01/Accounts/{sid}/Recordings.json"
    while url:
        r = session.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        for rec in data.get("recordings", []):
            yield rec
        nxt = data.get("next_page_uri")
        url = (TWILIO_API + nxt) if nxt else None
        params = None  # type: ignore[assignment]


def fetch_recording(session: requests.Session, sid: str, recording_sid: str) -> dict[str, Any]:
    url = f"{TWILIO_API}/2010-04-01/Accounts/{sid}/Recordings/{recording_sid}.json"
    r = session.get(url, timeout=60)
    r.raise_for_status()
    return r.json()


def fetch_call(session: requests.Session, sid: str, call_sid: str) -> dict[str, Any]:
    url = f"{TWILIO_API}/2010-04-01/Accounts/{sid}/Calls/{call_sid}.json"
    r = session.get(url, timeout=60)
    r.raise_for_status()
    return r.json()


def client_phone_from_call(call: dict[str, Any]) -> str:
    direction = (call.get("direction") or "").lower()
    if "outbound" in direction:
        return (call.get("to") or "").strip()
    return (call.get("from") or "").strip()


def download_mp3(
    session: requests.Session,
    media_url: str,
    dest: Path,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = media_url if media_url.endswith(".mp3") else media_url + ".mp3"
    with session.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        tmp.replace(dest)
    return dest


def enrich_recording_meta(session: requests.Session, account_sid: str, rec: dict[str, Any]) -> dict[str, Any]:
    """Normalise un recording Twilio + call associé."""
    call_sid = rec.get("call_sid") or ""
    call: dict[str, Any] = {}
    if call_sid:
        try:
            call = fetch_call(session, account_sid, call_sid)
        except Exception as exc:
            logger.warning("Call %s introuvable: %s", call_sid, exc)

    phone = client_phone_from_call(call) if call else ""
    media = rec.get("media_url") or (
        f"{TWILIO_API}/2010-04-01/Accounts/{account_sid}/Recordings/{rec.get('sid')}"
    )
    try:
        duration = float(rec.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    try:
        channels = int(rec.get("channels") or 1)
    except (TypeError, ValueError):
        channels = 1

    return {
        "recording_sid": rec.get("sid") or "",
        "call_sid": call_sid or None,
        "phone": phone or None,
        "direction": call.get("direction"),
        "from_number": call.get("from"),
        "to_number": call.get("to"),
        "duration_sec": duration,
        "channels": channels,
        "recorded_at": to_paris(rec.get("date_created")),
        "media_url": media,
        "status_twilio": rec.get("status"),
    }

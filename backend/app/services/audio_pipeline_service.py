"""Pipeline analyse audio Concentrix — Twilio → OpenAI → Postgres (pas de BigQuery)."""
from __future__ import annotations

import base64
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models_audio import (
    AudioAnalysis,
    AudioCriterion,
    AudioPromptTemplate,
    AudioRecording,
    AudioRecordingStatus,
)
from app.services import audio_twilio_service as twilio
from app.services.audio_seed import ensure_audio_config_seed

logger = logging.getLogger(__name__)

CONV_CODIFS = {"Vente", "Pre-vente", "Refus", "Deja Orange", "Rappel perso", "Probleme fiche"}


def _openai_client():
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY manquant")
    from openai import OpenAI

    return OpenAI(api_key=api_key)


def _parse_json_content(txt: str, client) -> dict[str, Any]:
    raw = (txt or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].lstrip("json").strip()
    try:
        return json.loads(raw)
    except Exception:
        fix = client.chat.completions.create(
            model=os.getenv("OPENAI_JSON_FIX_MODEL", "gpt-4o-mini"),
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Reformate ce texte en JSON STRICTEMENT valide "
                        "(mêmes clés/valeurs) :\n\n" + raw
                    ),
                }
            ],
        )
        return json.loads(fix.choices[0].message.content or "{}")


def _prompts_ready(db: Session) -> tuple[Optional[AudioPromptTemplate], bool]:
    ensure_audio_config_seed(db)
    codif = (
        db.query(AudioPromptTemplate)
        .filter(AudioPromptTemplate.key == "codif", AudioPromptTemplate.enabled.is_(True))
        .first()
    )
    if not codif:
        return None, False
    ready = bool((codif.system_prompt or "").strip() and (codif.user_prompt or "").strip())
    return codif, ready


def _build_criteres_rules(db: Session) -> str:
    rows = (
        db.query(AudioCriterion)
        .filter(AudioCriterion.enabled.is_(True))
        .order_by(AudioCriterion.sort_order.asc(), AudioCriterion.id.asc())
        .all()
    )
    if not rows:
        return "(aucun critère actif)"
    lines = []
    for r in rows:
        desc = (r.description or "").strip() or "(règle non renseignée — à compléter dans Admin)"
        lines.append(f'- "{r.key}" ({r.label}) : {desc}')
    return "\n".join(lines)


def _analyze_audio_with_prompts(
    client,
    *,
    audio_path: Path,
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    model = model or os.getenv("OPENAI_AUDIO_MODEL", "gpt-audio-mini")
    b64 = base64.b64encode(audio_path.read_bytes()).decode()
    r = client.chat.completions.create(
        model=model,
        modalities=["text"],
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "input_audio", "input_audio": {"data": b64, "format": "mp3"}},
                ],
            },
        ],
    )
    data = _parse_json_content(r.choices[0].message.content or "", client)
    u = r.usage
    tokens = {
        "in": getattr(u, "prompt_tokens", 0) or 0,
        "out": getattr(u, "completion_tokens", 0) or 0,
        "audio": getattr(getattr(u, "prompt_tokens_details", None), "audio_tokens", 0) or 0,
    }
    data["_tokens"] = tokens
    return data, tokens


def upsert_recording_from_meta(db: Session, meta: dict[str, Any], *, source: str = "twilio") -> AudioRecording:
    sid = meta["recording_sid"]
    row = db.query(AudioRecording).filter(AudioRecording.recording_sid == sid).first()
    if not row:
        row = AudioRecording(recording_sid=sid, source=source)
        db.add(row)
    row.call_sid = meta.get("call_sid")
    row.phone = meta.get("phone")
    row.direction = meta.get("direction")
    row.from_number = meta.get("from_number")
    row.to_number = meta.get("to_number")
    row.duration_sec = meta.get("duration_sec")
    row.channels = meta.get("channels")
    row.recorded_at = meta.get("recorded_at")
    row.media_url = meta.get("media_url")
    if row.status in (None, "", AudioRecordingStatus.ERROR.value):
        row.status = AudioRecordingStatus.PENDING.value
        row.error_message = None
    db.commit()
    db.refresh(row)
    return row


def ensure_local_audio(db: Session, recording: AudioRecording) -> Path:
    if recording.local_path and Path(recording.local_path).is_file():
        return Path(recording.local_path)

    if not recording.media_url:
        raise RuntimeError("media_url manquant")

    recording.status = AudioRecordingStatus.DOWNLOADING.value
    db.commit()

    session = twilio.twilio_session()
    account_sid, _ = twilio.twilio_credentials()
    dest_dir = twilio.audio_storage_dir()
    phone_safe = re.sub(r"[^\d+]", "", recording.phone or "unknown") or "unknown"
    ts = (recording.recorded_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d-%H-%M")
    dest = dest_dir / f"{recording.recording_sid}_{ts}_{phone_safe}.mp3"
    twilio.download_mp3(session, recording.media_url, dest)
    recording.local_path = str(dest)
    db.commit()
    return dest


def _save_analysis(db: Session, recording: AudioRecording, codif: dict[str, Any], criteres: Optional[dict[str, Any]]) -> AudioAnalysis:
    analysis = recording.analysis
    if not analysis:
        analysis = AudioAnalysis(recording_id=recording.id)
        db.add(analysis)

    analysis.codification = codif.get("codification")
    analysis.vente_conclue = codif.get("vente_conclue")
    try:
        analysis.score_qualite = int(codif.get("score_qualite")) if codif.get("score_qualite") is not None else None
    except (TypeError, ValueError):
        analysis.score_qualite = None
    analysis.deroule = codif.get("deroule")
    analysis.posture = codif.get("posture")
    analysis.offre_proposee = codif.get("offre_24_99_proposee")
    analysis.champs_lead_redemandes = codif.get("champs_lead_redemandes")
    analysis.ton_conseiller = codif.get("ton_conseiller")
    analysis.ecoute_active = codif.get("ecoute_active")
    analysis.closing = codif.get("closing")
    analysis.points_forts = codif.get("points_forts")
    analysis.axes_amelioration = codif.get("axes_amelioration")
    analysis.criteres_result = criteres
    analysis.codif_raw = {k: v for k, v in codif.items() if k != "_tokens"}
    tokens = {"codif": codif.get("_tokens")}
    if criteres and criteres.get("_tokens"):
        tokens["criteres"] = criteres.get("_tokens")
    analysis.tokens_json = tokens
    analysis.analyzed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(analysis)
    return analysis


def process_recording(db: Session, recording_id: int, *, force: bool = False) -> AudioRecording:
    """Télécharge + analyse un enregistrement. Stocke tout en base locale."""
    recording = db.query(AudioRecording).filter(AudioRecording.id == recording_id).first()
    if not recording:
        raise ValueError(f"recording {recording_id} introuvable")

    if recording.status == AudioRecordingStatus.DONE.value and recording.analysis and not force:
        return recording

    codif_tpl, ready = _prompts_ready(db)
    if not ready:
        recording.status = AudioRecordingStatus.NEEDS_PROMPTS.value
        recording.error_message = (
            "Prompts d'analyse vides — renseigner la page Critères d'analyse audio"
        )
        db.commit()
        db.refresh(recording)
        return recording

    try:
        path = ensure_local_audio(db, recording)
        recording.status = AudioRecordingStatus.ANALYZING.value
        recording.error_message = None
        db.commit()

        client = _openai_client()
        assert codif_tpl is not None
        codif, _ = _analyze_audio_with_prompts(
            client,
            audio_path=path,
            system_prompt=codif_tpl.system_prompt,
            user_prompt=codif_tpl.user_prompt,
        )

        criteres_out: Optional[dict[str, Any]] = None
        crit_tpl = (
            db.query(AudioPromptTemplate)
            .filter(AudioPromptTemplate.key == "criteres", AudioPromptTemplate.enabled.is_(True))
            .first()
        )
        codif_label = str(codif.get("codification") or "")
        if (
            crit_tpl
            and (crit_tpl.system_prompt or "").strip()
            and (crit_tpl.user_prompt or "").strip()
            and codif_label in CONV_CODIFS
        ):
            rules = _build_criteres_rules(db)
            user_prompt = (
                crit_tpl.user_prompt
                .replace("{CRITERES_RULES}", rules)
                .replace("{LEAD_CTX}", "Aucune info CRM connue pour ce lead.")
            )
            criteres_out, _ = _analyze_audio_with_prompts(
                client,
                audio_path=path,
                system_prompt=crit_tpl.system_prompt,
                user_prompt=user_prompt,
            )

        _save_analysis(db, recording, codif, criteres_out)
        recording.status = AudioRecordingStatus.DONE.value
        recording.error_message = None
        db.commit()
    except Exception as exc:
        logger.exception("Échec analyse recording %s", recording_id)
        recording.status = AudioRecordingStatus.ERROR.value
        recording.error_message = str(exc)[:500]
        db.commit()

    db.refresh(recording)
    return recording


def ingest_twilio_recording_sid(db: Session, recording_sid: str, *, process: bool = True) -> AudioRecording:
    session = twilio.twilio_session()
    account_sid, _ = twilio.twilio_credentials()
    rec = twilio.fetch_recording(session, account_sid, recording_sid)
    if not twilio.is_finalized(rec):
        meta = twilio.enrich_recording_meta(session, account_sid, rec)
        row = upsert_recording_from_meta(db, meta)
        row.status = AudioRecordingStatus.SKIPPED.value
        row.error_message = "Enregistrement Twilio non finalisé / durée nulle"
        db.commit()
        db.refresh(row)
        return row

    meta = twilio.enrich_recording_meta(session, account_sid, rec)
    row = upsert_recording_from_meta(db, meta)
    if process:
        return process_recording(db, row.id)
    return row


def sync_new_recordings(
    db: Session,
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    process: bool = True,
    limit: int = 100,
) -> dict[str, int]:
    """Poll Twilio : crée les recordings absents, lance le pipeline."""
    session = twilio.twilio_session()
    account_sid, _ = twilio.twilio_credentials()
    created = processed = skipped = errors = 0

    for rec in twilio.iter_recordings(session, account_sid, date_from=date_from, date_to=date_to):
        if created + skipped + errors >= limit:
            break
        sid = rec.get("sid")
        if not sid:
            continue
        exists = db.query(AudioRecording.id).filter(AudioRecording.recording_sid == sid).first()
        if exists:
            continue
        if not twilio.is_finalized(rec):
            skipped += 1
            continue
        try:
            meta = twilio.enrich_recording_meta(session, account_sid, rec)
            row = upsert_recording_from_meta(db, meta)
            created += 1
            if process:
                process_recording(db, row.id)
                processed += 1
        except Exception as exc:
            logger.exception("sync recording %s: %s", sid, exc)
            errors += 1

    return {
        "created": created,
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
    }

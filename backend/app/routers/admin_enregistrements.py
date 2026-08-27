"""API admin — Enregistrements / relances + critères d'analyse audio."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app import auth, models
from app.database import SessionLocal, get_db
from app.models_audio import AudioAnalysis, AudioCriterion, AudioPromptTemplate, AudioRecording
from app.services import audio_pipeline_service as pipeline
from app.services.audio_dashboard_service import build_dashboard_payload
from app.services.audio_seed import apply_orange_defaults, ensure_audio_config_seed

router = APIRouter(prefix="/api/admin/enregistrements", tags=["admin-enregistrements"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class PromptTemplateOut(BaseModel):
    id: int
    key: str
    label: str
    description: Optional[str] = None
    system_prompt: str
    user_prompt: str
    enabled: bool
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PromptTemplateUpdate(BaseModel):
    label: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt: Optional[str] = None
    enabled: Optional[bool] = None


class CriterionOut(BaseModel):
    id: int
    key: str
    label: str
    description: str
    enabled: bool
    sort_order: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CriterionUpdate(BaseModel):
    label: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    sort_order: Optional[int] = None


class CriterionCreate(BaseModel):
    key: str = Field(..., min_length=2, max_length=64)
    label: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    enabled: bool = True
    sort_order: int = 0


class AnalysisOut(BaseModel):
    id: int
    codification: Optional[str] = None
    vente_conclue: Optional[bool] = None
    score_qualite: Optional[int] = None
    deroule: Optional[str] = None
    posture: Optional[str] = None
    offre_proposee: Optional[bool] = None
    champs_lead_redemandes: Optional[bool] = None
    ton_conseiller: Optional[str] = None
    ecoute_active: Optional[str] = None
    closing: Optional[str] = None
    points_forts: Optional[Any] = None
    axes_amelioration: Optional[Any] = None
    criteres_result: Optional[Any] = None
    analyzed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RecordingOut(BaseModel):
    id: int
    recording_sid: str
    call_sid: Optional[str] = None
    phone: Optional[str] = None
    direction: Optional[str] = None
    duration_sec: Optional[float] = None
    channels: Optional[int] = None
    recorded_at: Optional[datetime] = None
    status: str
    error_message: Optional[str] = None
    source: str
    created_at: Optional[datetime] = None
    analysis: Optional[AnalysisOut] = None

    class Config:
        from_attributes = True


class RecordingDetailOut(RecordingOut):
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    media_url: Optional[str] = None
    local_path: Optional[str] = None
    codif_raw: Optional[Any] = None
    tokens_json: Optional[Any] = None


class StatsOut(BaseModel):
    total: int
    by_status: dict[str, int]
    by_codification: dict[str, int]


class SyncBody(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    process: bool = True
    limit: int = Field(50, ge=1, le=500)


class IngestBody(BaseModel):
    recording_sid: str
    process: bool = True


# ── Helpers ──────────────────────────────────────────────────────────────────


def _bg_process(recording_id: int, force: bool = False) -> None:
    db = SessionLocal()
    try:
        pipeline.process_recording(db, recording_id, force=force)
    finally:
        db.close()


# ── Critères / prompts ───────────────────────────────────────────────────────


@router.get("/config/prompts", response_model=List[PromptTemplateOut])
def list_prompts(
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_admin_user),
):
    ensure_audio_config_seed(db)
    return (
        db.query(AudioPromptTemplate)
        .order_by(AudioPromptTemplate.id.asc())
        .all()
    )


@router.put("/config/prompts/{prompt_id}", response_model=PromptTemplateOut)
def update_prompt(
    prompt_id: int,
    body: PromptTemplateUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_admin_user),
):
    row = db.query(AudioPromptTemplate).filter(AudioPromptTemplate.id == prompt_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Prompt introuvable")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.get("/config/criteria", response_model=List[CriterionOut])
def list_criteria(
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_admin_user),
):
    ensure_audio_config_seed(db)
    return (
        db.query(AudioCriterion)
        .order_by(AudioCriterion.sort_order.asc(), AudioCriterion.id.asc())
        .all()
    )


@router.post("/config/criteria", response_model=CriterionOut, status_code=status.HTTP_201_CREATED)
def create_criterion(
    body: CriterionCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_admin_user),
):
    key = body.key.strip()
    if not re_match_key(key):
        raise HTTPException(status_code=400, detail="Clé invalide (a-z, 0-9, _)")
    if db.query(AudioCriterion).filter(AudioCriterion.key == key).first():
        raise HTTPException(status_code=409, detail="Clé déjà existante")
    row = AudioCriterion(
        key=key,
        label=body.label.strip(),
        description=body.description or "",
        enabled=body.enabled,
        sort_order=body.sort_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/config/criteria/{criterion_id}", response_model=CriterionOut)
def update_criterion(
    criterion_id: int,
    body: CriterionUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_admin_user),
):
    row = db.query(AudioCriterion).filter(AudioCriterion.id == criterion_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Critère introuvable")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/config/criteria/{criterion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_criterion(
    criterion_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_admin_user),
):
    row = db.query(AudioCriterion).filter(AudioCriterion.id == criterion_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Critère introuvable")
    db.delete(row)
    db.commit()
    return None


@router.post("/config/load-orange-defaults")
def load_orange_defaults(
    overwrite: bool = Query(True),
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_admin_user),
):
    ensure_audio_config_seed(db)
    result = apply_orange_defaults(db, overwrite=overwrite)
    return {"ok": True, **result}


def re_match_key(key: str) -> bool:
    import re

    return bool(re.fullmatch(r"[a-z][a-z0-9_]{1,63}", key))


# ── Enregistrements ──────────────────────────────────────────────────────────


@router.get("/dashboard")
def dashboard(
    week: Optional[str] = Query(None, description="Lundi ISO YYYY-MM-DD ou 'all'"),
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_admin_user),
):
    """KPI Dispositif de Réactivation (contrat Tersea) — 100% tables Concentrix."""
    wk = None if not week or week == "all" else week
    return build_dashboard_payload(db, wk)


@router.get("/stats", response_model=StatsOut)
def stats(
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_admin_user),
):
    rows = db.query(AudioRecording.status).all()
    by_status: dict[str, int] = {}
    for (st,) in rows:
        by_status[st or "?"] = by_status.get(st or "?", 0) + 1

    codifs = (
        db.query(AudioAnalysis.codification)
        .filter(AudioAnalysis.codification.isnot(None))
        .all()
    )
    by_codif: dict[str, int] = {}
    for (c,) in codifs:
        by_codif[c or "?"] = by_codif.get(c or "?", 0) + 1

    return StatsOut(total=len(rows), by_status=by_status, by_codification=by_codif)


@router.get("", response_model=List[RecordingOut])
def list_recordings(
    status_filter: Optional[str] = Query(None, alias="status"),
    phone: Optional[str] = Query(None),
    codification: Optional[str] = Query(None),
    recorded_from: Optional[datetime] = Query(None),
    recorded_to: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_admin_user),
):
    q = db.query(AudioRecording).options(joinedload(AudioRecording.analysis))
    if status_filter:
        q = q.filter(AudioRecording.status == status_filter)
    if phone:
        q = q.filter(AudioRecording.phone.ilike(f"%{phone.strip()}%"))
    if recorded_from:
        q = q.filter(AudioRecording.recorded_at >= recorded_from)
    if recorded_to:
        q = q.filter(AudioRecording.recorded_at <= recorded_to)
    if codification:
        q = q.join(AudioAnalysis).filter(AudioAnalysis.codification == codification)
    rows = (
        q.order_by(AudioRecording.recorded_at.desc().nullslast(), AudioRecording.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows


@router.get("/{recording_id}", response_model=RecordingDetailOut)
def get_recording(
    recording_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_admin_user),
):
    row = (
        db.query(AudioRecording)
        .options(joinedload(AudioRecording.analysis))
        .filter(AudioRecording.id == recording_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Enregistrement introuvable")
    out = RecordingDetailOut.model_validate(row)
    if row.analysis:
        out.codif_raw = row.analysis.codif_raw
        out.tokens_json = row.analysis.tokens_json
        out.analysis = AnalysisOut.model_validate(row.analysis)
    return out


@router.post("/{recording_id}/reprocess", response_model=RecordingOut)
def reprocess(
    recording_id: int,
    background_tasks: BackgroundTasks,
    async_mode: bool = Query(True, alias="async"),
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_admin_user),
):
    row = db.query(AudioRecording).filter(AudioRecording.id == recording_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Enregistrement introuvable")
    if async_mode:
        row.status = "pending"
        row.error_message = None
        db.commit()
        background_tasks.add_task(_bg_process, recording_id, True)
        db.refresh(row)
        return row
    return pipeline.process_recording(db, recording_id, force=True)


@router.post("/sync")
def sync_twilio(
    body: SyncBody,
    background_tasks: BackgroundTasks,
    async_mode: bool = Query(True, alias="async"),
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_admin_user),
):
    if async_mode:
        def _run():
            s = SessionLocal()
            try:
                pipeline.sync_new_recordings(
                    s,
                    date_from=body.date_from,
                    date_to=body.date_to,
                    process=body.process,
                    limit=body.limit,
                )
            finally:
                s.close()

        background_tasks.add_task(_run)
        return {"ok": True, "queued": True}
    result = pipeline.sync_new_recordings(
        db,
        date_from=body.date_from,
        date_to=body.date_to,
        process=body.process,
        limit=body.limit,
    )
    return {"ok": True, "queued": False, **result}


@router.post("/ingest", response_model=RecordingOut)
def ingest_one(
    body: IngestBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_admin_user),
):
    row = pipeline.ingest_twilio_recording_sid(db, body.recording_sid.strip(), process=False)
    if body.process:
        background_tasks.add_task(_bg_process, row.id, False)
    return row

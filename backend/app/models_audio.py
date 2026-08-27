"""Modèles audio Concentrix — enregistrements Twilio + analyses + critères admin."""
from __future__ import annotations

import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class AudioRecordingStatus(str, enum.Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    ANALYZING = "analyzing"
    DONE = "done"
    ERROR = "error"
    SKIPPED = "skipped"
    NEEDS_PROMPTS = "needs_prompts"


class AudioPromptTemplate(Base):
    """Prompts LLM paramétrables (codif / critères). Vides par défaut."""

    __tablename__ = "audio_prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    label = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=False, default="")
    user_prompt = Column(Text, nullable=False, default="")
    enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AudioCriterion(Base):
    """Critères qualité évalués (ex. posture, offre, champs) — paramétrables admin."""

    __tablename__ = "audio_criteria"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    label = Column(String(255), nullable=False)
    description = Column(Text, nullable=False, default="")
    enabled = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AudioRecording(Base):
    __tablename__ = "audio_recordings"
    __table_args__ = (UniqueConstraint("recording_sid", name="uq_audio_recording_sid"),)

    id = Column(Integer, primary_key=True, index=True)
    recording_sid = Column(String(64), nullable=False, index=True)
    call_sid = Column(String(64), nullable=True, index=True)
    phone = Column(String(32), nullable=True, index=True)
    direction = Column(String(32), nullable=True)
    from_number = Column(String(32), nullable=True)
    to_number = Column(String(32), nullable=True)
    duration_sec = Column(Float, nullable=True)
    channels = Column(Integer, nullable=True)
    recorded_at = Column(DateTime(timezone=True), nullable=True, index=True)
    media_url = Column(Text, nullable=True)
    local_path = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default=AudioRecordingStatus.PENDING.value, index=True)
    error_message = Column(Text, nullable=True)
    source = Column(String(32), nullable=False, default="twilio")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    analysis = relationship(
        "AudioAnalysis",
        back_populates="recording",
        uselist=False,
        cascade="all, delete-orphan",
    )


class AudioAnalysis(Base):
    __tablename__ = "audio_analyses"

    id = Column(Integer, primary_key=True, index=True)
    recording_id = Column(
        Integer,
        ForeignKey("audio_recordings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    codification = Column(String(64), nullable=True, index=True)
    vente_conclue = Column(Boolean, nullable=True)
    score_qualite = Column(Integer, nullable=True)
    deroule = Column(Text, nullable=True)
    posture = Column(String(32), nullable=True)
    offre_proposee = Column(Boolean, nullable=True)
    champs_lead_redemandes = Column(Boolean, nullable=True)
    ton_conseiller = Column(String(32), nullable=True)
    ecoute_active = Column(String(32), nullable=True)
    closing = Column(String(32), nullable=True)
    points_forts = Column(JSONB, nullable=True)
    axes_amelioration = Column(JSONB, nullable=True)
    criteres_result = Column(JSONB, nullable=True)
    codif_raw = Column(JSONB, nullable=True)
    tokens_json = Column(JSONB, nullable=True)
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    recording = relationship("AudioRecording", back_populates="analysis")


class ReactivationLead(Base):
    """Lead réactivé reçu via webhook JSON (POST /api/webhooks-reactivation)."""

    __tablename__ = "reactivation_leads"

    id = Column(Integer, primary_key=True, index=True)
    dedupe_key = Column(String(128), nullable=True, index=True)
    source = Column(String(64), nullable=False, default="default", index=True)
    payload = Column(JSONB, nullable=False)
    headers = Column(JSONB, nullable=True)
    lead_external_id = Column(BigInteger, nullable=True, index=True)
    phone = Column(String(32), nullable=True, index=True)
    campaign_external_id = Column(BigInteger, nullable=True, index=True)
    supplier_external_id = Column(BigInteger, nullable=True, index=True)
    status_id = Column(Integer, nullable=True, index=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ReactivationWebhookCall(Base):
    """Historique de chaque POST /api/webhooks-reactivation (OK ou échec)."""

    __tablename__ = "reactivation_webhook_calls"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(64), nullable=False, default="default", index=True)
    ok = Column(Boolean, nullable=False, default=False, index=True)
    http_status = Column(Integer, nullable=False, default=201, index=True)
    error = Column(Text, nullable=True)
    client_ip = Column(String(64), nullable=True, index=True)
    lead_external_id = Column(BigInteger, nullable=True, index=True)
    campaign_external_id = Column(BigInteger, nullable=True, index=True)
    stored = Column(Integer, nullable=False, default=0)
    created = Column(Integer, nullable=False, default=0)
    updated = Column(Integer, nullable=False, default=0)
    payload_preview = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class QualificationLead(Base):
    """Événement JSON brut reçu via POST /api/webhooks-qualification (tout JSON)."""

    __tablename__ = "qualification_leads"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(64), nullable=False, default="default", index=True)
    payload = Column(JSONB, nullable=False)
    headers = Column(JSONB, nullable=True)
    lead_external_id = Column(BigInteger, nullable=True, index=True)
    phone = Column(String(32), nullable=True, index=True)
    campaign_external_id = Column(BigInteger, nullable=True, index=True)
    supplier_external_id = Column(BigInteger, nullable=True, index=True)
    status_id = Column(Integer, nullable=True, index=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

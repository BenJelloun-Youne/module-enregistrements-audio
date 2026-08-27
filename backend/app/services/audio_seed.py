"""Seed idempotent des templates / critères audio (vides)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models_audio import AudioCriterion, AudioPromptTemplate
from app.services.audio_criteria_defaults import ORANGE_CRITERIA, ORANGE_PROMPT_TEMPLATES


def ensure_audio_config_seed(db: Session) -> dict:
    """Crée les lignes manquantes avec prompts/descriptions VIDES."""
    created_prompts = 0
    created_criteria = 0

    for tpl in ORANGE_PROMPT_TEMPLATES:
        existing = db.query(AudioPromptTemplate).filter(AudioPromptTemplate.key == tpl["key"]).first()
        if existing:
            continue
        db.add(
            AudioPromptTemplate(
                key=tpl["key"],
                label=tpl["label"],
                description=tpl.get("description") or "",
                system_prompt="",  # vide volontairement
                user_prompt="",
                enabled=True,
            )
        )
        created_prompts += 1

    for crit in ORANGE_CRITERIA:
        existing = db.query(AudioCriterion).filter(AudioCriterion.key == crit["key"]).first()
        if existing:
            continue
        db.add(
            AudioCriterion(
                key=crit["key"],
                label=crit["label"],
                description="",  # vide volontairement
                enabled=True,
                sort_order=crit.get("sort_order", 0),
            )
        )
        created_criteria += 1

    if created_prompts or created_criteria:
        db.commit()

    return {"prompts_created": created_prompts, "criteria_created": created_criteria}


def apply_orange_defaults(db: Session, *, overwrite: bool = True) -> dict:
    """Remplit prompts + descriptions avec le modèle Orange."""
    updated_prompts = 0
    updated_criteria = 0

    for tpl in ORANGE_PROMPT_TEMPLATES:
        row = db.query(AudioPromptTemplate).filter(AudioPromptTemplate.key == tpl["key"]).first()
        if not row:
            row = AudioPromptTemplate(key=tpl["key"], label=tpl["label"])
            db.add(row)
        elif not overwrite and (row.system_prompt or row.user_prompt):
            continue
        row.label = tpl["label"]
        row.description = tpl.get("description") or ""
        row.system_prompt = tpl["system_prompt"]
        row.user_prompt = tpl["user_prompt"]
        row.enabled = True
        updated_prompts += 1

    for crit in ORANGE_CRITERIA:
        row = db.query(AudioCriterion).filter(AudioCriterion.key == crit["key"]).first()
        if not row:
            row = AudioCriterion(key=crit["key"], label=crit["label"])
            db.add(row)
        elif not overwrite and row.description:
            continue
        row.label = crit["label"]
        row.description = crit["description"]
        row.sort_order = crit.get("sort_order", 0)
        row.enabled = True
        updated_criteria += 1

    db.commit()
    return {"prompts_updated": updated_prompts, "criteria_updated": updated_criteria}

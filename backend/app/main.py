"""FastAPI — module Enregistrements / Relances / Critères audio (standalone)."""
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_env = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_env)

from app.database import Base, SessionLocal, engine  # noqa: E402
from app import models  # noqa: F401, E402
from app import models_audio  # noqa: F401, E402
from app.routers import admin_enregistrements  # noqa: E402
from app.routers import auth  # noqa: E402
from app.routers import webhooks_reactivation  # noqa: E402
from app.routers import webhooks_twilio  # noqa: E402
from app.services.audio_seed import ensure_audio_config_seed  # noqa: E402

Base.metadata.create_all(bind=engine)

try:
    _seed_db = SessionLocal()
    try:
        ensure_audio_config_seed(_seed_db)
    finally:
        _seed_db.close()
except Exception:
    pass

app = FastAPI(
    title="Enregistrements & Relances — Audio",
    description="Module Smart Convers : Twilio → OpenAI → Postgres + critères admin",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin_enregistrements.router)
app.include_router(webhooks_twilio.router)
app.include_router(webhooks_reactivation.router)

_default_static = Path(__file__).resolve().parents[2] / "frontend"
_static_env = os.getenv("FRONTEND_STATIC_DIR", "").strip()
_candidate = Path(_static_env).expanduser().resolve() if _static_env else _default_static
_FRONTEND_STATIC: Path | None = _candidate if _candidate.is_dir() else None


@app.get("/health")
def health():
    return {"status": "ok", "module": "enregistrements-audio"}


@app.get("/api")
def api_root():
    return {
        "module": "enregistrements-audio",
        "version": "1.0.0",
        "pages": [
            "/pages/enregistrements-relances.html",
            "/pages/criteres-analyse-audio.html",
        ],
        "webhooks": [
            "/api/webhooks/twilio/recording",
            "/api/webhooks-reactivation",
        ],
    }


if _FRONTEND_STATIC is not None:

    @app.get("/")
    def root():
        index = _FRONTEND_STATIC / "index.html"
        if index.is_file():
            return FileResponse(index)
        return {"message": "API Enregistrements audio"}

    app.mount("/", StaticFiles(directory=str(_FRONTEND_STATIC), html=True), name="frontend")
else:

    @app.get("/")
    def root_api():
        return {"message": "API Enregistrements audio", "hint": "FRONTEND_STATIC_DIR manquant"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

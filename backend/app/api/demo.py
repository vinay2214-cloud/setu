from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.config import get_settings
from app.core.clock import now
from app.core.security import current_clinician
from app.db import engine
from app.schemas.api import DemoSeedRequest
from app.seed_loader import reset_demo, seed_demo

router = APIRouter(prefix="/demo", tags=["demo"], dependencies=[Depends(current_clinician)])


def _enabled() -> None:
    if not get_settings().demo_mode:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "Demo mode is disabled."}
        )


@router.post("/seed")
def seed(payload: DemoSeedRequest) -> dict:
    _enabled()
    if payload.scenario != "default":
        raise HTTPException(
            status_code=422, detail={"code": "validation_error", "message": "Unknown scenario."}
        )
    return seed_demo()


@router.post("/reset", status_code=204)
def reset() -> None:
    _enabled()
    reset_demo()


@router.get("/state")
def state() -> dict:
    _enabled()
    with engine.connect() as connection:
        offset = connection.execute(
            text("SELECT offset_seconds FROM demo_clock WHERE id=1")
        ).scalar_one()
    settings = get_settings()
    return {
        "now": now().isoformat().replace("+00:00", "Z"),
        "day_offset": offset // 86400,
        "llm_provider": settings.llm_provider,
        "speech_provider": settings.speech_provider,
        "channel": settings.channel_adapter,
    }

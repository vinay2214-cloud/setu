from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config import get_settings
from app.core.audit import record
from app.core.clock import now
from app.core.security import current_clinician
from app.db import engine
from app.schemas.api import DemoSeedRequest, TimeTravelRequest
from app.seed_loader import reset_demo, seed_demo
from app.services.events import broker

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


@router.get("/sample-summary")
def sample_summary() -> dict:
    from app.seed_loader import SEED

    _enabled()
    return {"text": (SEED / "discharge_summary_ramesh.txt").read_text()}


@router.post("/time-travel")
def time_travel(payload: TimeTravelRequest, request: Request) -> dict:
    _enabled()
    from app.core.clock import advance
    from app.services.orchestrator import tick

    for _ in range(payload.days):
        advance(days=1)
        tick(request.app.state.rule_pack)
    if payload.hours:
        advance(hours=payload.hours)
        tick(request.app.state.rule_pack)
    broker.publish("demo.clock", {"now": now().isoformat()})
    return state()


class CheckInRequest(BaseModel):
    patient_id: str
    kind: Literal["morning", "evening"] = "morning"


class ScenarioRequest(BaseModel):
    patient_id: str = "P001"
    step: int = Field(ge=1, le=5)


class ProviderRequest(BaseModel):
    llm: Literal["mock", "gemini"]


@router.post("/check-in")
def check_in(payload: CheckInRequest) -> dict:
    _enabled()
    from app.services.orchestrator import send_check_in

    messages = send_check_in(payload.patient_id, payload.kind)
    if not messages:
        raise HTTPException(
            409, detail="An active plan and consent are required, or check-in was already sent."
        )
    return {"messages": messages}


@router.post("/providers")
def providers(payload: ProviderRequest) -> dict:
    _enabled()
    settings = get_settings()
    if payload.llm == "gemini" and not (settings.gemini_api_key and settings.gemini_model):
        raise HTTPException(409, detail="Configure GEMINI_API_KEY and GEMINI_MODEL first.")
    settings.llm_provider = payload.llm
    with engine.begin() as connection:
        record(
            connection,
            actor="system",
            action="provider_switched",
            entity="demo",
            entity_id="default",
            detail={"llm": payload.llm},
        )
    return state()


@router.post("/scenario-step")
def scenario_step(payload: ScenarioRequest, request: Request) -> dict:
    _enabled()
    import json

    from app.seed_loader import SEED
    from app.services.pipeline import handle_inbound_message

    steps = json.loads((SEED / "scenario_ramesh.json").read_text())["live_steps"]
    step = next(item for item in steps if item["step"] == payload.step)
    if payload.patient_id != "P001":
        raise HTTPException(422, detail="The scripted scenario uses synthetic patient P001.")
    if payload.step == 1:
        return check_in(CheckInRequest(patient_id="P001"))
    if payload.step == 4:
        from app.api.alerts import approve_call
        from app.schemas.api import ApproveCallRequest

        with engine.connect() as connection:
            alert_id = connection.execute(
                text(
                    "SELECT id FROM alerts WHERE patient_id='P001' AND rule_id='R-COMBO-01' AND status='open' ORDER BY created_at DESC LIMIT 1"
                )
            ).scalar()
        if not alert_id:
            raise HTTPException(409, detail="Run swelling step first.")
        return approve_call(alert_id, ApproveCallRequest(), {"id": "C001"})
    return handle_inbound_message(
        "P001",
        text_value=step["text"],
        language="te",
        client_msg_id=f"scenario-{payload.step}",
        quick_reply=step.get("quick_reply"),
        rule_pack=request.app.state.rule_pack,
    )

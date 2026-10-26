import asyncio
import json
import secrets

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.clock import now
from app.db import engine
from app.schemas.api import SimMessageRequest, SimSessionRequest
from app.services.pipeline import _message_payload, get_stored_result, handle_inbound_message
from app.services.reply_composer import render_template

router = APIRouter(prefix="/sim", tags=["sim"])
_sessions: dict[str, str] = {}


def _session_patient(token: str | None, patient_id: str) -> None:
    if not token or _sessions.get(token) != patient_id:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Valid simulator session required."},
        )


@router.post("/session")
def create_session(payload: SimSessionRequest) -> dict:
    with engine.begin() as connection:
        patient = (
            connection.execute(
                text("SELECT id,name,language FROM patients WHERE id=:id"),
                {"id": payload.patient_id},
            )
            .mappings()
            .first()
        )
        if not patient:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": "Patient not found."}
            )
        consent = connection.execute(
            text("SELECT 1 FROM consents WHERE patient_id=:id AND granted=1 LIMIT 1"),
            {"id": payload.patient_id},
        ).first()
        if not consent:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "consent_missing",
                    "message": "Consent is required for simulator access.",
                },
            )
        messages = connection.execute(
            text(
                "SELECT id FROM messages WHERE patient_id=:id AND direction='out' AND template_key='disclaimer_intro'"
            ),
            {"id": payload.patient_id},
        ).first()
        if not messages:
            mid = f"M-{secrets.token_hex(4)}"
            lang = patient["language"]
            connection.execute(
                text("""INSERT INTO messages(id,patient_id,direction,channel,language,text,text_en,template_key,created_at)
                          VALUES (:id,:patient,'out','simulator',:language,:text,:english,'disclaimer_intro',:at)"""),
                {
                    "id": mid,
                    "patient": payload.patient_id,
                    "language": lang,
                    "text": render_template("disclaimer_intro", lang),
                    "english": render_template("disclaimer_intro", "en"),
                    "at": now().isoformat().replace("+00:00", "Z"),
                },
            )
    token = secrets.token_urlsafe(24)
    _sessions[token] = payload.patient_id
    with engine.connect() as connection:
        rows = (
            connection.execute(
                text(
                    "SELECT * FROM messages WHERE patient_id=:p ORDER BY created_at DESC,id DESC LIMIT 100"
                ),
                {"p": payload.patient_id},
            )
            .mappings()
            .all()
        )
    history = [_message_payload(dict(row)) for row in reversed(rows)]
    history.sort(key=lambda message: message["template_key"] != "disclaimer_intro")
    return {"token": token, "patient": dict(patient), "messages": history}


@router.post("/messages")
def send_message(
    payload: SimMessageRequest,
    request: Request,
    x_sim_token: str | None = Header(default=None, alias="X-Sim-Token"),
) -> dict:
    _session_patient(x_sim_token, payload.patient_id)
    try:
        return handle_inbound_message(
            payload.patient_id,
            text_value=payload.text,
            language=payload.language,
            client_msg_id=payload.client_msg_id,
            quick_reply=payload.quick_reply,
            rule_pack=request.app.state.rule_pack,
        )
    except IntegrityError:
        replay = get_stored_result(payload.patient_id, payload.client_msg_id)
        if replay is not None:
            return replay
        raise
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "Patient not found."}
        ) from exc


@router.get("/messages")
def poll_messages(
    patient_id: str,
    after: str | None = None,
    limit: int = 50,
    x_sim_token: str | None = Header(default=None, alias="X-Sim-Token"),
) -> dict:
    _session_patient(x_sim_token, patient_id)
    page_size = min(max(limit, 1), 100)
    with engine.connect() as connection:
        patient = connection.execute(
            text("SELECT 1 FROM patients WHERE id=:id"), {"id": patient_id}
        ).first()
        if not patient:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": "Patient not found."}
            )
        after_row = (
            connection.execute(
                text("SELECT created_at,id FROM messages WHERE id=:id AND patient_id=:patient"),
                {"id": after, "patient": patient_id},
            )
            .mappings()
            .first()
            if after
            else None
        )
        rows = (
            connection.execute(
                text(
                    "SELECT * FROM messages WHERE patient_id=:patient AND direction='out' "
                    "AND (:after_time IS NULL OR created_at>:after_time OR "
                    "(created_at=:after_time AND id>:after_id)) "
                    "ORDER BY created_at,id LIMIT :limit"
                ),
                {
                    "patient": patient_id,
                    "after_time": after_row["created_at"] if after_row else None,
                    "after_id": after_row["id"] if after_row else None,
                    "limit": page_size + 1,
                },
            )
            .mappings()
            .all()
        )
        has_more = len(rows) > page_size
        items = [_message_payload(dict(row)) for row in rows[:page_size]]
        return {"items": items, "next_after": items[-1]["id"] if has_more and items else None}


@router.get("/stream")
async def stream_messages(
    patient_id: str,
    x_sim_token: str | None = Header(default=None, alias="X-Sim-Token"),
):
    from app.services.events import broker

    _session_patient(x_sim_token, patient_id)
    subscription = broker.subscribe()

    async def events():
        try:
            while True:
                try:
                    event, payload = await asyncio.wait_for(subscription[1].get(), timeout=15)
                    message = payload.get("message", {})
                    if event == "message.created" and message.get("patient_id") == patient_id:
                        yield f"event: message.created\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                except TimeoutError:
                    yield "event: ping\ndata: {}\n\n"
        finally:
            broker.unsubscribe(subscription)

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )

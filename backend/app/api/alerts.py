import asyncio
import base64
import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from app.core.audit import record
from app.core.clock import IST, now
from app.core.security import current_clinician
from app.db import engine
from app.schemas.api import ApproveCallRequest, NoteRequest, SnoozeRequest
from app.services.events import broker

router = APIRouter(prefix="/alerts", tags=["alerts"], dependencies=[Depends(current_clinician)])


def _cursor_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        offset = int(base64.b64decode(cursor.encode(), altchars=b"-_", validate=True).decode())
        if offset < 0:
            raise ValueError
        return offset
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(
            status_code=422,
            detail={"code": "validation_error", "message": "Invalid pagination cursor."},
        ) from None


def _alert(connection, row) -> dict:
    patient = (
        connection.execute(
            text("SELECT id,name,age,sex,language,discharge_date FROM patients WHERE id=:id"),
            {"id": row["patient_id"]},
        )
        .mappings()
        .one()
    )
    events = (
        connection.execute(
            text("SELECT actor,action,note,at FROM alert_events WHERE alert_id=:id ORDER BY at"),
            {"id": row["id"]},
        )
        .mappings()
        .all()
    )
    return {
        "id": row["id"],
        "patient": {
            **dict(patient),
            "day_since_discharge": max(
                (now().astimezone(IST).date() - date.fromisoformat(patient["discharge_date"])).days,
                1,
            ),
        },
        "severity": row["severity"],
        "status": row["status"],
        "title": row["title"],
        "summary": row["summary"],
        "rule": {
            "id": row["rule_id"],
            "version": row["rule_version"],
            "title": row["title"],
            "clinician_review": "required",
        },
        "facts_used": json.loads(row["facts_json"] or "{}"),
        "contributing_rules": json.loads(row["contributing_json"] or "[]"),
        "related_alert_id": row["related_alert_id"],
        "evidence": json.loads(row["evidence_json"] or "[]"),
        "suggested_action": row["suggested_action"],
        "due_by": row["due_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "acknowledged_by": row["acknowledged_by"],
        "resolved_at": row["resolved_at"],
        "snoozed_until": row["snoozed_until"],
        "events": [dict(event) for event in events],
    }


@router.get("")
def list_alerts(
    status: str = "open,acknowledged",
    severity: str | None = None,
    patient_id: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> dict:
    statuses = [value.strip() for value in status.split(",") if value.strip()]
    clauses = ["status IN (" + ",".join(f":s{i}" for i in range(len(statuses))) + ")"]
    params = {f"s{i}": value for i, value in enumerate(statuses)}
    if severity:
        clauses.append("severity=:severity")
        params["severity"] = severity.upper()
    if patient_id:
        clauses.append("patient_id=:patient_id")
        params["patient_id"] = patient_id
    with engine.connect() as connection:
        rows = (
            connection.execute(text("SELECT * FROM alerts WHERE " + " AND ".join(clauses)), params)
            .mappings()
            .all()
        )
        order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        values = [_alert(connection, row) for row in rows]
        values.sort(key=lambda item: (-order[item["severity"]], item["due_by"]))
        offset = _cursor_offset(cursor)
        page = values[offset : offset + min(max(limit, 1), 100)]
        next_offset = offset + len(page)
        next_cursor = (
            base64.urlsafe_b64encode(str(next_offset).encode()).decode()
            if next_offset < len(values)
            else None
        )
        return {"items": page, "next_cursor": next_cursor}


@router.get("/metrics")
def metrics() -> dict:
    with engine.connect() as connection:
        rows = (
            connection.execute(text("SELECT severity,status,due_by FROM alerts")).mappings().all()
        )
    active = [row for row in rows if row["status"] in {"open", "acknowledged"}]
    by_severity = {
        key: sum(row["severity"] == key for row in active)
        for key in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    }
    overdue = sum(row["due_by"] < now().isoformat().replace("+00:00", "Z") for row in active)
    return {
        "open": len(active),
        "by_severity": by_severity,
        "median_minutes_to_ack_7d": None,
        "overdue": overdue,
    }


@router.get("/stream")
async def stream_alerts():
    subscription = broker.subscribe()

    async def events():
        yield "event: ping\ndata: {}\n\n"
        try:
            while True:
                try:
                    event, payload = await asyncio.wait_for(subscription[1].get(), timeout=15)
                    yield f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                except TimeoutError:
                    yield "event: ping\ndata: {}\n\n"
        finally:
            broker.unsubscribe(subscription)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get("/{alert_id}")
def get_alert(alert_id: str) -> dict:
    with engine.connect() as connection:
        row = (
            connection.execute(text("SELECT * FROM alerts WHERE id=:id"), {"id": alert_id})
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": "Alert not found."}
            )
        return _alert(connection, row)


def _transition(
    alert_id: str,
    actor: dict,
    action: str,
    *,
    note: str = "",
    status: str | None = None,
    snooze_until: str | None = None,
    assignee: str | None = None,
) -> dict:
    timestamp = now().isoformat().replace("+00:00", "Z")
    with engine.begin() as connection:
        row = (
            connection.execute(text("SELECT * FROM alerts WHERE id=:id"), {"id": alert_id})
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": "Alert not found."}
            )
        if action == "snoozed" and row["severity"] == "CRITICAL":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "validation_error",
                    "message": "Critical alerts cannot be snoozed.",
                },
            )
        if status:
            connection.execute(
                text("""UPDATE alerts SET status=:status,updated_at=:at,
                acknowledged_by=CASE WHEN :status='acknowledged' THEN :actor ELSE acknowledged_by END,
                acknowledged_at=CASE WHEN :status='acknowledged' THEN :at ELSE acknowledged_at END,
                resolved_at=CASE WHEN :status='resolved' THEN :at ELSE resolved_at END,
                resolution_note=CASE WHEN :status='resolved' THEN :note ELSE resolution_note END,
                snoozed_until=:snooze,assignee=COALESCE(:assignee,assignee) WHERE id=:id"""),
                {
                    "id": alert_id,
                    "status": status,
                    "at": timestamp,
                    "actor": actor["id"],
                    "note": note,
                    "snooze": snooze_until,
                    "assignee": assignee,
                },
            )
        else:
            connection.execute(
                text("UPDATE alerts SET assignee=:assignee,updated_at=:at WHERE id=:id"),
                {"id": alert_id, "assignee": assignee, "at": timestamp},
            )
        connection.execute(
            text(
                "INSERT INTO alert_events(alert_id,actor,action,note,at) VALUES (:id,:actor,:action,:note,:at)"
            ),
            {"id": alert_id, "actor": actor["id"], "action": action, "note": note, "at": timestamp},
        )
        record(
            connection,
            actor=actor["id"],
            action=action,
            entity="alert",
            entity_id=alert_id,
            detail={"status": status, "note": note},
        )
        updated = (
            connection.execute(text("SELECT * FROM alerts WHERE id=:id"), {"id": alert_id})
            .mappings()
            .one()
        )
        payload = _alert(connection, updated)
    broker.publish("alert.updated", {"alert": payload})
    return payload


@router.post("/{alert_id}/acknowledge")
def acknowledge(
    alert_id: str, payload: NoteRequest, actor: dict = Depends(current_clinician)
) -> dict:
    return _transition(alert_id, actor, "acknowledged", note=payload.note, status="acknowledged")


@router.post("/{alert_id}/snooze")
def snooze(alert_id: str, payload: SnoozeRequest, actor: dict = Depends(current_clinician)) -> dict:
    until = (now() + timedelta(minutes=payload.minutes)).isoformat().replace("+00:00", "Z")
    return _transition(
        alert_id, actor, "snoozed", note=payload.note, status="snoozed", snooze_until=until
    )


@router.post("/{alert_id}/resolve")
def resolve(alert_id: str, payload: NoteRequest, actor: dict = Depends(current_clinician)) -> dict:
    if not payload.note.strip():
        raise HTTPException(
            status_code=422,
            detail={"code": "validation_error", "message": "A resolution note is required."},
        )
    return _transition(alert_id, actor, "resolved", note=payload.note, status="resolved")


@router.post("/{alert_id}/approve-call")
def approve_call(
    alert_id: str, payload: ApproveCallRequest, actor: dict = Depends(current_clinician)
) -> dict:
    return _transition(
        alert_id,
        actor,
        "call_approved",
        note=payload.note,
        status="acknowledged",
        assignee=payload.assignee,
    )

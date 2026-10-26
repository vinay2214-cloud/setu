import base64
import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.config import get_settings
from app.core.audit import record
from app.core.clock import IST, now
from app.core.security import current_clinician
from app.db import engine
from app.schemas.api import PatientCreate

router = APIRouter(prefix="/patients", tags=["patients"], dependencies=[Depends(current_clinician)])


def _patient_payload(connection, patient) -> dict:
    plan = (
        connection.execute(
            text(
                "SELECT id,status,version FROM care_plans WHERE patient_id=:id ORDER BY version DESC LIMIT 1"
            ),
            {"id": patient["id"]},
        )
        .mappings()
        .first()
    )
    alerts = (
        connection.execute(
            text(
                "SELECT severity,COUNT(*) AS total FROM alerts WHERE patient_id=:id AND status IN ('open','acknowledged') GROUP BY severity"
            ),
            {"id": patient["id"]},
        )
        .mappings()
        .all()
    )
    sev_order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    highest = max((row["severity"] for row in alerts), key=lambda sev: sev_order[sev], default=None)
    latest = connection.execute(
        text("SELECT MAX(created_at) FROM messages WHERE patient_id=:id AND direction='in'"),
        {"id": patient["id"]},
    ).scalar()
    oldest_open_alert = connection.execute(
        text(
            "SELECT MIN(created_at) FROM alerts WHERE patient_id=:id AND status IN ('open','acknowledged')"
        ),
        {"id": patient["id"]},
    ).scalar()
    adherence_rows = (
        connection.execute(
            text("""SELECT status FROM medication_events WHERE patient_id=:id
                  AND event_date >= :from_date"""),
            {
                "id": patient["id"],
                "from_date": (now().astimezone(IST).date() - timedelta(days=6)).isoformat(),
            },
        )
        .mappings()
        .all()
    )
    known = [row["status"] for row in adherence_rows if row["status"] in {"taken", "missed"}]
    adherence = sum(status == "taken" for status in known) / len(known) if known else None
    discharge = date.fromisoformat(patient["discharge_date"])
    day = max((now().astimezone(IST).date() - discharge).days + 1, 1)
    return {
        "id": patient["id"],
        "name": patient["name"],
        "age": patient["age"],
        "sex": patient["sex"],
        "language": patient["language"],
        "location": patient["location"],
        "conditions": json.loads(patient["conditions"]),
        "discharge_date": patient["discharge_date"],
        "day_since_discharge": day,
        "status": patient["status"],
        "plan": dict(plan) if plan else None,
        "risk": {
            "open_alerts": sum(row["total"] for row in alerts),
            "highest_severity": highest,
            "adherence_7d": adherence,
            "last_response_at": latest,
        },
        "_oldest_open_alert": oldest_open_alert or "9999-12-31T23:59:59Z",
    }


def _cursor_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        offset = int(base64.b64decode(cursor.encode(), altchars=b"-_", validate=True).decode())
        if offset < 0 or offset > 10_000:
            raise ValueError
        return offset
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(
            status_code=422,
            detail={"code": "validation_error", "message": "Invalid pagination cursor."},
        ) from None


def _page(items: list, limit: int, cursor: str | None) -> dict:
    offset = _cursor_offset(cursor)
    page_size = min(max(limit, 1), 100)
    page = items[offset : offset + page_size]
    next_offset = offset + len(page)
    next_cursor = (
        base64.urlsafe_b64encode(str(next_offset).encode()).decode()
        if next_offset < len(items)
        else None
    )
    return {"items": page, "next_cursor": next_cursor}


def _query_page(connection, query: str, params: dict, limit: int, cursor: str | None) -> dict:
    offset = _cursor_offset(cursor)
    page_size = min(max(limit, 1), 100)
    rows = (
        connection.execute(
            text(f"{query} LIMIT :page_limit OFFSET :page_offset"),
            {**params, "page_limit": page_size + 1, "page_offset": offset},
        )
        .mappings()
        .all()
    )
    has_more = len(rows) > page_size
    items = [dict(row) for row in rows[:page_size]]
    next_offset = offset + len(items)
    next_cursor = base64.urlsafe_b64encode(str(next_offset).encode()).decode() if has_more else None
    return {"items": items, "next_cursor": next_cursor}


def _api_message(row) -> dict:
    item = dict(row)
    return {
        key: item.get(key)
        for key in (
            "id",
            "patient_id",
            "direction",
            "channel",
            "language",
            "text",
            "text_en",
            "template_key",
            "created_at",
        )
    } | {
        "intent": json.loads(item["intent_json"] or "{}") if item.get("intent_json") else None,
        "quick_replies": [],
    }


@router.get("")
def list_patients(
    status: str | None = None, q: str | None = None, limit: int = 50, cursor: str | None = None
) -> dict:
    query = "SELECT * FROM patients WHERE 1=1"
    params: dict = {}
    if status:
        query += " AND status=:status"
        params["status"] = status
    if q:
        query += " AND (name LIKE :q OR id LIKE :q)"
        params["q"] = f"%{q}%"
    with engine.connect() as connection:
        patients = [
            _patient_payload(connection, row)
            for row in connection.execute(text(query), params).mappings()
        ]
    order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4, None: 0}
    patients.sort(
        key=lambda item: (
            -order[item["risk"]["highest_severity"]],
            item["_oldest_open_alert"],
        )
    )
    for patient in patients:
        patient.pop("_oldest_open_alert")
    offset = _cursor_offset(cursor)
    page = patients[offset : offset + min(max(limit, 1), 100)]
    next_offset = offset + len(page)
    next_cursor = (
        base64.urlsafe_b64encode(str(next_offset).encode()).decode()
        if next_offset < len(patients)
        else None
    )
    return {"items": page, "next_cursor": next_cursor}


@router.post("", status_code=201)
def create_patient(payload: PatientCreate, clinician: dict = Depends(current_clinician)) -> dict:
    if not payload.consent.get("granted"):
        raise HTTPException(
            status_code=409, detail={"code": "consent_missing", "message": "Consent is required."}
        )
    from secrets import token_hex

    from app.core.audit import record

    patient_id = f"P{token_hex(3).upper()}"
    timestamp = now().isoformat().replace("+00:00", "Z")
    with engine.begin() as connection:
        connection.execute(
            text("""INSERT INTO patients(id,name,age,sex,language,phone,location,conditions,
            discharge_date,status,created_at) VALUES (:id,:name,:age,:sex,:language,:phone,:location,:conditions,
            :discharge,'pending',:at)"""),
            {
                "id": patient_id,
                "name": payload.name,
                "age": payload.age,
                "sex": payload.sex,
                "language": payload.language,
                "phone": payload.phone,
                "location": payload.location,
                "conditions": json.dumps(payload.conditions),
                "discharge": payload.discharge_date,
                "at": timestamp,
            },
        )
        consent = payload.consent
        connection.execute(
            text("""INSERT INTO consents(patient_id,type,channel,text_version,granted,granted_at)
            VALUES (:id,:type,:channel,:version,1,:at)"""),
            {
                "id": patient_id,
                "type": consent.get("type", "care_messaging"),
                "channel": consent.get("channel", "simulator"),
                "version": consent.get("text_version", "v1"),
                "at": timestamp,
            },
        )
        record(
            connection,
            actor=clinician["id"],
            action="patient_created",
            entity="patient",
            entity_id=patient_id,
        )
        patient = (
            connection.execute(text("SELECT * FROM patients WHERE id=:id"), {"id": patient_id})
            .mappings()
            .one()
        )
        return _patient_payload(connection, patient)


@router.get("/{patient_id}")
def get_patient(patient_id: str) -> dict:
    with engine.connect() as connection:
        patient = (
            connection.execute(text("SELECT * FROM patients WHERE id=:id"), {"id": patient_id})
            .mappings()
            .first()
        )
        if not patient:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": "Patient not found."}
            )
        return _patient_payload(connection, patient)


@router.get("/{patient_id}/messages")
def patient_messages(patient_id: str, limit: int = 50, cursor: str | None = None) -> dict:
    with engine.connect() as connection:
        page = _query_page(
            connection,
            "SELECT * FROM messages WHERE patient_id=:id ORDER BY created_at,id",
            {"id": patient_id},
            limit,
            cursor,
        )
        page["items"] = [_api_message(row) for row in page["items"]]
    return page


@router.get("/{patient_id}/timeline")
def patient_timeline(patient_id: str, limit: int = 50, cursor: str | None = None) -> dict:
    offset = _cursor_offset(cursor)
    page_size = min(max(limit, 1), 100)
    with engine.connect() as connection:
        items = []
        for table, kind, at_column in (
            ("medication_events", "medication", "recorded_at"),
            ("observations", "observation", "recorded_at"),
            ("symptoms_reported", "symptom", "recorded_at"),
            ("check_ins", "check_in", "scheduled_for"),
            ("alerts", "alert", "created_at"),
        ):
            rows = (
                connection.execute(
                    text(
                        f"SELECT * FROM {table} WHERE patient_id=:id ORDER BY {at_column} DESC LIMIT :n OFFSET :offset"
                    ),
                    {"id": patient_id, "n": offset + page_size + 1, "offset": 0},
                )
                .mappings()
                .all()
            )
            items.extend({"type": kind, "at": row[at_column], "data": dict(row)} for row in rows)
    items.sort(key=lambda item: item["at"], reverse=True)
    page = items[offset : offset + page_size]
    next_cursor = (
        base64.urlsafe_b64encode(str(offset + len(page)).encode()).decode()
        if len(items) > offset + page_size
        else None
    )
    return {"items": page, "next_cursor": next_cursor}


@router.get("/{patient_id}/adherence")
def patient_adherence(
    patient_id: str, days: int = 14, limit: int = 50, cursor: str | None = None
) -> dict:
    start = (now().astimezone(IST).date() - timedelta(days=max(1, min(days, 90)) - 1)).isoformat()
    with engine.connect() as connection:
        page = _query_page(
            connection,
            "SELECT event_date,med_id,slot,status FROM medication_events WHERE patient_id=:id AND event_date>=:start ORDER BY event_date,med_id,slot",
            {"id": patient_id, "start": start},
            limit,
            cursor,
        )
    return page


@router.get("/{patient_id}/vitals")
def patient_vitals(
    patient_id: str,
    type: str = "glucose",
    days: int = 14,
    limit: int = 50,
    cursor: str | None = None,
) -> dict:
    start = (now().astimezone(IST).date() - timedelta(days=max(1, min(days, 90)) - 1)).isoformat()
    since = f"{start}T00:00:00Z"
    with engine.connect() as connection:
        page = _query_page(
            connection,
            "SELECT * FROM observations WHERE patient_id=:id AND type=:type AND recorded_at>=:since ORDER BY recorded_at",
            {"id": patient_id, "type": type, "since": since},
            limit,
            cursor,
        )
    return page


@router.delete("/{patient_id}", status_code=204)
def delete_patient(patient_id: str, clinician: dict = Depends(current_clinician)) -> None:
    if not get_settings().demo_mode:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Patient deletion is demo-only."},
        )
    child_tables = [
        "alert_events",
        "alerts",
        "rule_evaluations",
        "symptoms_reported",
        "observations",
        "medication_events",
        "check_ins",
        "messages",
        "care_plans",
        "documents",
        "consents",
    ]
    with engine.begin() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM patients WHERE id=:id"), {"id": patient_id}
        ).first()
        if not exists:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": "Patient not found."}
            )
        record(
            connection,
            actor=clinician["id"],
            action="patient_deleted",
            entity="patient",
            entity_id=patient_id,
        )
        for table in child_tables:
            connection.execute(
                text(f"DELETE FROM {table} WHERE patient_id=:id"), {"id": patient_id}
            )
        connection.execute(text("DELETE FROM patients WHERE id=:id"), {"id": patient_id})

import json
from collections import defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.clock import IST


def _iso(value: Any) -> str:
    return value.isoformat().replace("+00:00", "Z") if hasattr(value, "isoformat") else str(value)


def missed_streak(statuses_by_date: dict[str, set[str]]) -> int:
    """Count missed days from the newest scheduled day; taken resets, unknown is neutral."""
    streak = 0
    for day in sorted(statuses_by_date, reverse=True):
        statuses = statuses_by_date[day]
        if "taken" in statuses:
            break
        if "missed" in statuses:
            streak += 1
    return streak


def build_facts(
    connection: Connection,
    patient_id: str,
    now,
    trigger_message_id: str | None = None,
) -> dict[str, Any]:
    patient = (
        connection.execute(
            text("SELECT conditions, discharge_date FROM patients WHERE id = :id"),
            {"id": patient_id},
        )
        .mappings()
        .first()
    )
    if patient is None:
        raise KeyError(patient_id)

    conditions = set(json.loads(patient["conditions"] or "[]"))
    local_today = now.astimezone(IST).date()
    discharge = __import__("datetime").date.fromisoformat(patient["discharge_date"])
    days_since_discharge = max((local_today - discharge).days, 0)

    plan_row = (
        connection.execute(
            text(
                "SELECT plan_json FROM care_plans WHERE patient_id = :id AND status = 'active' ORDER BY version DESC LIMIT 1"
            ),
            {"id": patient_id},
        )
        .mappings()
        .first()
    )
    plan = json.loads(plan_row["plan_json"]) if plan_row else {}
    critical_meds = {
        med.get("id") for med in plan.get("medications", []) if med.get("criticality") == "critical"
    }

    streak_by_med: dict[str, int] = {}
    if critical_meds:
        med_rows = connection.execute(
            text("""SELECT med_id, event_date, status FROM medication_events
                      WHERE patient_id = :id ORDER BY event_date DESC, recorded_at DESC"""),
            {"id": patient_id},
        ).mappings()
        daily: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for row in med_rows:
            if row["med_id"] in critical_meds:
                daily[row["med_id"]][row["event_date"]].add(row["status"])
        for med_id in critical_meds:
            streak_by_med[med_id] = missed_streak(daily[med_id])

    last_day = _iso(now - timedelta(hours=24))
    symptom_rows = connection.execute(
        text("""SELECT code, severity_hint, negated FROM symptoms_reported
                  WHERE patient_id = :id AND recorded_at >= :since"""),
        {"id": patient_id, "since": last_day},
    ).mappings()
    symptom_rows = list(symptom_rows)
    symptoms = {row["code"] for row in symptom_rows if not row["negated"]}
    critical_codes = {
        "chest_pain",
        "breathlessness",
        "fainting",
        "confusion",
        "one_sided_weakness",
        "slurred_speech",
    }
    symptom_severity_unknown_critical = any(
        row["code"] in critical_codes
        and not row["negated"]
        and row["severity_hint"] in (None, "unknown")
        for row in symptom_rows
    )

    glucose = (
        connection.execute(
            text("""SELECT value_num, context FROM observations WHERE patient_id = :id AND type = 'glucose'
                  AND recorded_at >= :since ORDER BY recorded_at DESC LIMIT 1"""),
            {"id": patient_id, "since": _iso(now - timedelta(hours=12))},
        )
        .mappings()
        .first()
    )
    bp = (
        connection.execute(
            text("""SELECT value_num, value_num2 FROM observations WHERE patient_id = :id AND type = 'bp'
                  AND recorded_at >= :since ORDER BY recorded_at DESC LIMIT 1"""),
            {"id": patient_id, "since": last_day},
        )
        .mappings()
        .first()
    )
    missed = connection.execute(
        text("""SELECT status FROM check_ins WHERE patient_id = :id
                  ORDER BY scheduled_for DESC LIMIT 20"""),
        {"id": patient_id},
    ).mappings()
    consecutive_no_response = 0
    for checkin in missed:
        if checkin["status"] == "missed":
            consecutive_no_response += 1
        else:
            break

    latest_message = None
    if trigger_message_id:
        latest_message = (
            connection.execute(
                text("SELECT intent_json FROM messages WHERE id = :id"), {"id": trigger_message_id}
            )
            .mappings()
            .first()
        )
    intent_json = latest_message["intent_json"] if latest_message else None
    intent = json.loads(intent_json or "{}") if intent_json else {}

    return {
        "conditions": conditions,
        "days_since_discharge": days_since_discharge,
        "max_missed_streak_critical": max(streak_by_med.values(), default=0),
        "symptoms": symptoms,
        "symptom_severity_unknown_critical": symptom_severity_unknown_critical,
        "glucose_latest": float(glucose["value_num"]) if glucose else None,
        "glucose_context": glucose["context"] if glucose else None,
        "bp_sys_latest": int(bp["value_num"]) if bp else None,
        "bp_dia_latest": int(bp["value_num2"]) if bp and bp["value_num2"] is not None else None,
        "consecutive_no_response": consecutive_no_response,
        # Missing extraction is uncertain: route it to human review instead of
        # treating absence of evidence as a confident, safe result.
        "intent_confidence_min": float(intent.get("confidence", 0.0)),
        "needs_human": bool(intent.get("needs_human", True)),
        "medical_question": (intent.get("question") or {}).get("category") == "medical",
    }

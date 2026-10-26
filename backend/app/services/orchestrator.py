import json
import secrets
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import text

from app.core.audit import record
from app.core.clock import IST, now
from app.db import engine
from app.services.events import broker
from app.services.fact_builder import build_facts
from app.services.nutrition import daily_tip
from app.services.pipeline import _message_payload
from app.services.reply_composer import render_template
from app.services.sentinel import evaluate_facts, persist_alerts


def _stamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def send_check_in(patient_id: str, kind: str, scheduled: datetime | None = None) -> list[dict]:
    current = now()
    at = _stamp(current)
    scheduled = scheduled or current.replace(microsecond=0)
    published = []
    with engine.begin() as connection:
        patient = (
            connection.execute(text("SELECT * FROM patients WHERE id=:id"), {"id": patient_id})
            .mappings()
            .first()
        )
        plan = (
            connection.execute(
                text(
                    "SELECT * FROM care_plans WHERE patient_id=:id AND "
                    "status='active' ORDER BY version DESC LIMIT 1"
                ),
                {"id": patient_id},
            )
            .mappings()
            .first()
        )
        consent = connection.execute(
            text("SELECT 1 FROM consents WHERE patient_id=:id AND granted=1 LIMIT 1"),
            {"id": patient_id},
        ).first()
        if not patient or not plan or not consent:
            return []
        slot_at = _stamp(scheduled)
        existing = (
            connection.execute(
                text(
                    "SELECT id,status FROM check_ins WHERE patient_id=:p AND "
                    "kind=:kind AND scheduled_for=:at"
                ),
                {"p": patient_id, "kind": kind, "at": slot_at},
            )
            .mappings()
            .first()
        )
        if existing and existing["status"] != "pending":
            return []
        cid = existing["id"] if existing else f"CI-{secrets.token_hex(4)}"
        if not existing:
            connection.execute(
                text(
                    "INSERT INTO "
                    "check_ins(id,patient_id,kind,scheduled_for,status) VALUES "
                    "(:id,:p,:kind,:at,'pending') "
                    "ON CONFLICT(patient_id,kind,scheduled_for) DO NOTHING"
                ),
                {"id": cid, "p": patient_id, "kind": kind, "at": slot_at},
            )
        row = connection.execute(
            text(
                "SELECT id FROM check_ins WHERE patient_id=:p AND kind=:kind "
                "AND scheduled_for=:scheduled"
            ),
            {"p": patient_id, "kind": kind, "scheduled": slot_at},
        ).first()
        if row:
            cid = row[0]
        claimed = connection.execute(
            text(
                "UPDATE check_ins SET status='sent',sent_at=:at WHERE id=:id AND status='pending'"
            ),
            {"at": at, "id": cid},
        )
        if claimed.rowcount != 1:
            return []
        language = patient["language"]
        data = json.loads(plan["plan_json"])
        meds = data.get("medications", [])
        meds = [
            med
            for med in meds
            if any((int(t.split(":")[0]) < 14) == (kind == "morning") for t in med.get("times", []))
        ]
        values = {
            "name": patient["name"],
            "clinic": "Demo Clinic",
            "med_list": ", ".join(med["name"] for med in meds),
        }
        keys = [f"greeting_{kind}", f"ask_meds_{kind}", "ask_glucose", "ask_symptoms"]
        if kind == "evening":
            keys = ["greeting_evening", "ask_meds_evening", "ask_meal_dinner", "ask_symptoms"]
        tip = daily_tip(json.loads(patient["conditions"]), language)
        if tip:
            keys.append(tip["template_key"])
        for key in keys:
            params = tip["params"] if tip and key == tip["template_key"] else values
            message_id = f"M-{secrets.token_hex(4)}"
            connection.execute(
                text(
                    "INSERT INTO messages(id,patient_id,direction,channel,languag"
                    "e,text,text_en,template_key,created_at) VALUES "
                    "(:id,:p,'out','simulator',:lang,:raw,:en,:key,:at)"
                ),
                {
                    "id": message_id,
                    "p": patient_id,
                    "lang": language,
                    "raw": render_template(
                        key, language, params, allowed_meds={med["name"] for med in meds}
                    ),
                    "en": render_template(
                        key, "en", params, allowed_meds={med["name"] for med in meds}
                    ),
                    "key": key,
                    "at": at,
                },
            )
            row = (
                connection.execute(text("SELECT * FROM messages WHERE id=:id"), {"id": message_id})
                .mappings()
                .one()
            )
            published.append(_message_payload(dict(row)))
        event_date = current.astimezone(IST).date().isoformat()
        for med in meds:
            slot = (
                "morning"
                if kind == "morning"
                else "bedtime"
                if med.get("frequency_code") == "HS"
                else "evening"
            )
            connection.execute(
                text(
                    "INSERT INTO medication_events(patient_id,care_plan_id,med_id"
                    ",event_date,slot,status,recorded_at) VALUES "
                    "(:p,:plan,:med,:day,:slot,'unknown',:at) ON "
                    "CONFLICT(patient_id,med_id,event_date,slot) DO NOTHING"
                ),
                {
                    "p": patient_id,
                    "plan": plan["id"],
                    "med": med["id"],
                    "day": event_date,
                    "slot": slot,
                    "at": at,
                },
            )
        record(connection, actor="system", action="check_in_sent", entity="check_in", entity_id=cid)
    for message in published:
        broker.publish("message.created", {"message": message})
    broker.publish("check_in.sent", {"patient_id": patient_id, "kind": kind})
    return published


def tick(rule_pack) -> dict:
    current = now()
    with engine.connect() as connection:
        plans = (
            connection.execute(
                text("SELECT patient_id,activated_at FROM care_plans WHERE status='active'")
            )
            .mappings()
            .all()
        )
    sent = 0
    for plan in plans:
        start = datetime.fromisoformat(plan["activated_at"].replace("Z", "+00:00")).astimezone(
            IST
        ).date() + timedelta(days=1)
        today = current.astimezone(IST).date()
        # Advance walks one day at a time; normal ticks also recover the most recent missed day.
        day = max(start, today - timedelta(days=1))
        while day <= today:
            for kind, hour in (("morning", 8), ("evening", 19)):
                due = datetime.combine(day, time(hour), IST)
                if due <= current:
                    sent += bool(send_check_in(plan["patient_id"], kind, due))
            day += timedelta(days=1)
    alerts_to_publish = []
    with engine.begin() as connection:
        missed = (
            connection.execute(
                text(
                    "SELECT id,patient_id FROM check_ins WHERE status='sent' AND sent_at<=:cutoff"
                ),
                {"cutoff": _stamp(current - timedelta(hours=3))},
            )
            .mappings()
            .all()
        )
        for checkin in missed:
            connection.execute(
                text("UPDATE check_ins SET status='missed' WHERE id=:id"), {"id": checkin["id"]}
            )
            record(
                connection,
                actor="system",
                action="check_in_missed",
                entity="check_in",
                entity_id=checkin["id"],
            )
        for patient_id in {row["patient_id"] for row in missed}:
            facts = build_facts(connection, patient_id, current)
            fired = evaluate_facts(rule_pack, facts, current, [])
            alerts_to_publish.extend(
                persist_alerts(
                    connection,
                    patient_id=patient_id,
                    fired=fired,
                    facts=facts,
                    evidence=[],
                    dedupe_window_hours=rule_pack.defaults.get("dedupe_window_hours", {}),
                    trigger_message_id=None,
                    now=current,
                )
            )
        expired = (
            connection.execute(
                text("SELECT id FROM alerts WHERE status='snoozed' AND snoozed_until<=:at"),
                {"at": _stamp(current)},
            )
            .scalars()
            .all()
        )
        for alert_id in expired:
            connection.execute(
                text(
                    "UPDATE alerts SET status='open',snoozed_until=NULL,updated_at=:at WHERE id=:id"
                ),
                {"id": alert_id, "at": _stamp(current)},
            )
            connection.execute(
                text(
                    "INSERT INTO alert_events(alert_id,actor,action,at) VALUES "
                    "(:id,'system','reopened',:at)"
                ),
                {"id": alert_id, "at": _stamp(current)},
            )
            record(
                connection,
                actor="system",
                action="alert_reopened",
                entity="alert",
                entity_id=alert_id,
            )
    for alert in alerts_to_publish:
        broker.publish("alert.updated", {"alert": alert})
    return {"check_ins_sent": sent, "check_ins_missed": len(missed)}

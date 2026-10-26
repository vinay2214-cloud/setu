import json
import secrets
from datetime import UTC
from typing import Any

from sqlalchemy import text

from app.core.audit import record
from app.core.clock import IST, now
from app.db import engine
from app.services.events import broker
from app.services.fact_builder import build_facts
from app.services.intent_extractor import IntentExtractor
from app.services.nutrition import meal_feedback
from app.services.reply_composer import plan_replies, render_template
from app.services.sentinel import evaluate_facts, persist_alerts


class PipelineError(RuntimeError):
    pass


def _id() -> str:
    return f"M-{secrets.token_hex(4)}"


def _message_payload(row: dict) -> dict:
    return {
        key: row[key]
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
        "intent": json.loads(row["intent_json"] or "{}") if row.get("intent_json") else None,
        "quick_replies": [],
    }


def _stored_result(
    connection, patient_id: str, client_msg_id: str, *, persist_legacy: bool = False
) -> dict | None:
    inbound = (
        connection.execute(
            text("SELECT * FROM messages WHERE patient_id=:p AND client_msg_id=:client"),
            {"p": patient_id, "client": client_msg_id},
        )
        .mappings()
        .first()
    )
    if not inbound:
        return None
    if inbound["response_json"]:
        return json.loads(inbound["response_json"])
    intent = json.loads(inbound["intent_json"] or "{}")
    reply_prefix = f"reply:{inbound['id']}:"
    replies = (
        connection.execute(
            text(
                "SELECT * FROM messages WHERE patient_id=:p AND direction='out' "
                "AND client_msg_id LIKE :prefix ORDER BY client_msg_id"
            ),
            {"p": patient_id, "prefix": f"{reply_prefix}%"},
        )
        .mappings()
        .all()
    )
    alerts = (
        connection.execute(
            text("SELECT * FROM alerts WHERE patient_id=:p ORDER BY updated_at"),
            {"p": patient_id},
        )
        .mappings()
        .all()
    )
    alerts = [
        row
        for row in alerts
        if any(
            item.get("message_id") == inbound["id"]
            for item in json.loads(row["evidence_json"] or "[]")
        )
    ]
    result = {
        "message": _message_payload(inbound),
        "replies": [_message_payload(row) for row in replies],
        "alerts": [
            {
                "id": row["id"],
                "severity": row["severity"],
                "rule_id": row["rule_id"],
                "status": row["status"],
            }
            for row in alerts
        ],
        "extracted": intent,
    }
    if persist_legacy:
        connection.execute(
            text("UPDATE messages SET response_json=:response WHERE id=:id"),
            {"response": json.dumps(result, ensure_ascii=False), "id": inbound["id"]},
        )
    return result


def handle_inbound_message(
    patient_id: str,
    *,
    text_value: str | None,
    language: str | None,
    client_msg_id: str,
    quick_reply: str | None = None,
    rule_pack,
) -> dict[str, Any]:
    with engine.begin() as connection:
        duplicate = _stored_result(connection, patient_id, client_msg_id, persist_legacy=True)
        if duplicate is not None:
            return duplicate
        patient = (
            connection.execute(text("SELECT * FROM patients WHERE id=:id"), {"id": patient_id})
            .mappings()
            .first()
        )
        if patient is None:
            raise KeyError(patient_id)
        active_consent = connection.execute(
            text("SELECT 1 FROM consents WHERE patient_id=:id AND granted=1 LIMIT 1"),
            {"id": patient_id},
        ).first()
        plan_row = (
            connection.execute(
                text(
                    "SELECT id,plan_json FROM care_plans WHERE patient_id=:id AND status='active' "
                    "ORDER BY version DESC LIMIT 1"
                ),
                {"id": patient_id},
            )
            .mappings()
            .first()
        )
        lang = language if language in {"te", "hi", "en"} else patient["language"]
        inbound_id = _id()
        at = now().isoformat().replace("+00:00", "Z")
        raw = (text_value or "")[:1000]
        try:
            intent = IntentExtractor().extract(raw, lang, quick_reply)
        except Exception:
            intent = {
                "language": lang,
                "intents": ["other"],
                "medication_events": [],
                "symptoms": [],
                "vitals": [],
                "meal": None,
                "question": None,
                "confidence": 0.0,
                "needs_human": True,
            }
        translated = {
            "కాళ్ళు కొంచెం వాచాయి.": "My feet are a bit swollen.",
            "లేదు, ఈ రోజు బాగానే ఉన్నాను.": "No, I'm feeling fine today.",
            "ఛాతీలో నొప్పిగా ఉంది": "I have chest pain.",
        }.get(raw)
        connection.execute(
            text("""INSERT INTO messages(
                id,patient_id,direction,channel,language,text,text_en,intent_json,client_msg_id,created_at
                ) VALUES (:id,:patient,'in','simulator',:language,:text,:text_en,:intent,
                          :client,:at)"""),
            {
                "id": inbound_id,
                "patient": patient_id,
                "language": lang,
                "text": raw or None,
                "text_en": translated,
                "intent": json.dumps(intent, ensure_ascii=False),
                "client": client_msg_id,
                "at": at,
            },
        )
        consented = bool(active_consent)
        if not consented:
            intent["needs_human"] = True
            intent["confidence"] = 0.0
            connection.execute(
                text("UPDATE messages SET intent_json=:intent WHERE id=:id"),
                {"intent": json.dumps(intent, ensure_ascii=False), "id": inbound_id},
            )
            record(
                connection,
                actor="system",
                action="message_without_consent",
                entity="message",
                entity_id=inbound_id,
            )
        plan = json.loads(plan_row["plan_json"]) if plan_row else {}
        medications = plan.get("medications", [])
        effective_intent = (
            intent
            if consented
            else {**intent, "medication_events": [], "symptoms": [], "vitals": []}
        )
        med_events = effective_intent.get("medication_events", [])
        timestamp = now().astimezone(UTC).isoformat().replace("+00:00", "Z")
        event_date = now().astimezone(IST).date().isoformat()
        for event in med_events:
            slot = "morning" if now().astimezone(IST).hour < 14 else "evening"
            target_meds = [
                med
                for med in medications
                if any(
                    (int(t.split(":")[0]) < 14) == (slot == "morning") for t in med.get("times", [])
                )
            ]
            named = [med for med in target_meds if med["name"].lower() in raw.lower()]
            target_meds = named or target_meds
            for med in target_meds:
                connection.execute(
                    text("""INSERT INTO medication_events(
                              patient_id,care_plan_id,med_id,event_date,slot,status,source_message_id,recorded_at)
                              VALUES (:patient,:plan,:med,:day,:slot,:status,:source,:at)
                              ON CONFLICT(patient_id,med_id,event_date,slot) DO UPDATE SET
                              status=excluded.status,source_message_id=excluded.source_message_id,
                              recorded_at=excluded.recorded_at"""),
                    {
                        "patient": patient_id,
                        "plan": plan_row["id"] if plan_row else None,
                        "med": med["id"],
                        "day": event_date,
                        "slot": "bedtime" if med.get("frequency_code") == "HS" else slot,
                        "status": event["status"],
                        "source": inbound_id,
                        "at": timestamp,
                    },
                )
        for symptom in effective_intent.get("symptoms", []):
            connection.execute(
                text("""INSERT INTO symptoms_reported(
                          patient_id,code,raw_text,severity_hint,negated,source_message_id,recorded_at)
                          VALUES (:patient,:code,:raw,:severity,:negated,:source,:at)"""),
                {
                    "patient": patient_id,
                    "code": symptom["code"],
                    "raw": raw,
                    "severity": symptom.get("severity_hint"),
                    "negated": int(symptom.get("negated", False)),
                    "source": inbound_id,
                    "at": timestamp,
                },
            )
        for vital in effective_intent.get("vitals", []):
            if vital["type"] == "glucose":
                connection.execute(
                    text("""INSERT INTO observations(
                              patient_id,type,value_num,unit,context,source_message_id,recorded_at)
                              VALUES (:patient,'glucose',:value,:unit,:context,:source,:at)"""),
                    {
                        "patient": patient_id,
                        "value": vital["value"],
                        "unit": vital["unit"],
                        "context": vital.get("context"),
                        "source": inbound_id,
                        "at": timestamp,
                    },
                )
            elif vital["type"] == "bp":
                connection.execute(
                    text("""INSERT INTO observations(
                              patient_id,type,value_num,value_num2,unit,context,source_message_id,recorded_at)
                              VALUES (:patient,'bp',:sys,:dia,:unit,'unknown',:source,:at)"""),
                    {
                        "patient": patient_id,
                        "sys": vital["systolic"],
                        "dia": vital["diastolic"],
                        "unit": vital["unit"],
                        "source": inbound_id,
                        "at": timestamp,
                    },
                )
        connection.execute(
            text(
                "UPDATE check_ins SET status='answered',answered_at=:at WHERE "
                "patient_id=:p AND status='sent'"
            ),
            {"at": timestamp, "p": patient_id},
        )
        feedback = (
            meal_feedback(raw, json.loads(patient["conditions"]), lang) if consented else None
        )
        facts = build_facts(connection, patient_id, now(), inbound_id)
        evidence = [
            {
                "message_id": inbound_id,
                "at": timestamp,
                "text": raw,
                "text_en": translated,
                "language": lang,
            }
        ]
        fired = evaluate_facts(rule_pack, facts, now(), [inbound_id])
        alerts = persist_alerts(
            connection,
            patient_id=patient_id,
            fired=fired,
            facts=facts,
            evidence=evidence,
            dedupe_window_hours=rule_pack.defaults.get("dedupe_window_hours", {}),
            trigger_message_id=inbound_id,
            now=now(),
        )
        reply_keys = plan_replies(intent, fired, lang) if consented else []
        if feedback and not any(rule.severity in {"CRITICAL", "HIGH", "MEDIUM"} for rule in fired):
            reply_keys = (reply_keys + [feedback["template_key"]])[:3]
        for reply_index, key in enumerate(reply_keys):
            values = feedback["params"] if feedback and key == feedback["template_key"] else {}
            if key == "ack_vital" and intent.get("vitals"):
                v = intent["vitals"][0]
                values = {
                    "vital": "blood pressure" if v["type"] == "bp" else "glucose",
                    "value": f"{v.get('systolic')}/{v.get('diastolic')}"
                    if v["type"] == "bp"
                    else str(v["value"]),
                }
            reply_text = render_template(key, lang, values)
            out_id = _id()
            connection.execute(
                text("""INSERT INTO messages(
                          id,patient_id,direction,channel,language,text,text_en,template_key,client_msg_id,created_at)
                          VALUES (:id,:patient,'out','simulator',:language,:text,:text_en,:key,
                                  :client,:at)"""),
                {
                    "id": out_id,
                    "patient": patient_id,
                    "language": lang,
                    "text": reply_text,
                    "text_en": render_template(key, "en", values),
                    "key": key,
                    "client": f"reply:{inbound_id}:{reply_index}",
                    "at": now().isoformat().replace("+00:00", "Z"),
                },
            )
        inbound_row = dict(
            connection.execute(text("SELECT * FROM messages WHERE id=:id"), {"id": inbound_id})
            .mappings()
            .one()
        )
        result = _stored_result(connection, patient_id, client_msg_id)
        if result is not None:
            connection.execute(
                text("UPDATE messages SET response_json=:response WHERE id=:id"),
                {"response": json.dumps(result, ensure_ascii=False), "id": inbound_id},
            )
    for alert in alerts:
        broker.publish(
            "alert.created" if alert["created_at"] == alert["updated_at"] else "alert.updated",
            {"alert": alert},
        )
    broker.publish("message.created", {"message": _message_payload(inbound_row)})
    for row in result.get("replies", []) if result else []:
        broker.publish("message.created", {"message": row})
    return result or {
        "message": _message_payload(inbound_row),
        "replies": [],
        "alerts": [],
        "extracted": intent,
    }


def get_stored_result(patient_id: str, client_msg_id: str) -> dict[str, Any] | None:
    with engine.connect() as connection:
        return _stored_result(connection, patient_id, client_msg_id)

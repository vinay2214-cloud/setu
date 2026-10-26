import json
import secrets
from datetime import UTC, datetime, time, timedelta
from hashlib import scrypt
from pathlib import Path

from sqlalchemy import text

from app.core.audit import record
from app.core.clock import IST, now, set_time
from app.db import engine, settings

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "seed"
DELETE_ORDER = [
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
    "patients",
    "rule_packs",
]


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1).hex()
    return f"scrypt${salt.hex()}${digest}"


def _id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4)}"


def reset_demo() -> None:
    if not settings.demo_mode:
        raise RuntimeError("Demo endpoints are disabled")
    if not settings.database_url.startswith("sqlite"):
        raise RuntimeError("Demo reset currently supports SQLite only")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        for table in DELETE_ORDER:
            connection.exec_driver_sql(f"DELETE FROM {table}")
        connection.exec_driver_sql("DELETE FROM sqlite_sequence")
        connection.exec_driver_sql("UPDATE demo_clock SET offset_seconds = 0 WHERE id = 1")
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        record(
            connection,
            actor="system",
            action="demo_reset",
            entity="demo",
            entity_id="default",
        )


def ensure_demo_accounts() -> None:
    """Keep synthetic login accounts available before the first demo seed."""
    if not settings.demo_mode:
        return
    fixtures = json.loads((SEED / "patients.json").read_text(encoding="utf-8"))
    timestamp = now().isoformat().replace("+00:00", "Z")
    with engine.begin() as connection:
        for clinician in fixtures["clinicians"]:
            connection.execute(
                text("""INSERT OR IGNORE INTO clinicians(id,name,email,role,clinic,password_hash,created_at)
                          VALUES (:id,:name,:email,:role,:clinic,:password_hash,:created_at)"""),
                {
                    **clinician,
                    "clinic": fixtures["_meta"]["clinic"],
                    "password_hash": _password_hash(clinician["password"]),
                    "created_at": timestamp,
                },
            )


def seed_demo() -> dict[str, int]:
    reset_demo()
    fixtures = json.loads((SEED / "patients.json").read_text(encoding="utf-8"))
    history = json.loads((SEED / "scenario_ramesh.json").read_text(encoding="utf-8"))
    plan = json.loads(
        (SEED / "discharge_summary_ramesh.expected_plan.json").read_text(encoding="utf-8")
    )
    raw_summary = (SEED / "discharge_summary_ramesh.txt").read_text(encoding="utf-8")
    pack_text = (SEED / "rules" / "diabetes_htn_v1.yaml").read_text(encoding="utf-8")
    scenario_start = datetime.fromisoformat(
        fixtures["_meta"]["scenario_start"].replace("Z", "+00:00")
    )
    set_time(scenario_start)
    timestamp = now().isoformat().replace("+00:00", "Z")

    with engine.begin() as connection:
        for clinician in fixtures["clinicians"]:
            connection.execute(
                text("""INSERT OR IGNORE INTO clinicians(id,name,email,role,clinic,password_hash,created_at)
                          VALUES (:id,:name,:email,:role,:clinic,:password_hash,:created_at)"""),
                {
                    **clinician,
                    "clinic": fixtures["_meta"]["clinic"],
                    "password_hash": _password_hash(clinician["password"]),
                    "created_at": timestamp,
                },
            )

        for patient in fixtures["patients"]:
            connection.execute(
                text("""INSERT INTO patients(id,name,age,sex,language,phone,location,conditions,
                          discharge_date,status,created_at) VALUES (:id,:name,:age,:sex,:language,:phone,
                          :location,:conditions,:discharge_date,'active',:created_at)"""),
                {
                    **patient,
                    "conditions": json.dumps(patient["conditions"]),
                    "created_at": timestamp,
                },
            )
            connection.execute(
                text("""INSERT INTO consents(patient_id,type,channel,text_version,granted,granted_at)
                          VALUES (:id,'care_messaging','simulator','v1',1,:at)"""),
                {"id": patient["id"], "at": timestamp},
            )

        connection.execute(
            text("""INSERT INTO rule_packs(id,name,version,status,yaml_text,loaded_at)
                      VALUES ('diabetes_htn','Diabetes + Hypertension post-discharge monitoring',
                              '1.0.0','DRAFT',:yaml,:at)"""),
            {"yaml": pack_text, "at": timestamp},
        )
        connection.execute(
            text("""INSERT INTO documents(id,patient_id,kind,raw_text,uploaded_at)
                      VALUES ('DOC-0001','P001','discharge_summary',:text,:at)"""),
            {"text": raw_summary, "at": timestamp},
        )
        connection.execute(
            text("""INSERT INTO care_plans(id,patient_id,version,status,plan_json,warnings_json,
                      source_document_id,created_by,approved_by,approved_at,activated_at,created_at)
                      VALUES ('CP-0001','P001',1,'active',:plan,'[]','DOC-0001','seed','C001',:at,:at,:at)"""),
            {"plan": json.dumps(plan, ensure_ascii=False), "at": timestamp},
        )
        _seed_history(connection, history["history"], plan)
        _seed_alert(
            connection,
            "P002",
            "R-ADH-01",
            "MEDIUM",
            "Critical medicines missed 2 days running",
            timestamp,
        )
        _seed_alert(
            connection,
            "P003",
            "R-QUESTION-01",
            "LOW",
            "Patient asked a medical question",
            timestamp,
        )
        _seed_alert(
            connection, "P005", "R-NORESP-01", "MEDIUM", "No reply to 2 check-ins", timestamp
        )
        record(
            connection,
            actor="system",
            action="seeded",
            entity="demo",
            entity_id="default",
            detail={"patients": 5},
        )
    return {"patients": len(fixtures["patients"]), "alerts": 3}


def _seed_history(connection, days: list[dict], plan: dict) -> None:
    discharge = datetime.fromisoformat("2026-10-18").date()
    medicines = plan["medications"]
    for day in days:
        event_date = (discharge + timedelta(days=day["day"] - 1)).isoformat()
        event_at = datetime.combine(discharge + timedelta(days=day["day"] - 1), time(8), IST)
        event_at_str = event_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
        message_id = _id("M")
        text_value = (
            "లేదు, ఈ రోజు బాగానే ఉన్నాను." if day["day"] == 7 else "Daily check-in response recorded."
        )
        connection.execute(
            text("""INSERT INTO messages(id,patient_id,direction,channel,language,text,text_en,created_at)
                      VALUES (:id,'P001','in','simulator','te',:text,:text_en,:at)"""),
            {
                "id": message_id,
                "text": text_value,
                "text_en": "Daily check-in response recorded.",
                "at": event_at_str,
            },
        )
        for med in medicines:
            med_result = day["meds"]
            status = (
                med_result
                if isinstance(med_result, str)
                else med_result.get(med["id"].removeprefix("med_"), "taken")
            )
            status = "taken" if status == "all_taken" else status
            connection.execute(
                text("""INSERT INTO medication_events(patient_id,care_plan_id,med_id,event_date,slot,
                          status,source_message_id,recorded_at) VALUES ('P001','CP-0001',:med,:date,
                          :slot,:status,:message,:at)"""),
                {
                    "med": med["id"],
                    "date": event_date,
                    "slot": "bedtime" if med["frequency_code"] == "HS" else "morning",
                    "status": status,
                    "message": message_id,
                    "at": event_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                },
            )
        if day.get("glucose") is not None:
            connection.execute(
                text("""INSERT INTO observations(patient_id,type,value_num,unit,context,recorded_at,source_message_id)
                          VALUES ('P001','glucose',:value,'mg/dL','fasting',:at,:message)"""),
                {"value": day["glucose"], "at": event_at_str, "message": message_id},
            )
        if day.get("bp"):
            connection.execute(
                text("""INSERT INTO observations(patient_id,type,value_num,value_num2,unit,context,recorded_at,source_message_id)
                          VALUES ('P001','bp',:sys,:dia,'mmHg','morning',:at,:message)"""),
                {
                    "sys": day["bp"][0],
                    "dia": day["bp"][1],
                    "at": event_at_str,
                    "message": message_id,
                },
            )
        scheduled = event_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
        connection.execute(
            text("""INSERT INTO check_ins(id,patient_id,kind,scheduled_for,status,sent_at,answered_at)
                      VALUES (:id,'P001','morning',:at,'answered',:at,:at)"""),
            {"id": _id("CI"), "at": scheduled},
        )
    if not days:
        return


def _seed_alert(
    connection, patient_id: str, rule_id: str, severity: str, title: str, created_at: str
) -> None:
    ids = {"R-ADH-01": "R-ADH-01", "R-QUESTION-01": "R-QUESTION-01", "R-NORESP-01": "R-NORESP-01"}
    version = "1.0.0"
    due = now() + timedelta(
        minutes={"LOW": 4320, "MEDIUM": 1440, "HIGH": 240, "CRITICAL": 15}[severity]
    )
    alert_id = f"A-{connection.execute(text('SELECT COUNT(*) FROM alerts')).scalar_one() + 1:04d}"
    facts = {
        "R-ADH-01": {"max_missed_streak_critical": 2},
        "R-QUESTION-01": {"medical_question": True},
        "R-NORESP-01": {"consecutive_no_response": 2},
    }[rule_id]
    # The alert fixtures have rule/fact provenance but no persisted source
    # messages, so do not fabricate patient evidence.
    source_message_id = None
    evidence = []
    connection.execute(
        text("""INSERT INTO alerts(id,patient_id,severity,status,rule_id,rule_version,title,summary,
                  facts_json,contributing_json,evidence_json,suggested_action,due_by,created_at,updated_at)
                  VALUES (:id,:patient,:severity,'open',:rule,:version,:title,:summary,:facts,'[]',:evidence,:action,:due,:at,:at)"""),
        {
            "id": alert_id,
            "patient": patient_id,
            "severity": severity,
            "rule": ids[rule_id],
            "version": version,
            "title": title,
            "summary": "Synthetic demo alert awaiting clinician review.",
            "facts": json.dumps(facts),
            "evidence": json.dumps(evidence, ensure_ascii=False),
            "action": "Review with the patient.",
            "due": due.isoformat().replace("+00:00", "Z"),
            "at": created_at,
        },
    )
    connection.execute(
        text(
            "INSERT INTO alert_events(alert_id,actor,action,at) VALUES (:id,'system','created',:at)"
        ),
        {"id": alert_id, "at": created_at},
    )
    record(
        connection,
        actor="system",
        action="alert_created",
        entity="alert",
        entity_id=alert_id,
        detail={
            "rule_id": rule_id,
            "rule_version": version,
            "facts": facts,
            "source_message_ids": [],
            "source_fixture": f"seed/patients.json#patients[{patient_id}]",
        },
    )
    connection.execute(
        text("""INSERT INTO rule_evaluations(patient_id,rule_pack_id,rule_id,rule_version,fired,
            facts_json,trigger_message_id,evaluated_at) VALUES (:patient,'diabetes_htn',:rule,:version,1,
            :facts,:message,:at)"""),
        {
            "patient": patient_id,
            "rule": rule_id,
            "version": version,
            "facts": json.dumps(facts),
            "message": source_message_id,
            "at": created_at,
        },
    )

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.audit import record
from app.core.clock import IST
from app.rules.engine import SEVERITY_ORDER, evaluate
from app.rules.loader import RulePack


@dataclass(frozen=True)
class FiredRule:
    rule_id: str
    rule_version: str
    title: str
    severity: str
    suggested_action: str
    facts_used: dict[str, Any]
    evidence_message_ids: list[str]
    due_by: datetime


def evaluate_facts(
    pack: RulePack, facts: dict[str, Any], now: datetime, evidence_ids: list[str]
) -> list[FiredRule]:
    version = str(pack.pack.get("version", "unknown"))
    defaults = pack.defaults.get("sla_minutes", {})
    fired: list[FiredRule] = []
    for rule in evaluate(pack, facts):
        used = {
            key: sorted(facts[key]) if isinstance(facts.get(key), set) else facts.get(key)
            for key in facts
            if _fact_used(rule.when, key)
        }
        fired.append(
            FiredRule(
                rule_id=rule.id,
                rule_version=version,
                title=rule.title,
                severity=rule.severity,
                suggested_action=rule.suggested_action,
                facts_used=used,
                evidence_message_ids=list(evidence_ids),
                due_by=now + timedelta(minutes=int(defaults.get(rule.severity, 4320))),
            )
        )
    return fired


def _fact_used(node: dict[str, Any], fact: str) -> bool:
    if "all" in node or "any" in node:
        return any(_fact_used(child, fact) for child in node.get("all", node.get("any", [])))
    if "not" in node:
        return _fact_used(node["not"], fact)
    return node.get("fact") == fact


def primary_and_contributors(fired: list[FiredRule]) -> tuple[FiredRule | None, list[FiredRule]]:
    if not fired:
        return None, []
    ordered = sorted(fired, key=lambda rule: -SEVERITY_ORDER[rule.severity])
    return ordered[0], ordered[1:]


def persist_alerts(
    connection: Connection,
    *,
    patient_id: str,
    fired: list[FiredRule],
    facts: dict[str, Any],
    evidence: list[dict[str, Any]],
    dedupe_window_hours: dict[str, int],
    trigger_message_id: str | None = None,
    now: datetime,
) -> list[dict[str, Any]]:
    primary, contributors = primary_and_contributors(fired)
    if primary is None:
        connection.execute(
            text("""INSERT INTO rule_evaluations(patient_id,rule_pack_id,rule_id,rule_version,
            fired,facts_json,trigger_message_id,evaluated_at) VALUES (:patient,'diabetes_htn',NULL,NULL,0,
            :facts,:message,:at)"""),
            {
                "patient": patient_id,
                "facts": json.dumps(facts, default=list),
                "message": trigger_message_id,
                "at": now.isoformat().replace("+00:00", "Z"),
            },
        )
        return []

    patient = (
        connection.execute(
            text("SELECT name,age,sex,discharge_date FROM patients WHERE id=:id"),
            {"id": patient_id},
        )
        .mappings()
        .one()
    )
    windows = {
        severity: max(int(dedupe_window_hours.get(severity, 0)), 0) for severity in SEVERITY_ORDER
    }
    window_start = (
        (now - timedelta(hours=windows[primary.severity])).isoformat().replace("+00:00", "Z")
    )
    existing = None
    if windows[primary.severity] > 0:
        existing = (
            connection.execute(
                text("""SELECT * FROM alerts WHERE patient_id=:patient
            AND rule_id=:rule AND status IN ('open','acknowledged') AND created_at>=:since
            ORDER BY created_at DESC LIMIT 1"""),
                {"patient": patient_id, "rule": primary.rule_id, "since": window_start},
            )
            .mappings()
            .first()
        )

    contributing = [
        {
            "id": rule.rule_id,
            "version": rule.rule_version,
            "title": rule.title,
            "severity": rule.severity,
        }
        for rule in contributors
    ]
    evidence_by_id = {item.get("message_id"): item for item in evidence if item.get("message_id")}
    if existing:
        evidence_by_id.update(
            {item.get("message_id"): item for item in json.loads(existing["evidence_json"] or "[]")}
        )
        old_contributors = json.loads(existing["contributing_json"] or "[]")
        by_rule = {item["id"]: item for item in old_contributors + contributing}
        contributing = list(by_rule.values())
        connection.execute(
            text("""UPDATE alerts SET facts_json=:facts, contributing_json=:contributors,
            evidence_json=:evidence, updated_at=:at WHERE id=:id"""),
            {
                "facts": json.dumps(primary.facts_used, default=list),
                "contributors": json.dumps(contributing),
                "evidence": json.dumps(list(evidence_by_id.values()), ensure_ascii=False),
                "at": now.isoformat().replace("+00:00", "Z"),
                "id": existing["id"],
            },
        )
        alert_id = existing["id"]
        action = "updated"
    else:
        older = (
            connection.execute(
                text("""SELECT * FROM alerts WHERE patient_id=:patient
            AND status IN ('open','acknowledged') ORDER BY created_at DESC"""),
                {"patient": patient_id},
            )
            .mappings()
            .all()
        )
        older = [
            row
            for row in older
            if SEVERITY_ORDER.get(row["severity"], -1) < SEVERITY_ORDER[primary.severity]
        ]
        merged_evidence = {
            item.get("message_id"): item for item in evidence if item.get("message_id")
        }
        for old in older:
            for item in json.loads(old["evidence_json"] or "[]"):
                if item.get("message_id"):
                    merged_evidence[item["message_id"]] = item
        evidence = sorted(merged_evidence.values(), key=lambda item: item.get("at", ""))
        alert_id = (
            f"A-{connection.execute(text('SELECT COUNT(*) FROM alerts')).scalar_one() + 1:04d}"
        )
        if older:
            old_rules = {rule.rule_id: rule for rule in fired}
            for old in older:
                old_primary = old_rules.get(old["rule_id"])
                if old_primary is None or any(
                    item["id"] == old_primary.rule_id for item in contributing
                ):
                    continue
                contributing.append(
                    {
                        "id": old_primary.rule_id,
                        "version": old_primary.rule_version,
                        "title": old_primary.title,
                        "severity": old_primary.severity,
                    }
                )
        local_day = max(
            (
                now.astimezone(IST).date()
                - datetime.fromisoformat(patient["discharge_date"]).date()
            ).days,
            1,
        )
        summary = (
            f"{patient['age']}{patient['sex']}, day {local_day} post-discharge. {primary.title}."
        )
        timestamp = now.isoformat().replace("+00:00", "Z")
        connection.execute(
            text("""INSERT INTO alerts(id,patient_id,severity,status,rule_id,rule_version,title,
            summary,facts_json,contributing_json,evidence_json,suggested_action,related_alert_id,due_by,created_at,updated_at)
            VALUES (:id,:patient,:severity,'open',:rule,:version,:title,:summary,:facts,:contributors,:evidence,
                    :action,:related,:due,:at,:at)"""),
            {
                "id": alert_id,
                "patient": patient_id,
                "severity": primary.severity,
                "rule": primary.rule_id,
                "version": primary.rule_version,
                "title": primary.title,
                "summary": summary,
                "facts": json.dumps(primary.facts_used, default=list),
                "contributors": json.dumps(contributing),
                "evidence": json.dumps(evidence, ensure_ascii=False),
                "action": primary.suggested_action,
                "related": older[0]["id"] if older else None,
                "due": primary.due_by.isoformat().replace("+00:00", "Z"),
                "at": timestamp,
            },
        )
        action = "created"
        for lower in older:
            connection.execute(
                text("""UPDATE alerts SET status='resolved',resolved_at=:at,updated_at=:at,
                resolution_note=:note WHERE id=:id"""),
                {"at": timestamp, "note": f"merged into {alert_id}", "id": lower["id"]},
            )
            connection.execute(
                text("""INSERT INTO alert_events(alert_id,actor,action,note,at)
                VALUES (:id,'system','merged',:note,:at)"""),
                {"id": lower["id"], "note": f"merged into {alert_id}", "at": timestamp},
            )
            record(
                connection,
                actor="system",
                action="alert_merged",
                entity="alert",
                entity_id=lower["id"],
                detail={"merged_into": alert_id, "rule_id": primary.rule_id},
            )

    timestamp = now.isoformat().replace("+00:00", "Z")
    connection.execute(
        text(
            "INSERT INTO alert_events(alert_id,actor,action,at) VALUES (:id,'system',:action,:at)"
        ),
        {"id": alert_id, "action": action, "at": timestamp},
    )
    record(
        connection,
        actor="system",
        action=f"alert_{action}",
        entity="alert",
        entity_id=alert_id,
        detail={
            "rule_id": primary.rule_id,
            "rule_version": primary.rule_version,
            "facts": primary.facts_used,
            "source_message_ids": [item.get("message_id") for item in evidence],
        },
    )

    for rule in fired:
        connection.execute(
            text("""INSERT INTO rule_evaluations(patient_id,rule_pack_id,rule_id,rule_version,
            fired,facts_json,trigger_message_id,evaluated_at) VALUES (:patient,'diabetes_htn',:rule,:version,1,
            :facts,:message,:at)"""),
            {
                "patient": patient_id,
                "rule": rule.rule_id,
                "version": rule.rule_version,
                "facts": json.dumps(rule.facts_used, default=list),
                "message": trigger_message_id,
                "at": timestamp,
            },
        )

    return [
        dict(
            connection.execute(text("SELECT * FROM alerts WHERE id=:id"), {"id": alert_id})
            .mappings()
            .one()
        )
    ]

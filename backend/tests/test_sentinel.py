import json
from datetime import timedelta
from pathlib import Path

from sqlalchemy import text

from app.core.clock import now
from app.db import engine
from app.rules.loader import load_pack
from app.services.sentinel import FiredRule, persist_alerts, primary_and_contributors

RULE_PACK = load_pack(Path(__file__).resolve().parents[2] / "seed/rules/diabetes_htn_v1.yaml")
DEDUPE_HOURS = RULE_PACK.defaults["dedupe_window_hours"]


def test_primary_rule_orders_by_severity_then_pack_order():
    rules = [
        FiredRule("R-Z", "1.0.0", "Z", "MEDIUM", "Review", {}, [], now()),
        FiredRule("R-A", "1.0.0", "A", "HIGH", "Call", {}, [], now()),
        FiredRule("R-B", "1.0.0", "B", "HIGH", "Call", {}, [], now()),
    ]
    primary, contributors = primary_and_contributors(rules)
    assert primary.rule_id == "R-A"
    assert [rule.rule_id for rule in contributors] == ["R-B", "R-Z"]


def test_sentinel_dedupes_then_upgrades_and_merges(seeded_client):
    moment = now()
    adherence = FiredRule(
        "R-ADH-01",
        "1.0.0",
        "Missed doses",
        "MEDIUM",
        "Review within 24 hours",
        {"max_missed_streak_critical": 2},
        [],
        moment + timedelta(hours=24),
    )
    combo = FiredRule(
        "R-COMBO-01",
        "1.0.0",
        "Swelling with repeated missed doses",
        "HIGH",
        "Call within 4 hours",
        {"symptoms": ["leg_swelling"], "max_missed_streak_critical": 2},
        [],
        moment + timedelta(hours=4),
    )
    with engine.begin() as connection:
        first = persist_alerts(
            connection,
            patient_id="P001",
            fired=[adherence],
            facts={},
            evidence=[],
            dedupe_window_hours=DEDUPE_HOURS,
            now=moment,
        )[0]
    with engine.begin() as connection:
        same = persist_alerts(
            connection,
            patient_id="P001",
            fired=[adherence],
            facts={},
            evidence=[{"message_id": "M-evidence-1", "text": "synthetic"}],
            dedupe_window_hours=DEDUPE_HOURS,
            now=moment + timedelta(minutes=1),
        )[0]
    assert same["id"] == first["id"]
    with engine.begin() as connection:
        upgraded = persist_alerts(
            connection,
            patient_id="P001",
            fired=[combo, adherence],
            facts={},
            evidence=[{"message_id": "M-evidence-2", "text": "synthetic"}],
            dedupe_window_hours=DEDUPE_HOURS,
            now=moment + timedelta(minutes=2),
        )[0]
        old = (
            connection.execute(
                text("SELECT status,resolution_note FROM alerts WHERE id=:id"), {"id": first["id"]}
            )
            .mappings()
            .one()
        )
    assert upgraded["severity"] == "HIGH"
    assert upgraded["rule_id"] == "R-COMBO-01"
    assert upgraded["related_alert_id"] == first["id"]
    contributors = json.loads(upgraded["contributing_json"])
    assert [rule["id"] for rule in contributors] == ["R-ADH-01"]
    assert old["status"] == "resolved"
    assert old["resolution_note"] == f"merged into {upgraded['id']}"

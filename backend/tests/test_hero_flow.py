import asyncio
import json

from sqlalchemy import text

from app.db import engine
from app.services.events import broker


async def test_complete_hero_flow_with_sse_audit_and_fixed_emergency(seeded_client, caplog):
    assert seeded_client.post("/api/v1/demo/reset").status_code == 204
    assert seeded_client.post("/api/v1/demo/seed", json={"scenario": "default"}).status_code == 200
    assert seeded_client.post("/api/v1/care-plans/CP-0001/activate").status_code == 409
    session = seeded_client.post("/api/v1/sim/session", json={"patient_id": "P001"}).json()
    headers = {"X-Sim-Token": session["token"]}

    async def send(key, raw, quick=None):
        response = await asyncio.to_thread(
            seeded_client.post,
            "/api/v1/sim/messages",
            headers=headers,
            json={
                "patient_id": "P001",
                "client_msg_id": key,
                "language": "te",
                "text": raw,
                "quick_reply": quick,
            },
        )
        assert response.status_code == 200
        return response.json()

    missed = await send("hero-missed", "లేదు, ఈ రోజు బాగానే ఉన్నాను.", "not_taken")
    assert any(alert["severity"] == "MEDIUM" for alert in missed["alerts"])
    subscription = broker.subscribe()
    try:
        high = await send("hero-swollen", "కాళ్ళు కొంచెం వాచాయి.")
        event, payload = await asyncio.wait_for(subscription[1].get(), 2)
        assert event in {"alert.created", "alert.updated"}
        assert payload["alert"]["severity"] == "HIGH"
    finally:
        broker.unsubscribe(subscription)
    high_alert = next(alert for alert in high["alerts"] if alert["severity"] == "HIGH")
    detail = seeded_client.get(f"/api/v1/alerts/{high_alert['id']}").json()
    assert detail["rule"]["id"] == "R-COMBO-01"
    assert detail["patient"]["day_since_discharge"] == 8
    assert [rule["id"] for rule in detail["contributing_rules"]] == ["R-ADH-01"]
    assert len(detail["evidence"]) == 2
    assert any(
        reply["template_key"] == "escalate_notified" and reply["language"] == "te"
        for reply in high["replies"]
    )
    open_alerts = seeded_client.get("/api/v1/alerts?patient_id=P001").json()["items"]
    assert len(open_alerts) == 1
    assert (await send("hero-missed", "లేదు, ఈ రోజు బాగానే ఉన్నాను.", "not_taken")) == missed
    approved = seeded_client.post(
        f"/api/v1/alerts/{high_alert['id']}/approve-call",
        json={"assignee": "dr.anitha", "note": "Synthetic call approved"},
    )
    assert approved.json()["status"] == "acknowledged"
    with engine.connect() as connection:
        audit = (
            connection.execute(
                text("SELECT action FROM audit_log WHERE entity_id=:id"), {"id": high_alert["id"]}
            )
            .scalars()
            .all()
        )
        rows = (
            connection.execute(
                text(
                    "SELECT evidence_json,status FROM alerts WHERE patient_id='P001' "
                    "AND severity='MEDIUM'"
                )
            )
            .mappings()
            .all()
        )
    assert "call_approved" in audit
    assert rows and all(row["status"] == "resolved" for row in rows)
    assert all(json.loads(row["evidence_json"]) for row in rows)
    emergency = await send("hero-emergency", "ఛాతీలో నొప్పిగా ఉంది")
    assert any(
        alert["rule_id"] == "R-CRIT-SYM-01" and alert["severity"] == "CRITICAL"
        for alert in emergency["alerts"]
    )
    assert emergency["replies"][0]["template_key"] == "emergency_advice"
    assert "108" in emergency["replies"][0]["text"]
    assert "కాళ్ళు కొంచెం వాచాయి" not in caplog.text
    assert "లేదు, ఈ రోజు బాగానే ఉన్నాను" not in caplog.text

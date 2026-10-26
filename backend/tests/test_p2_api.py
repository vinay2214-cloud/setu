from sqlalchemy import text

from app.db import engine


def test_hero_inbound_pipeline_is_idempotent_and_merges_evidence(seeded_client):
    session = seeded_client.post("/api/v1/sim/session", json={"patient_id": "P001"})
    assert session.status_code == 200
    assert session.json()["patient"]["language"] == "te"
    headers = {"X-Sim-Token": session.json()["token"]}

    first_payload = {
        "patient_id": "P001",
        "client_msg_id": "hero-step-2",
        "text": "లేదు, ఈ రోజు బాగానే ఉన్నాను.",
        "language": "te",
        "quick_reply": "not_taken",
    }
    first = seeded_client.post("/api/v1/sim/messages", json=first_payload, headers=headers)
    assert first.status_code == 200
    assert first.json()["message"]["channel"] == "simulator"
    assert "intent" in first.json()["message"]
    assert "intent_json" not in first.json()["message"]
    poll_response = seeded_client.get(
        "/api/v1/sim/messages?patient_id=P001&limit=1", headers=headers
    ).json()
    polled = poll_response["items"]
    assert polled
    assert {"channel", "intent", "quick_replies"} <= polled[0].keys()
    assert poll_response["next_after"]
    next_poll = seeded_client.get(
        f"/api/v1/sim/messages?patient_id=P001&limit=1&after={poll_response['next_after']}",
        headers=headers,
    ).json()
    assert next_poll["items"][0]["id"] != polled[0]["id"]
    assert any(alert["rule_id"] == "R-ADH-01" for alert in first.json()["alerts"])
    duplicate = seeded_client.post("/api/v1/sim/messages", json=first_payload, headers=headers)
    assert duplicate.status_code == 200
    assert duplicate.json()["message"]["id"] == first.json()["message"]["id"]

    second = seeded_client.post(
        "/api/v1/sim/messages",
        json={
            "patient_id": "P001",
            "client_msg_id": "hero-step-3",
            "text": "కాళ్ళు కొంచెం వాచాయి.",
            "language": "te",
        },
        headers=headers,
    )
    assert second.status_code == 200
    high = next(alert for alert in second.json()["alerts"] if alert["severity"] == "HIGH")
    assert high["rule_id"] == "R-COMBO-01"
    detail = seeded_client.get(f"/api/v1/alerts/{high['id']}").json()
    assert len(detail["evidence"]) == 2
    assert detail["contributing_rules"][0]["id"] == "R-ADH-01"
    assert any(reply["template_key"] == "escalate_notified" for reply in second.json()["replies"])
    replay_after_upgrade = seeded_client.post(
        "/api/v1/sim/messages", json=first_payload, headers=headers
    )
    assert replay_after_upgrade.json() == first.json()


def test_critical_phrase_uses_fixed_emergency_template(seeded_client):
    token = seeded_client.post("/api/v1/sim/session", json={"patient_id": "P001"}).json()["token"]
    unauthorized = seeded_client.post(
        "/api/v1/sim/messages",
        json={"patient_id": "P001", "client_msg_id": "missing-token", "text": "hello"},
    )
    assert unauthorized.status_code == 401
    response = seeded_client.post(
        "/api/v1/sim/messages",
        json={
            "patient_id": "P001",
            "client_msg_id": "critical-1",
            "text": "ఛాతీలో నొప్పిగా ఉంది",
            "language": "te",
        },
        headers={"X-Sim-Token": token},
    )
    assert response.status_code == 200
    assert response.json()["alerts"][0]["rule_id"] == "R-CRIT-SYM-01"
    assert response.json()["replies"][0]["template_key"] == "emergency_advice"
    assert "108" in response.json()["replies"][0]["text"]


def test_patient_history_endpoints_return_pagination_envelope(seeded_client):
    response = seeded_client.get(
        "/api/v1/patients/P001/messages?limit=2",
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
    assert response.json()["next_cursor"]
    timeline = seeded_client.get("/api/v1/patients/P001/timeline?limit=2")
    assert len(timeline.json()["items"]) == 2
    assert "next_cursor" in timeline.json()


def test_message_without_consent_is_retained_and_creates_human_review_alert(seeded_client):
    token = seeded_client.post("/api/v1/sim/session", json={"patient_id": "P004"}).json()["token"]
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM consents WHERE patient_id='P004'"))
    response = seeded_client.post(
        "/api/v1/sim/messages",
        json={
            "patient_id": "P004",
            "client_msg_id": "no-consent",
            "text": "hello",
            "language": "en",
        },
        headers={"X-Sim-Token": token},
    )
    assert response.status_code == 200
    assert response.json()["message"]["id"].startswith("M-")
    assert response.json()["replies"] == []
    assert any(alert["rule_id"] == "R-UNCLEAR-01" for alert in response.json()["alerts"])


def test_message_history_uses_public_message_shape(seeded_client):
    response = seeded_client.get("/api/v1/patients/P001/messages?limit=1")
    assert response.status_code == 200
    message = response.json()["items"][0]
    assert "channel" in message
    assert "intent" in message
    assert "quick_replies" in message
    assert "intent_json" not in message

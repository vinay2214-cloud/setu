from sqlalchemy import text

from app.db import engine
from app.services.nutrition import FOODS, daily_tip, permitted


def test_time_travel_schedules_and_marks_unanswered_checkins(seeded_client):
    result = seeded_client.post("/api/v1/demo/time-travel", json={"days": 1})
    assert result.status_code == 200
    assert seeded_client.get("/api/v1/auth/me").status_code == 200
    result = seeded_client.post("/api/v1/demo/time-travel", json={"hours": 4})
    assert result.status_code == 200
    with engine.connect() as connection:
        rows = (
            connection.execute(
                text(
                    "SELECT status FROM check_ins WHERE patient_id='P001' "
                    "AND scheduled_for>='2026-10-27'"
                )
            )
            .scalars()
            .all()
        )
    assert "missed" in rows


def test_scheduled_slots_can_be_answered_without_duplicate_events(seeded_client):
    assert (
        seeded_client.post(
            "/api/v1/demo/check-in", json={"patient_id": "P001", "kind": "morning"}
        ).status_code
        == 200
    )
    session = seeded_client.post("/api/v1/sim/session", json={"patient_id": "P001"}).json()
    headers = {"X-Sim-Token": session["token"]}
    for index, status in enumerate(("not_taken", "yes_taken")):
        result = seeded_client.post(
            "/api/v1/sim/messages",
            headers=headers,
            json={
                "patient_id": "P001",
                "client_msg_id": f"slot-{index}",
                "text": "",
                "language": "te",
                "quick_reply": status,
            },
        )
        assert result.status_code == 200
    with engine.connect() as connection:
        statuses = (
            connection.execute(
                text(
                    "SELECT status FROM medication_events WHERE patient_id='P001' "
                    "AND event_date='2026-10-26' AND slot='morning'"
                )
            )
            .scalars()
            .all()
        )
    assert statuses and set(statuses) == {"taken"}


def test_nutrition_never_recommends_avoid_or_limit_foods():
    for conditions in (["diabetes"], ["hypertension"], ["diabetes", "hypertension"]):
        for language in ("en", "te", "hi"):
            tip = daily_tip(conditions, language)
            assert tip
            for food_id in tip["food_ids"]:
                food = next(food for food in FOODS if food["id"] == food_id)
                assert permitted(food, conditions)
            assert not any(c.isdigit() for c in tip["text"])


def test_future_pending_checkins_do_not_hide_missed_streak(seeded_client):
    from app.core.clock import now
    from app.services.fact_builder import build_facts

    with engine.begin() as connection:
        connection.execute(text("UPDATE check_ins SET status='missed' WHERE patient_id='P001'"))
        connection.execute(
            text(
                "INSERT INTO check_ins(id,patient_id,kind,scheduled_for,status) "
                "VALUES ('CI-future','P001','morning','2026-11-01T02:30:00Z','pending')"
            )
        )
        facts = build_facts(connection, "P001", now())
        assert facts["consecutive_no_response"] == 7
        assert facts["needs_human"] is False


def test_checkin_messages_keep_sequence_order(seeded_client):
    sent = seeded_client.post(
        "/api/v1/demo/check-in", json={"patient_id": "P001", "kind": "morning"}
    )
    assert sent.status_code == 200
    expected = ["greeting_morning", "ask_meds_morning", "ask_glucose", "ask_symptoms"]
    keys = [m["template_key"] for m in sent.json()["messages"]]
    assert keys[:4] == expected
    stored = seeded_client.get("/api/v1/patients/P001/messages").json()
    items = stored["items"] if isinstance(stored, dict) else stored
    assert [m["template_key"] for m in items[-len(keys) :]] == keys
    greeting = next(m for m in items if m["template_key"] == "greeting_morning")
    assert "సేతు" in greeting["text"]  # the real greeting, not the "did not understand" fallback

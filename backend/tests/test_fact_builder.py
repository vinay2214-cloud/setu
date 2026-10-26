from sqlalchemy import text

from app.core.clock import now
from app.db import engine
from app.services.fact_builder import build_facts, missed_streak


def test_missed_streak_counts_consecutive_missed_days():
    assert missed_streak({"2026-10-24": {"missed"}, "2026-10-25": {"missed"}}) == 2


def test_taken_resets_missed_streak():
    assert missed_streak({"2026-10-24": {"missed"}, "2026-10-25": {"taken"}}) == 0


def test_unsure_or_missing_days_are_neutral():
    statuses = {"2026-10-23": {"missed"}, "2026-10-24": {"unsure"}, "2026-10-25": {"missed"}}
    assert missed_streak(statuses) == 2


def test_missing_intent_extraction_routes_to_human_review(seeded_client):
    with engine.connect() as connection:
        message_id = connection.execute(
            text("SELECT id FROM messages WHERE patient_id='P001' ORDER BY created_at DESC LIMIT 1")
        ).scalar_one()
        facts = build_facts(connection, "P001", now(), trigger_message_id=message_id)
    assert facts["intent_confidence_min"] == 0.0
    assert facts["needs_human"] is True

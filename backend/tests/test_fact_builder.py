from sqlalchemy import text

from app.core.clock import now
from app.db import engine
from app.services.fact_builder import build_facts, missed_streak
from app.services.intent_extractor import IntentExtractor


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


def test_critical_keyword_aliases_are_independent_of_model_output():
    extractor = IntentExtractor()
    cases = {
        "ayasam": "breathlessness",
        "साँस लेने में तकलीफ़": "breathlessness",
        "saans phool": "breathlessness",
        "moorcha": "fainting",
        "हाथ पैर नहीं चल": "one_sided_weakness",
        "చేయి కాలు పనిచేయడం లేదు": "one_sided_weakness",
        "ज़ुबान लड़खड़": "slurred_speech",
        "chaati noppi": "chest_pain",
        "chaati noppiga undi": "chest_pain",
    }
    for utterance, expected in cases.items():
        result = extractor.extract(utterance)
        assert expected in {item["code"] for item in result["symptoms"]}


def test_critical_negation_is_local_and_ambiguous_mentions_fail_safe():
    extractor = IntentExtractor()
    clear = extractor.extract("No chest pain today")
    chest = next(item for item in clear["symptoms"] if item["code"] == "chest_pain")
    assert chest["negated"] is True
    assert clear["needs_human"] is True
    unrelated = extractor.extract("No fever today but I have chest pain")
    assert (
        next(item for item in unrelated["symptoms"] if item["code"] == "chest_pain")["negated"]
        is False
    )
    clause = extractor.extract("No medication, but chest pain")
    assert (
        next(item for item in clause["symptoms"] if item["code"] == "chest_pain")["negated"]
        is False
    )
    repeated = extractor.extract("No chest pain, now chest pain")
    assert (
        next(item for item in repeated["symptoms"] if item["code"] == "chest_pain")["negated"]
        is False
    )


def test_missed_medication_phrases_never_become_taken():
    extractor = IntentExtractor()
    for phrase in ("No, not taken", "I have not taken my medicine", "I did not take my medicine"):
        result = extractor.extract(phrase, "en")
        assert result["medication_events"][0]["status"] == "missed"
    conflict = extractor.extract("I took it", "en", quick_reply="not_taken")
    assert conflict["medication_events"][0]["status"] == "missed"
    assert conflict["needs_human"] is True

import pytest

from app.services.reply_composer import render_template, validate_reply


@pytest.mark.parametrize(
    "unsafe",
    [
        "You have diabetes.",
        "You are suffering from a disease.",
        "diagnosis: hypertension",
        "Take 10 mg now.",
        "Take 5 tablets.",
        "Take 4 units.",
        "https://example.com",
        "Call +91 99999 99999",
        "{dose}",
        "x" * 401,
        "I prescribe insulin.",
        "Please take metformin",
        "Set the dose to 2 tablets",
        "Use www.example.com",
        "निदान हो गया",
        "మీకు సమస్య ఉంది",
        "You have chest pain",
        "Your diagnosis is clear",
        "http://clinic.example",
        "Take 500mg Metformin",
        "Call 1234567890",
    ],
)
def test_unsafe_reply_strings_are_rejected(unsafe):
    assert not validate_reply(unsafe, "en")


def test_fixed_emergency_template_keeps_108():
    assert "108" in render_template("emergency_advice", "te")


def test_telugu_greeting_with_latin_name_is_not_replaced_by_fallback():
    from app.services.reply_composer import TEMPLATES, render_template

    text = render_template(
        "greeting_morning", "te", {"name": "Ramesh Kumar", "clinic": "Demo Clinic"}
    )
    assert text != TEMPLATES["unclear_ask_again"]["te"]
    assert "Ramesh Kumar" in text and "సేతు" in text


def test_hindi_greeting_with_latin_name_is_not_replaced_by_fallback():
    from app.services.reply_composer import TEMPLATES, render_template

    text = render_template(
        "greeting_morning", "hi", {"name": "Suresh Patel", "clinic": "Demo Clinic"}
    )
    assert text != TEMPLATES["unclear_ask_again"]["hi"]
    assert "Suresh Patel" in text

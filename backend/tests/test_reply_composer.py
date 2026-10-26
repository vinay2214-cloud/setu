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

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_DATA = json.loads((ROOT / "seed" / "message_templates.json").read_text(encoding="utf-8"))
TEMPLATES = TEMPLATE_DATA["templates"]
DENYLIST = TEMPLATE_DATA["validator_denylist"]


def validate_reply(
    text: str, language: str, *, allowed_meds: set[str] | None = None, template_key: str = ""
) -> bool:
    if template_key in TEMPLATES and language in {"en", "te", "hi"}:
        approved = TEMPLATES[template_key][language]
        if "{" not in approved and text == approved:
            return template_key != "emergency_advice" or text == approved
    if len(text) > 400 or re.search(r"https?://|www\.|\+?\d[\d\s()-]{7,}", text):
        return False
    if re.search(r"\{[^}]+\}", text):
        return False
    lower = text.lower()
    if any(term.lower() in lower for terms in DENYLIST.values() for term in terms):
        return False
    if template_key == "emergency_advice":
        if text != TEMPLATES["emergency_advice"][language]:
            return False
    else:
        if re.search(r"\d+\s*(?:mg|ml|mcg|units?|tablets?|tabs?)\b", lower):
            return False
        if re.search(
            r"\b(?:metformin|glimepiride|amlodipine|telmisartan|atorvastatin|insulin)\b", lower
        ):
            if not any(med.lower() in lower for med in (allowed_meds or set())):
                return False
    if language == "te":
        letters = [c for c in text if c.isalpha()]
        if letters and sum("\u0c00" <= c <= "\u0c7f" for c in letters) / len(letters) < 0.6:
            return False
    if language == "hi":
        letters = [c for c in text if c.isalpha()]
        if letters and sum("\u0900" <= c <= "\u097f" for c in letters) / len(letters) < 0.6:
            return False
    return True


def render_template(key: str, language: str, values: dict[str, str] | None = None) -> str:
    if key not in TEMPLATES:
        key = "unclear_ask_again"
    template = TEMPLATES[key].get(language) or TEMPLATES[key]["en"]
    rendered = template.format_map(defaultdict(str, values or {}))
    if not validate_reply(rendered, language, template_key=key):
        # Approved clinical copy is fixed; validator failure falls back to a
        # fixed, localized review prompt, never generated text.
        key = "unclear_ask_again"
        rendered = TEMPLATES[key][language]
    return rendered


def plan_replies(intent: dict, fired_rules: list, language: str) -> list[str]:
    if any(rule.severity == "CRITICAL" for rule in fired_rules):
        return ["emergency_advice"]
    keys = []
    if any(rule.severity in {"HIGH", "MEDIUM"} for rule in fired_rules):
        keys.append("escalate_notified")
    for event in intent.get("medication_events", []):
        keys.append("ack_taken" if event.get("status") == "taken" else "ack_missed_gentle")
    if intent.get("vitals"):
        keys.append("ack_vital")
    if (intent.get("question") or {}).get("category") == "medical":
        keys.append("medical_question_defer")
    if intent.get("needs_human") and not keys:
        keys.append("unclear_ask_again")
    return list(dict.fromkeys(keys))[:3]

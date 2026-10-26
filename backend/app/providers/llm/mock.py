from typing import Any


class MockLLMProvider:
    """Deterministic local provider; always available without network access."""

    def generate_json(self, *, task: str, text: str, language: str | None = None) -> dict[str, Any]:
        if task in {"intent", "intent_extraction"}:
            from app.services.intent_extractor import IntentExtractor

            return IntentExtractor().extract(text, language or "en")
        if task == "summary":
            return {"summary": "A synthetic patient update is available for clinician review."}
        return {"needs_review": True, "warnings": ["Mock provider has no result for this task."]}

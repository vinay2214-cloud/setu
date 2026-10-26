from typing import Any, Protocol


class LLMProvider(Protocol):
    def generate_json(
        self, *, task: str, text: str, language: str | None = None
    ) -> dict[str, Any]: ...

from typing import Protocol


class ChannelAdapter(Protocol):
    def send(self, *, patient_id: str, text: str, template_key: str) -> None: ...

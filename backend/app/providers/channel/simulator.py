class SimulatorAdapter:
    """Offline adapter: outbound messages are persisted by the pipeline."""

    def send(self, *, patient_id: str, text: str, template_key: str) -> None:
        return None

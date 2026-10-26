from datetime import UTC, datetime


def now() -> datetime:
    """Return the current UTC time; demo-clock offsets are layered on in P1."""
    return datetime.now(UTC)

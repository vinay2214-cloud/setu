import math
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def _offset_seconds() -> int:
    from sqlalchemy import text

    from app.db import engine

    try:
        with engine.connect() as connection:
            value = connection.execute(
                text("SELECT offset_seconds FROM demo_clock WHERE id = 1")
            ).scalar_one()
            return int(value)
    except Exception:
        return 0


def real_now() -> datetime:
    """Wall time for authentication, independent of demo time travel."""
    return datetime.now(UTC)


def now() -> datetime:
    """Return current UTC time shifted by the persisted demo-clock offset."""
    return real_now() + timedelta(seconds=_offset_seconds())


def set_time(value: datetime) -> datetime:
    from sqlalchemy import text

    from app.db import engine

    target = value.astimezone(UTC)
    offset = math.ceil((target - real_now()).total_seconds())
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE demo_clock SET offset_seconds = :offset WHERE id = 1"), {"offset": offset}
        )
    return now()


def advance(*, days: int = 0, hours: int = 0) -> datetime:
    return set_time(now() + timedelta(days=days, hours=hours))


def reset() -> datetime:
    from sqlalchemy import text

    from app.db import engine

    with engine.begin() as connection:
        connection.execute(text("UPDATE demo_clock SET offset_seconds = 0 WHERE id = 1"))
    return now()

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def initialize_database() -> None:
    """Create the SQLite schema or apply additive runtime migrations to an existing DB."""
    if not settings.database_url.startswith("sqlite"):
        # PostgreSQL deploys already have the schema; this adds the idempotency snapshot field.
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS response_json TEXT")
            )
        return

    database_path = settings.database_url.removeprefix("sqlite:///")
    if database_path == ":memory:":
        return
    path = Path(database_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    schema_path = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
    with sqlite3.connect(path) as connection:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        message_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "response_json" not in message_columns:
            connection.execute("ALTER TABLE messages ADD COLUMN response_json TEXT")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

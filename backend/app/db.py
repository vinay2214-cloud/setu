from pathlib import Path
import sqlite3

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def initialize_database() -> None:
    """Create the SQLite schema from the checked-in SQL source of truth."""
    if not settings.database_url.startswith("sqlite"):
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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

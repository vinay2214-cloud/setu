from pathlib import Path

import yaml
from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.core.clock import now
from app.db import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str | int]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        db_status = "ok"
    except SQLAlchemyError:
        db_status = "error"

    settings = get_settings()
    rule_path = Path(__file__).resolve().parents[3] / "seed" / "rules" / "diabetes_htn_v1.yaml"
    try:
        rule_pack = yaml.safe_load(rule_path.read_text(encoding="utf-8"))
        loaded_rules = len(rule_pack.get("rules", [])) if isinstance(rule_pack, dict) else 0
    except (OSError, yaml.YAMLError):
        loaded_rules = 0

    return {
        "status": "ok" if db_status == "ok" and loaded_rules else "degraded",
        "db": db_status,
        "rules_loaded": loaded_rules,
        "llm": settings.llm_provider,
        "time": now().isoformat().replace("+00:00", "Z"),
    }

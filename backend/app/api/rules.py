from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text

from app.config import get_settings
from app.core.security import current_clinician
from app.db import engine
from app.rules.engine import evaluate
from app.schemas.api import EvaluateRequest

router = APIRouter(prefix="/rules", tags=["rules"], dependencies=[Depends(current_clinician)])


@router.get("/packs")
def list_rule_packs() -> list[dict]:
    with engine.connect() as connection:
        rows = (
            connection.execute(
                text(
                    "SELECT id,name,version,status,approved_by,approved_at,yaml_text FROM rule_packs"
                )
            )
            .mappings()
            .all()
        )
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "version": row["version"],
            "status": row["status"],
            "approved_by": row["approved_by"],
            "approved_at": row["approved_at"],
            "rule_count": row["yaml_text"].count("  - id:"),
        }
        for row in rows
    ]


@router.get("/packs/{pack_id}")
def get_rule_pack(pack_id: str, request: Request) -> dict:
    with engine.connect() as connection:
        row = (
            connection.execute(text("SELECT * FROM rule_packs WHERE id=:id"), {"id": pack_id})
            .mappings()
            .first()
        )
    if not row:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "Rule pack not found."}
        )
    pack = request.app.state.rule_pack
    pack = request.app.state.rule_pack
    defaults = pack.defaults.get("sla_minutes", {})

    def condition(node: dict) -> str:
        if "all" in node:
            return " AND ".join(f"({condition(child)})" for child in node["all"])
        if "any" in node:
            return " OR ".join(f"({condition(child)})" for child in node["any"])
        if "not" in node:
            return f"NOT ({condition(node['not'])})"
        return f"{node['fact']} {node['op']} {node.get('value', '')}".strip()

    rules = []
    for rule in pack.rules:
        item = rule.model_dump()
        item["condition"] = condition(rule.when)
        item["sla_minutes"] = int(defaults.get(rule.severity, 4320))
        rules.append(item)
    return {
        "id": row["id"],
        "name": row["name"],
        "version": row["version"],
        "status": row["status"],
        "approved_by": row["approved_by"],
        "approved_at": row["approved_at"],
        "rules": rules,
    }


@router.post("/evaluate")
def evaluate_rules(
    payload: EvaluateRequest,
    request: Request,
    clinician: dict = Depends(current_clinician),
) -> dict:
    if get_settings().app_env != "development":
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Rule evaluation is development-only."},
        )
    if not getattr(request.app.state, "rule_pack", None):
        raise HTTPException(
            status_code=503, detail={"code": "internal_error", "message": "Rules are not loaded."}
        )
    return {
        "fired": [
            rule.model_dump() for rule in evaluate(request.app.state.rule_pack, payload.facts)
        ]
    }

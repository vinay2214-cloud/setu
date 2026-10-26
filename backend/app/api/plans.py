import json
import secrets
from datetime import UTC, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config import get_settings
from app.core.audit import record
from app.core.clock import IST, now
from app.core.security import current_clinician
from app.db import engine
from app.providers.llm.gemini import GeminiProvider
from app.providers.llm.mock import MockLLMProvider
from app.services.plan_compiler import compile_plan, verify_plan

router = APIRouter(tags=["care-plans"], dependencies=[Depends(current_clinician)])


class DocumentRequest(BaseModel):
    kind: Literal["discharge_summary"] = "discharge_summary"
    text: str = Field(min_length=1, max_length=30000)


class DraftRequest(BaseModel):
    document_id: str


class PlanEditRequest(BaseModel):
    plan: dict
    expected_version: int


def _get(connection, plan_id: str) -> dict:
    row = (
        connection.execute(text("SELECT * FROM care_plans WHERE id=:id"), {"id": plan_id})
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, detail="Care plan not found.")
    source = (
        connection.execute(
            text("SELECT raw_text FROM documents WHERE id=:id"), {"id": row["source_document_id"]}
        ).scalar()
        or ""
    )
    return {
        **dict(row),
        "plan": json.loads(row["plan_json"]),
        "warnings": json.loads(row["warnings_json"]),
        "source_text": source,
    }


def _latest(connection, plan: dict) -> None:
    version = connection.execute(
        text("SELECT MAX(version) FROM care_plans WHERE patient_id=:id"), {"id": plan["patient_id"]}
    ).scalar()
    if plan["version"] != version:
        raise HTTPException(
            409, detail="A newer care plan version exists; reload before continuing."
        )


@router.post("/patients/{patient_id}/documents", status_code=201)
def document(
    patient_id: str, payload: DocumentRequest, actor: dict = Depends(current_clinician)
) -> dict:
    doc_id = f"DOC-{secrets.token_hex(4)}"
    with engine.begin() as connection:
        if not connection.execute(
            text("SELECT 1 FROM patients WHERE id=:id"), {"id": patient_id}
        ).first():
            raise HTTPException(404, detail="Patient not found.")
        connection.execute(
            text(
                "INSERT INTO documents(id,patient_id,kind,raw_text,uploaded_by,uploaded_at) VALUES (:id,:p,:kind,:raw,:actor,:at)"
            ),
            {
                "id": doc_id,
                "p": patient_id,
                "kind": payload.kind,
                "raw": payload.text,
                "actor": actor["id"],
                "at": now().isoformat(),
            },
        )
        record(
            connection,
            actor=actor["id"],
            action="document_uploaded",
            entity="document",
            entity_id=doc_id,
        )
    return {"id": doc_id}


@router.post("/patients/{patient_id}/care-plans/draft", status_code=201)
def draft(patient_id: str, payload: DraftRequest, actor: dict = Depends(current_clinician)) -> dict:
    with engine.connect() as connection:
        source = connection.execute(
            text("SELECT raw_text FROM documents WHERE id=:id AND patient_id=:p"),
            {"id": payload.document_id, "p": patient_id},
        ).scalar()
        lang = connection.execute(
            text("SELECT language FROM patients WHERE id=:p"), {"p": patient_id}
        ).scalar()
    if source is None:
        raise HTTPException(404, detail="Source document not found.")
    provider = GeminiProvider() if get_settings().llm_provider == "gemini" else MockLLMProvider()
    plan, warnings = compile_plan(source, lang, provider)
    plan_id = f"CP-{secrets.token_hex(4)}"
    with engine.begin() as connection:
        version = (
            connection.execute(
                text("SELECT MAX(version) FROM care_plans WHERE patient_id=:p"), {"p": patient_id}
            ).scalar()
            or 0
        ) + 1
        connection.execute(
            text(
                "INSERT INTO care_plans(id,patient_id,version,status,plan_json,warnings_json,source_document_id,created_by,created_at) VALUES (:id,:p,:v,'draft',:plan,:warnings,:doc,:actor,:at)"
            ),
            {
                "id": plan_id,
                "p": patient_id,
                "v": version,
                "plan": json.dumps(plan),
                "warnings": json.dumps(warnings),
                "doc": payload.document_id,
                "actor": actor["id"],
                "at": now().isoformat(),
            },
        )
        record(
            connection,
            actor=actor["id"],
            action="plan_drafted",
            entity="care_plan",
            entity_id=plan_id,
        )
        return _get(connection, plan_id)


@router.get("/care-plans/{plan_id}")
def get_plan(plan_id: str) -> dict:
    with engine.connect() as connection:
        return _get(connection, plan_id)


@router.get("/patients/{patient_id}/care-plans")
def versions(patient_id: str) -> dict:
    with engine.connect() as connection:
        ids = (
            connection.execute(
                text("SELECT id FROM care_plans WHERE patient_id=:p ORDER BY version DESC"),
                {"p": patient_id},
            )
            .scalars()
            .all()
        )
        return {"items": [_get(connection, pid) for pid in ids]}


@router.patch("/care-plans/{plan_id}")
def edit(plan_id: str, payload: PlanEditRequest, actor: dict = Depends(current_clinician)) -> dict:
    with engine.begin() as connection:
        old = _get(connection, plan_id)
        _latest(connection, old)
        if old["version"] != payload.expected_version:
            raise HTTPException(409, detail="Plan version conflict.")
        plan, warnings = verify_plan(payload.plan, old["source_text"])
        new_id = f"CP-{secrets.token_hex(4)}"
        connection.execute(
            text(
                "INSERT INTO care_plans(id,patient_id,version,status,plan_json,warnings_json,source_document_id,created_by,created_at) VALUES (:id,:p,:v,'draft',:plan,:warnings,:doc,:actor,:at)"
            ),
            {
                "id": new_id,
                "p": old["patient_id"],
                "v": old["version"] + 1,
                "plan": json.dumps(plan),
                "warnings": json.dumps(warnings),
                "doc": old["source_document_id"],
                "actor": actor["id"],
                "at": now().isoformat(),
            },
        )
        record(
            connection,
            actor=actor["id"],
            action="plan_edited",
            entity="care_plan",
            entity_id=new_id,
            detail={"previous_id": plan_id, "before": old["plan"], "after": plan},
        )
        return _get(connection, new_id)


@router.post("/care-plans/{plan_id}/approve")
def approve(plan_id: str, actor: dict = Depends(current_clinician)) -> dict:
    with engine.begin() as connection:
        plan = _get(connection, plan_id)
        _latest(connection, plan)
        if plan["status"] != "draft" or not plan["plan"].get("medications"):
            raise HTTPException(409, detail="A source-verified draft with medicines is required.")
        connection.execute(
            text(
                "UPDATE care_plans SET status='approved', approved_by=:actor,approved_at=:at WHERE id=:id"
            ),
            {"id": plan_id, "actor": actor["id"], "at": now().isoformat()},
        )
        record(
            connection,
            actor=actor["id"],
            action="plan_approved",
            entity="care_plan",
            entity_id=plan_id,
        )
        return _get(connection, plan_id)


@router.post("/care-plans/{plan_id}/activate")
def activate(plan_id: str, actor: dict = Depends(current_clinician)) -> dict:
    with engine.begin() as connection:
        plan = _get(connection, plan_id)
        _latest(connection, plan)
        if plan["status"] != "approved" or not plan["approved_by"]:
            raise HTTPException(
                409,
                detail={
                    "code": "plan_not_approved",
                    "message": "Care plan must be approved before activation.",
                },
            )
        connection.execute(
            text(
                "UPDATE care_plans SET status='completed' WHERE patient_id=:p AND status='active'"
            ),
            {"p": plan["patient_id"]},
        )
        connection.execute(
            text("UPDATE care_plans SET status='active',activated_at=:at WHERE id=:id"),
            {"id": plan_id, "at": now().isoformat()},
        )
        connection.execute(
            text("UPDATE patients SET status='active' WHERE id=:p"), {"p": plan["patient_id"]}
        )
        tomorrow = now().astimezone(IST).date() + timedelta(days=1)
        for kind, hour in (("morning", 8), ("evening", 19)):
            scheduled = (
                datetime.combine(tomorrow, time(hour), IST)
                .astimezone(UTC)
                .isoformat()
                .replace("+00:00", "Z")
            )
            connection.execute(
                text(
                    "INSERT INTO check_ins(id,patient_id,kind,scheduled_for,status) VALUES (:id,:p,:kind,:at,'pending') ON CONFLICT(patient_id,kind,scheduled_for) DO NOTHING"
                ),
                {
                    "id": f"CI-{secrets.token_hex(4)}",
                    "p": plan["patient_id"],
                    "kind": kind,
                    "at": scheduled,
                },
            )
        record(
            connection,
            actor=actor["id"],
            action="plan_activated",
            entity="care_plan",
            entity_id=plan_id,
        )
        return _get(connection, plan_id)

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import text

from app.config import get_settings
from app.core.security import create_token, current_clinician, verify_password
from app.db import engine
from app.schemas.api import LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, response: Response) -> dict:
    with engine.connect() as connection:
        clinician = (
            connection.execute(
                text(
                    "SELECT id, name, email, role, clinic, password_hash FROM clinicians WHERE email = :email"
                ),
                {"email": payload.email},
            )
            .mappings()
            .first()
        )
    if not clinician or not verify_password(payload.password, clinician["password_hash"]):
        raise HTTPException(
            status_code=401, detail={"code": "unauthorized", "message": "Invalid credentials."}
        )
    token = create_token(clinician["id"], clinician["email"], clinician["role"])
    response.set_cookie(
        "setu_session",
        token,
        httponly=True,
        samesite="lax",
        secure=get_settings().app_env != "development",
        max_age=28800,
    )
    return {"clinician": {key: clinician[key] for key in ("id", "name", "role")}}


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie("setu_session")


@router.get("/me")
def me(clinician: dict = Depends(current_clinician)) -> dict:
    return {key: clinician[key] for key in ("id", "name", "role", "clinic")}

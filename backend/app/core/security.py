import hashlib
import hmac
from datetime import timedelta
from typing import Any

import jwt
from fastapi import Cookie, HTTPException
from sqlalchemy import text

from app.config import get_settings
from app.core.clock import now
from app.db import engine


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt_hex, digest = stored.split("$", 2)
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1
        ).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


def create_token(clinician_id: str, email: str, role: str) -> str:
    settings = get_settings()
    issued = now()
    return jwt.encode(
        {
            "sub": clinician_id,
            "email": email,
            "role": role,
            "iat": issued,
            "exp": issued + timedelta(hours=8),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def current_clinician(setu_session: str | None = Cookie(default=None)) -> dict[str, Any]:
    if not setu_session:
        raise HTTPException(status_code=401, detail="unauthorized")
    try:
        claims = jwt.decode(setu_session, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="unauthorized") from exc
    with engine.connect() as connection:
        clinician = (
            connection.execute(
                text("SELECT id, name, email, role, clinic FROM clinicians WHERE id = :id"),
                {"id": claims.get("sub")},
            )
            .mappings()
            .first()
        )
    if not clinician:
        raise HTTPException(status_code=401, detail="unauthorized")
    return dict(clinician)

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.api.alerts import router as alerts_router
from app.api.auth import router as auth_router
from app.api.demo import router as demo_router
from app.api.health import router as health_router
from app.api.patients import router as patients_router
from app.api.plans import router as plans_router
from app.api.rules import router as rules_router
from app.api.sim import router as sim_router
from app.config import get_settings
from app.db import initialize_database
from app.models import initialize_models
from app.rules.loader import load_pack
from app.seed_loader import ensure_demo_accounts

ROOT = Path(__file__).resolve().parents[2]
RULE_PACK_PATH = ROOT / "seed" / "rules" / "diabetes_htn_v1.yaml"


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    if settings.app_env not in {"development", "demo"} and settings.demo_mode:
        raise RuntimeError("DEMO_MODE requires development or explicit demo environment.")
    default_secret = "local-demo-only-change-this-secret"
    if settings.app_env != "development" and settings.jwt_secret == default_secret:
        raise RuntimeError("JWT_SECRET must be configured outside development.")
    initialize_database()
    initialize_models()
    application.state.rule_pack = load_pack(RULE_PACK_PATH)
    ensure_demo_accounts()
    if settings.demo_auto_seed and settings.demo_mode:
        from sqlalchemy import text

        from app.db import engine
        from app.seed_loader import seed_demo

        with engine.connect() as connection:
            populated = connection.execute(text("SELECT COUNT(*) FROM patients")).scalar()
        if not populated:
            seed_demo()
    from apscheduler.schedulers.background import BackgroundScheduler

    from app.services.orchestrator import tick

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        tick, "interval", seconds=30, args=[application.state.rule_pack], max_instances=1
    )
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Setu API", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        code = detail.get("code") if isinstance(detail, dict) else None
        message = detail.get("message") if isinstance(detail, dict) else None
        if code is None:
            code = {401: "unauthorized", 403: "forbidden", 404: "not_found"}.get(
                exc.status_code, "internal_error"
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": message or str(detail),
                    "request_id": f"req_{uuid4().hex[:8]}",
                }
            },
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "request_id": f"req_{uuid4().hex[:8]}",
                }
            },
        )

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                    "request_id": f"req_{uuid4().hex[:8]}",
                }
            },
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(patients_router, prefix="/api/v1")
    app.include_router(alerts_router, prefix="/api/v1")
    app.include_router(rules_router, prefix="/api/v1")
    app.include_router(demo_router, prefix="/api/v1")
    app.include_router(sim_router, prefix="/api/v1")
    app.include_router(plans_router, prefix="/api/v1")
    return app


app = create_app()

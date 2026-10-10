import logging
from time import perf_counter
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.api.routes.actions import router as actions_router
from app.api.routes.auth import router as auth_router
from app.api.routes.fields import router as fields_router
from app.api.routes.health import router as health_router
from app.api.routes.methodology import router as methodology_router
from app.api.routes.ml import router as ml_router
from app.api.routes.regions import router as regions_router
from app.core.config import get_settings
from app.core.database import connect_to_mongo
from app.core.errors import register_error_handlers
from app.core.rate_limit import LoginRateLimiter
from app.services.ml_client import MLServiceClient


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        client, database = await connect_to_mongo(settings)
        application.state.mongo_client = client
        application.state.db = database
        ml_service_client = (
            MLServiceClient(
                settings.ml_service_url,
                settings.ml_service_api_key,
                settings.ml_request_timeout_seconds,
                settings.ml_status_timeout_seconds,
            )
            if settings.ml_service_enabled
            else None
        )
        application.state.ml_service_client = ml_service_client
        try:
            yield
        finally:
            if ml_service_client is not None:
                await ml_service_client.close()
            client.close()

    application = FastAPI(
        title="CropShield AI API",
        description="Field-level vegetation anomaly and inspection API.",
        version="0.1.0",
        openapi_tags=[
            {"name": "health", "description": "Process health checks."},
            {"name": "auth", "description": "Account registration, login, and profile."},
            {"name": "regions", "description": "Region summaries, maps, and queues."},
            {"name": "fields", "description": "Field results and time-series evidence."},
            {"name": "actions", "description": "User-owned inspection action tracking."},
            {"name": "methodology", "description": "Public analysis methods and validation."},
            {"name": "ml", "description": "Authenticated, non-persistent ML previews and service status."},
        ],
        lifespan=lifespan,
    )
    application.state.login_rate_limiter = LoginRateLimiter()
    application.state.ml_warmup_rate_limiter = LoginRateLimiter()

    @application.middleware("http")
    async def log_request(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        logger = logging.getLogger("cropshield.request")
        started = perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            logger.info(
                "http_request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        allow_credentials=False,
    )
    register_error_handlers(application)
    application.include_router(health_router, prefix="/api")
    application.include_router(auth_router, prefix="/api")
    application.include_router(regions_router, prefix="/api")
    application.include_router(fields_router, prefix="/api")
    application.include_router(actions_router, prefix="/api")
    application.include_router(methodology_router, prefix="/api")
    application.include_router(ml_router, prefix="/api")
    return application


app = create_app()
from __future__ import annotations

import asyncio
import hashlib
import re
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings, get_settings
from app.core.errors import error_response, register_error_handlers
from app.core.logging import (
    configure_logging,
    reset_request_id,
    set_request_id,
)
from app.routes.scoring import router as scoring_router
from app.services.model_store import ModelStore

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_RATE_WINDOW_SECONDS = 60.0


def _safe_request_id(value: str | None) -> str:
    if value is not None and _REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return str(uuid.uuid4())


class RequestHardeningMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self.request_history: dict[tuple[str, str], deque[float]] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_headers = dict(scope.get("headers", []))
        raw_request_id = request_headers.get(b"x-request-id", b"").decode(
            "latin-1"
        )
        request_id = _safe_request_id(raw_request_id or None)
        scope.setdefault("state", {})["request_id"] = request_id
        token = set_request_id(request_id)
        response_started = False

        async def send_with_headers(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower()
                    not in {
                        b"x-request-id",
                        b"x-content-type-options",
                        b"x-frame-options",
                        b"referrer-policy",
                        b"content-security-policy",
                        b"cache-control",
                    }
                ]
                headers.extend(
                    [
                        (b"x-request-id", request_id.encode("ascii")),
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"content-security-policy", b"default-src 'none'"),
                        (b"cache-control", b"no-store"),
                    ]
                )
                message["headers"] = headers
            await send(message)

        async def respond(status_code: int, detail: str, code: str) -> None:
            response = error_response(status_code, detail, code)
            await response(scope, receive, send_with_headers)

        try:
            try:
                async with asyncio.timeout(self.settings.request_timeout_seconds):
                    content_length = request_headers.get(b"content-length")
                    if content_length is not None:
                        if not content_length.isdigit():
                            await respond(
                                400,
                                "Invalid Content-Length header",
                                "VALIDATION_ERROR",
                            )
                            return
                        declared_size = int(content_length)
                        if declared_size > self.settings.max_request_bytes:
                            await respond(
                                413,
                                "Request body exceeds the configured limit",
                                "PAYLOAD_TOO_LARGE",
                            )
                            return

                    path = scope.get("path", "")
                    if path not in {"/health", "/ready"}:
                        now = time.monotonic()
                        for bucket, history in tuple(self.request_history.items()):
                            while history and now - history[0] >= _RATE_WINDOW_SECONDS:
                                history.popleft()
                            if not history:
                                del self.request_history[bucket]

                        client = scope.get("client")
                        client_host = str(client[0]) if client else "unknown"
                        supplied_key = request_headers.get(b"x-service-key", b"")
                        key_hash = hashlib.sha256(supplied_key).hexdigest()
                        buckets = (("ip", client_host), ("key", key_hash))
                        histories = [
                            self.request_history.setdefault(bucket, deque())
                            for bucket in buckets
                        ]
                        if any(
                            len(history) >= self.settings.rate_limit_requests_per_minute
                            for history in histories
                        ):
                            await respond(
                                429,
                                "Request rate limit exceeded",
                                "RATE_LIMITED",
                            )
                            return
                        for history in histories:
                            history.append(now)

                    body_chunks: list[bytes] = []
                    body_size = 0
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        if message["type"] != "http.request":
                            continue
                        chunk = message.get("body", b"")
                        body_size += len(chunk)
                        if body_size > self.settings.max_request_bytes:
                            await respond(
                                413,
                                "Request body exceeds the configured limit",
                                "PAYLOAD_TOO_LARGE",
                            )
                            return
                        body_chunks.append(chunk)
                        if not message.get("more_body", False):
                            break

                    body = b"".join(body_chunks)
                    body_sent = False

                    async def replay_receive() -> Message:
                        nonlocal body_sent
                        if not body_sent:
                            body_sent = True
                            return {
                                "type": "http.request",
                                "body": body,
                                "more_body": False,
                            }
                        return await receive()

                    await self.app(scope, replay_receive, send_with_headers)
            except TimeoutError:
                if not response_started:
                    await respond(504, "Request processing timed out", "REQUEST_TIMEOUT")
        finally:
            reset_request_id(token)


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        application.state.metadata_client = AsyncIOMotorClient(
            app_settings.mongodb_uri,
            serverSelectionTimeoutMS=3000,
            connectTimeoutMS=3000,
            socketTimeoutMS=3000,
        )
        database = application.state.metadata_client[app_settings.mongodb_db]
        model_store = ModelStore(
            database.model_artifacts,
            app_settings.model_dir,
            app_settings.model_refresh_interval_seconds,
        )
        application.state.model_store = model_store
        try:
            await model_store.start()
            yield
        finally:
            await model_store.stop()
            application.state.metadata_client.close()

    docs_enabled = app_settings.app_env != "production"
    application = FastAPI(
        title="CropShield ML Service",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    application.state.settings = app_settings
    register_error_handlers(application)
    application.include_router(scoring_router)
    application.add_middleware(RequestHardeningMiddleware, settings=app_settings)

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/ready", response_model=None)
    async def ready(request: Request) -> dict[str, str] | JSONResponse:
        model_store: ModelStore = request.app.state.model_store
        if not model_store.ready:
            code = model_store.error_code or "MODEL_NOT_LOADED"
            return error_response(503, "The verified model is not ready", code)
        return {
            "status": "ready",
            "model_version": model_store.runtime.version or "",
        }

    return application


app = create_app()

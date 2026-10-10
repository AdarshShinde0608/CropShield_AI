from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


def error_response(status_code: int, detail: str, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "code": code},
    )


async def http_exception_handler(
    request: Request,
    exception: StarletteHTTPException,
) -> JSONResponse:
    del request
    if isinstance(exception.detail, Mapping):
        detail = exception.detail.get("detail")
        code = exception.detail.get("code")
        if isinstance(detail, str) and isinstance(code, str):
            return error_response(exception.status_code, detail, code)
    message = exception.detail if isinstance(exception.detail, str) else "Request failed"
    code = "RATE_LIMITED" if exception.status_code == 429 else "HTTP_ERROR"
    return error_response(exception.status_code, message, code)


async def validation_exception_handler(
    request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    del request
    messages = [
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        for error in exception.errors()
    ]
    return error_response(422, "; ".join(messages), "VALIDATION_ERROR")


async def unhandled_exception_handler(request: Request, exception: Exception) -> JSONResponse:
    logger.error(
        "request_failed",
        extra={"event": "request_failed", "error_type": type(exception).__name__},
    )
    del request
    return error_response(500, "Internal server error", "INTERNAL_SERVER_ERROR")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

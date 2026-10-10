import logging
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

_HTTP_ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    429: "RATE_LIMITED",
}


def _error_response(status_code: int, detail: str, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "code": code},
    )


async def http_exception_handler(
    request: Request,
    exception: StarletteHTTPException,
) -> JSONResponse:
    del request
    detail = exception.detail
    if isinstance(detail, Mapping):
        message = detail.get("detail")
        code = detail.get("code")
        if isinstance(message, str) and isinstance(code, str):
            return _error_response(exception.status_code, message, code)
    message = detail if isinstance(detail, str) else str(detail)
    code = _HTTP_ERROR_CODES.get(exception.status_code, "HTTP_ERROR")
    return _error_response(exception.status_code, message, code)


async def validation_exception_handler(
    request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    del request
    messages = [
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        for error in exception.errors()
    ]
    return _error_response(422, "; ".join(messages), "VALIDATION_ERROR")


async def unhandled_exception_handler(request: Request, exception: Exception) -> JSONResponse:
    logger.error(
        "Unhandled request exception",
        extra={
            "method": request.method,
            "path": request.url.path,
            "error_type": type(exception).__name__,
        },
        exc_info=(type(exception), exception, exception.__traceback__),
    )
    return _error_response(500, "Internal server error", "INTERNAL_SERVER_ERROR")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
import hmac

from fastapi import Header, HTTPException, Request


def require_service_key(
    request: Request,
    x_service_key: str | None = Header(default=None, alias="X-Service-Key"),
) -> None:
    settings = request.app.state.settings
    accepted_keys = (
        settings.ml_service_api_key,
        settings.ml_service_api_key_previous,
    )
    if x_service_key is None or not any(
        expected and hmac.compare_digest(x_service_key, expected)
        for expected in accepted_keys
    ):
        raise HTTPException(
            status_code=401,
            detail={"detail": "A valid service key is required", "code": "SERVICE_KEY_INVALID"},
        )

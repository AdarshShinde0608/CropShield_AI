from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.core.config import Settings, get_settings


class TokenExpiredError(ValueError):
    """Raised when a JWT has expired."""


class TokenInvalidError(ValueError):
    """Raised when a JWT is invalid or missing required claims."""


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        return False
    try:
        return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str,
    role: str,
    settings: Settings | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    active_settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=active_settings.jwt_expire_minutes)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(payload, active_settings.jwt_secret, algorithm="HS256")


def decode_token(
    token: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    active_settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            active_settings.jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "role"]},
        )
    except ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired") from exc
    except InvalidTokenError as exc:
        raise TokenInvalidError("Token is invalid") from exc

    if not isinstance(payload.get("sub"), str) or not payload["sub"]:
        raise TokenInvalidError("Token subject is invalid")
    if not isinstance(payload.get("role"), str) or not payload["role"]:
        raise TokenInvalidError("Token role is invalid")
    return payload
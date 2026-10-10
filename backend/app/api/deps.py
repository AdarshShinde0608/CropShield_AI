from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.security import TokenExpiredError, TokenInvalidError, decode_token
from app.schemas.auth import UserOut
from app.services.auth_service import UserNotFoundError, get_user_by_id

bearer_scheme = HTTPBearer(auto_error=False)


def _token_error(detail: str, code: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"detail": detail, "code": code},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    database: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
) -> UserOut:
    if credentials is None:
        raise _token_error("Bearer token is required", "TOKEN_INVALID")

    try:
        payload: dict[str, Any] = decode_token(credentials.credentials)
    except TokenExpiredError as exc:
        raise _token_error("Token has expired", "TOKEN_EXPIRED") from exc
    except TokenInvalidError as exc:
        raise _token_error("Token is invalid", "TOKEN_INVALID") from exc

    try:
        return await get_user_by_id(database, payload["sub"])
    except UserNotFoundError as exc:
        raise _token_error("Token is invalid", "TOKEN_INVALID") from exc


CurrentUser = Annotated[UserOut, Depends(get_current_user)]
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import LoginRateLimiter
from app.schemas.auth import (
    LoginRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services.auth_service import (
    DuplicateEmailError,
    InvalidCredentialsError,
    UserNotFoundError,
    authenticate_user,
    register_user,
    update_user_profile,
)

router = APIRouter(prefix="/auth", tags=["auth"])
DatabaseDep = Annotated[AsyncIOMotorDatabase, Depends(get_db)]


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user",
)
async def register(
    request: RegisterRequest,
    database: DatabaseDep,
) -> TokenResponse:
    try:
        return await register_user(database, request, get_settings())
    except DuplicateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "detail": "An account with this email already exists",
                "code": "EMAIL_EXISTS",
            },
        ) from exc


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in",
)
async def login(
    request: LoginRequest,
    database: DatabaseDep,
    http_request: Request,
) -> TokenResponse:
    client_ip = http_request.client.host if http_request.client else "unknown"
    limiter: LoginRateLimiter = http_request.app.state.login_rate_limiter
    if not limiter.allow(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"detail": "Too many login attempts", "code": "RATE_LIMITED"},
        )
    try:
        return await authenticate_user(database, request, get_settings())
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "detail": "Invalid email or password",
                "code": "INVALID_CREDENTIALS",
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.get("/me", response_model=UserOut, summary="Get current user")
async def get_me(current_user: CurrentUser) -> UserOut:
    return current_user


@router.patch("/me", response_model=UserOut, summary="Update current user")
async def patch_me(
    request: ProfileUpdateRequest,
    current_user: CurrentUser,
    database: DatabaseDep,
) -> UserOut:
    try:
        return await update_user_profile(database, current_user.id, request)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Token is invalid", "code": "TOKEN_INVALID"},
        ) from exc
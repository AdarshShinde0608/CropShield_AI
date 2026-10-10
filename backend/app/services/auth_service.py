from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.config import Settings, get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.schemas.auth import (
    LoginRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)


class DuplicateEmailError(Exception):
    """Raised when registration uses an email that is already registered."""


class InvalidCredentialsError(Exception):
    """Raised when the email/password pair is not valid."""


class UserNotFoundError(Exception):
    """Raised when a user referenced by a valid token no longer exists."""


def _user_out(document: dict[str, Any]) -> UserOut:
    return UserOut(
        id=str(document["_id"]),
        email=document["email"],
        name=document["name"],
        role=document["role"],
        language=document["language"],
    )


async def register_user(
    database: AsyncIOMotorDatabase,
    request: RegisterRequest,
    settings: Settings | None = None,
) -> TokenResponse:
    document = {
        "email": str(request.email),
        "password_hash": hash_password(request.password.get_secret_value()),
        "name": request.name,
        "role": "officer",
        "language": request.language,
    }
    try:
        result = await database.users.insert_one(document)
    except DuplicateKeyError as exc:
        raise DuplicateEmailError from exc

    user_document = {**document, "_id": result.inserted_id}
    user = _user_out(user_document)
    token = create_access_token(user.id, user.role, settings or get_settings())
    return TokenResponse(access_token=token, user=user)


async def authenticate_user(
    database: AsyncIOMotorDatabase,
    request: LoginRequest,
    settings: Settings | None = None,
) -> TokenResponse:
    document = await database.users.find_one({"email": str(request.email)})
    password = request.password.get_secret_value()
    if document is None or not verify_password(
        password,
        document.get("password_hash", ""),
    ):
        raise InvalidCredentialsError

    user = _user_out(document)
    token = create_access_token(user.id, user.role, settings or get_settings())
    return TokenResponse(access_token=token, user=user)


async def get_user_by_id(
    database: AsyncIOMotorDatabase,
    user_id: str,
) -> UserOut:
    if not ObjectId.is_valid(user_id):
        raise UserNotFoundError
    document = await database.users.find_one(
        {"_id": ObjectId(user_id)},
        {"password_hash": 0},
    )
    if document is None:
        raise UserNotFoundError
    return _user_out(document)


async def update_user_profile(
    database: AsyncIOMotorDatabase,
    user_id: str,
    request: ProfileUpdateRequest,
) -> UserOut:
    if not ObjectId.is_valid(user_id):
        raise UserNotFoundError
    updates = request.model_dump(exclude_unset=True, exclude_none=True)
    result = await database.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": updates},
    )
    if result.matched_count == 0:
        raise UserNotFoundError
    return await get_user_by_id(database, user_id)
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from mongomock_motor import AsyncMongoMockClient

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app

TEST_EMAIL = "officer@example.org"
TEST_PASSWORD = "correct-horse"


@pytest_asyncio.fixture(scope="session")
async def auth_test_database() -> AsyncIterator[Any]:
    client = AsyncMongoMockClient()
    database_name = f"cropshield_auth_test_{uuid4().hex}"
    database = client[database_name]
    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: database
    try:
        yield database
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override
        await client.drop_database(database_name)
        client.close()


@pytest_asyncio.fixture(autouse=True)
async def clear_auth_test_database(auth_test_database: Any) -> None:
    for collection_name in await auth_test_database.list_collection_names():
        await auth_test_database.drop_collection(collection_name)
    await auth_test_database.users.create_index("email", unique=True)


@pytest_asyncio.fixture
async def client(auth_test_database: Any) -> AsyncIterator[httpx.AsyncClient]:
    del auth_test_database
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as test_client:
        yield test_client


async def register_user(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.post(
        "/api/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": "Test Officer",
            "language": "en",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_register_stores_hash_and_returns_safe_user(
    client: httpx.AsyncClient,
    auth_test_database: Any,
) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": "Test Officer",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == TEST_EMAIL
    assert body["user"]["role"] == "officer"
    assert body["user"]["language"] == "en"
    assert "password_hash" not in body["user"]
    assert TEST_PASSWORD not in response.text

    stored_user = await auth_test_database.users.find_one({"email": TEST_EMAIL})
    assert stored_user["password_hash"] != TEST_PASSWORD


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(client: httpx.AsyncClient) -> None:
    await register_user(client)

    response = await client.post(
        "/api/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": "Second Account",
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "EMAIL_EXISTS"


@pytest.mark.asyncio
async def test_login_returns_token_for_valid_credentials(
    client: httpx.AsyncClient,
) -> None:
    await register_user(client)

    response = await client.post(
        "/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["user"]["email"] == TEST_EMAIL
    assert "password_hash" not in response.text
    assert TEST_PASSWORD not in response.text


@pytest.mark.asyncio
async def test_login_uses_generic_error_for_wrong_password(
    client: httpx.AsyncClient,
) -> None:
    await register_user(client)

    response = await client.post(
        "/api/auth/login",
        json={"email": TEST_EMAIL, "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid email or password",
        "code": "INVALID_CREDENTIALS",
    }


@pytest.mark.asyncio
async def test_me_returns_safe_user_with_token(client: httpx.AsyncClient) -> None:
    registration = await register_user(client)

    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {registration['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == TEST_EMAIL
    assert "password_hash" not in response.text


@pytest.mark.asyncio
async def test_me_requires_token(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"


@pytest.mark.asyncio
async def test_me_rejects_expired_token(client: httpx.AsyncClient) -> None:
    registration = await register_user(client)
    token = create_access_token(
        subject=registration["user"]["id"],
        role="officer",
        settings=get_settings(),
        expires_delta=timedelta(seconds=-1),
    )

    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_patch_me_updates_name_and_language(
    client: httpx.AsyncClient,
) -> None:
    registration = await register_user(client)
    response = await client.patch(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {registration['access_token']}"},
        json={"name": "Officer Updated", "language": "mr"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Officer Updated"
    assert response.json()["language"] == "mr"
    assert "password_hash" not in response.text


@pytest.mark.asyncio
async def test_registration_rejects_short_password(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": "short",
            "name": "Test Officer",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_password_hashing_uses_bcrypt() -> None:
    encoded = hash_password(TEST_PASSWORD)

    assert encoded.startswith("$2")
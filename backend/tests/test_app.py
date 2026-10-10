import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app


@pytest.mark.asyncio
async def test_docs_and_cors_preflight() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        docs_response = await client.get("/docs")
        preflight_response = await client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert docs_response.status_code == 200
    assert preflight_response.status_code == 200
    assert (
        preflight_response.headers["access-control-allow-origin"]
        == "http://localhost:5173"
    )
    assert "GET" in preflight_response.headers["access-control-allow-methods"]


def test_production_rejects_the_development_jwt_placeholder() -> None:
    with pytest.raises(ValidationError, match="Production requires a unique JWT_SECRET"):
        Settings(
            app_env="production",
            jwt_secret="replace-with-a-random-secret-of-at-least-32-bytes",
        )


def test_production_accepts_a_unique_secret_of_sufficient_length() -> None:
    settings = Settings(
        app_env="production",
        jwt_secret="distinct-production-secret-material-0123456789",
    )

    assert settings.app_env == "production"

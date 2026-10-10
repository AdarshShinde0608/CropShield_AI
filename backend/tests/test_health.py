from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.health import router as health_router


def test_health_returns_ok() -> None:
    application = FastAPI()
    application.include_router(health_router, prefix="/api")

    with TestClient(application) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

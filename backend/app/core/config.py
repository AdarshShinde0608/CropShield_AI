from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mongodb_uri: str = Field(
        default="mongodb://localhost:27017",
        validation_alias="MONGODB_URI",
    )
    mongodb_db: str = Field(default="cropshield", validation_alias="MONGODB_DB")
    app_env: Literal["development", "production"] = Field(
        default="development",
        validation_alias="APP_ENV",
    )
    jwt_secret: str = Field(
        default="replace-with-a-random-secret-of-at-least-32-bytes",
        validation_alias="JWT_SECRET",
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(
        default=60,
        gt=0,
        validation_alias="JWT_EXPIRE_MINUTES",
    )
    cors_origins: str = Field(
        default="http://localhost:5173",
        validation_alias="CORS_ORIGINS",
    )
    ml_service_url: str = Field(
        default="http://localhost:8001",
        validation_alias="ML_SERVICE_URL",
    )
    ml_service_enabled: bool = Field(
        default=False,
        validation_alias="ML_SERVICE_ENABLED",
    )
    ml_service_api_key: str = Field(
        default="",
        validation_alias="ML_SERVICE_API_KEY",
    )
    ml_request_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        le=60.0,
        validation_alias="ML_REQUEST_TIMEOUT_SECONDS",
    )
    ml_status_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        le=30.0,
        validation_alias="ML_STATUS_TIMEOUT_SECONDS",
    )

    @field_validator("jwt_algorithm")
    @classmethod
    def require_hs256(cls, value: str) -> str:
        if value != "HS256":
            raise ValueError("JWT_ALGORITHM must be HS256")
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS must contain at least one origin")
        if "*" in origins:
            raise ValueError("Wildcard CORS origins are not allowed")
        return ",".join(origins)

    @model_validator(mode="after")
    def require_production_secret(self) -> "Settings":
        if self.app_env == "production" and (
            len(self.jwt_secret.encode("utf-8")) < 32
            or self.jwt_secret == "replace-with-a-random-secret-of-at-least-32-bytes"
        ):
            raise ValueError("Production requires a unique JWT_SECRET of at least 32 bytes")
        if self.app_env == "production" and self.ml_service_enabled:
            if len(self.ml_service_api_key.encode("utf-8")) < 32:
                raise ValueError(
                    "Production requires ML_SERVICE_API_KEY to be at least 32 bytes "
                    "when ML_SERVICE_ENABLED is true"
                )
            if not self.ml_service_url.startswith("https://"):
                raise ValueError(
                    "Production ML_SERVICE_URL must use HTTPS when "
                    "ML_SERVICE_ENABLED is true"
                )
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
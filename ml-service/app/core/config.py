from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "production"] = Field(
        default="development",
        validation_alias="APP_ENV",
    )
    mongodb_uri: str = Field(
        default="mongodb://localhost:27017",
        validation_alias="MONGODB_URI",
    )
    mongodb_db: str = Field(default="cropshield", validation_alias="MONGODB_DB")
    ml_service_api_key: str = Field(default="", validation_alias="ML_SERVICE_API_KEY")
    ml_service_api_key_previous: str = Field(
        default="",
        validation_alias="ML_SERVICE_API_KEY_PREVIOUS",
    )
    model_dir: Path = Field(default=Path("../models"), validation_alias="MODEL_DIR")
    model_refresh_interval_seconds: int = Field(
        default=60,
        gt=0,
        validation_alias="MODEL_REFRESH_INTERVAL_SECONDS",
    )
    max_request_bytes: int = Field(
        default=1_048_576,
        gt=0,
        validation_alias="MAX_REQUEST_BYTES",
    )
    max_batch_size: int = Field(default=32, gt=0, validation_alias="MAX_BATCH_SIZE")
    max_observations_per_field: int = Field(
        default=180,
        gt=0,
        validation_alias="MAX_OBSERVATIONS_PER_FIELD",
    )
    rate_limit_requests_per_minute: int = Field(
        default=60,
        gt=0,
        validation_alias="RATE_LIMIT_REQUESTS_PER_MINUTE",
    )
    request_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=300.0,
        validation_alias="REQUEST_TIMEOUT_SECONDS",
    )

    @field_validator("mongodb_uri", "mongodb_db")
    @classmethod
    def require_database_setting(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("MongoDB settings must not be empty")
        return value

    @model_validator(mode="after")
    def require_production_api_key(self) -> "Settings":
        if self.app_env == "production" and len(self.ml_service_api_key.encode("utf-8")) < 32:
            raise ValueError("Production requires ML_SERVICE_API_KEY to be at least 32 bytes")
        if self.app_env == "production" and self.ml_service_api_key_previous and len(
            self.ml_service_api_key_previous.encode("utf-8")
        ) < 32:
            raise ValueError("ML_SERVICE_API_KEY_PREVIOUS must be at least 32 bytes")
        if self.app_env == "production" and self.model_dir != Path("models"):
            raise ValueError("Production MODEL_DIR must be the repository-root models directory")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

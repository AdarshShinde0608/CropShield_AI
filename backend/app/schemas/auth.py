from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

Language = Literal["en", "mr", "hi"]
UserRole = Literal["officer", "farmer"]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: SecretStr = Field(min_length=8)
    name: str = Field(min_length=1, max_length=100)
    language: Language = "en"

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: SecretStr

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) > 72:
            raise ValueError("Invalid email or password")
        return value


class UserOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    email: EmailStr
    name: str
    role: UserRole
    language: Language


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserOut


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    language: Language | None = None

    @model_validator(mode="after")
    def require_update_field(self) -> "ProfileUpdateRequest":
        if self.name is None and self.language is None:
            raise ValueError("At least one profile field must be provided")
        return self
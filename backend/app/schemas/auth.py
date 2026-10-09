from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.core.validation import normalize_email


class LoginRequest(BaseModel):
    email: str = Field(max_length=320, examples=["admin@route53.local"])
    password: Annotated[SecretStr, Field(min_length=1, max_length=1024)]

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class AuthUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str


class RegisterRequest(LoginRequest):
    email: str = Field(max_length=320, examples=["user@example.com"])
    display_name: str = Field(max_length=128, examples=["Palak"])
    password: Annotated[SecretStr, Field(min_length=8, max_length=1024)]

    @field_validator("display_name", mode="before")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("Enter your name")
        return value


class LoginResponse(BaseModel):
    user: AuthUserResponse


class LogoutResponse(BaseModel):
    message: str = "Logged out successfully"


class AuthErrorResponse(BaseModel):
    detail: str

from functools import lru_cache
from pathlib import Path

from pydantic import Field, HttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.validation import normalize_email

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Environment values override backend/.env and development defaults."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Route53 Clone API"
    app_env: str = "development"
    database_url: str = "sqlite:///./route53.db"
    frontend_origin: HttpUrl = HttpUrl("http://localhost:3000")
    demo_user_email: str = "admin@route53.local"
    demo_user_password: SecretStr = Field(default=SecretStr("admin123"), min_length=1, max_length=1024)
    demo_user_display_name: str = Field(default="Admin User", min_length=1, max_length=128)
    session_cookie_name: str = Field(default="route53_session", pattern=r"^[A-Za-z0-9_-]+$", max_length=64)
    session_ttl_hours: int = Field(default=24, gt=0, le=8760)
    session_cookie_secure: bool | None = None

    @field_validator("demo_user_email")
    @classmethod
    def validate_demo_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("demo_user_display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def set_cookie_security_default(self) -> "Settings":
        if self.session_cookie_secure is None:
            self.session_cookie_secure = self.app_env.lower() == "production"
        return self

    @field_validator("frontend_origin")
    @classmethod
    def validate_frontend_origin(cls, value: HttpUrl) -> HttpUrl:
        if (
            value.path not in (None, "/")
            or value.query
            or value.fragment
            or value.username
            or value.password
        ):
            raise ValueError("FRONTEND_ORIGIN must contain only scheme, host and port")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

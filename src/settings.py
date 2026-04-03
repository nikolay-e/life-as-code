from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: str
    fernet_key: str

    postgres_user: str = "life_as_code_user"
    postgres_password: str
    postgres_db: str = "life_as_code"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str | None = None

    admin_username: str | None = None
    admin_password: str | None = None

    garmin_email: str | None = None
    garmin_password: str | None = None
    hevy_api_key: str | None = None

    whoop_client_id: str | None = None
    whoop_client_secret: str | None = None

    app_version: str = "dev"
    build_date: str = "unknown"
    vcs_ref: str = "unknown"

    flask_env: str = "development"
    flask_debug: bool = False

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v:
            raise ValueError("secret_key is required")
        return v

    @field_validator("fernet_key")
    @classmethod
    def validate_fernet_key(cls, v: str) -> str:
        if not v:
            raise ValueError("fernet_key is required")
        try:
            Fernet(v.encode())
        except Exception as e:
            raise ValueError(f"Invalid FERNET_KEY: {e}") from None
        return v

    @property
    def computed_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def commit_short(self) -> str:
        return self.vcs_ref[:7] if self.vcs_ref != "unknown" else "unknown"

    @property
    def is_production(self) -> bool:
        return self.flask_env == "production"


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()  # type: ignore[call-arg]


def get_settings_safe() -> AppSettings | None:
    try:
        return get_settings()
    except Exception:
        return None

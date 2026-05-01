from datetime import timedelta, timezone

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DAILY_LOGGING_SIGNALS_DEFAULT = "alcohol,illness,stress,caffeine"


class BotConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    token: str = Field("", validation_alias="TELEGRAM_BOT_TOKEN")
    allowed_users_raw: str = Field("", validation_alias="TELEGRAM_ALLOWED_USERS")
    db_user_id: int = 1
    timezone_offset_hours: int = Field(1, validation_alias="BOT_TIMEZONE_OFFSET_HOURS")
    daily_logging_hour: int = Field(21, validation_alias="BOT_DAILY_LOGGING_HOUR")
    daily_logging_signals_raw: str = Field(
        DAILY_LOGGING_SIGNALS_DEFAULT,
        validation_alias="BOT_DAILY_LOGGING_SIGNALS",
    )

    @property
    def allowed_user_ids(self) -> list[int]:
        if not self.allowed_users_raw:
            return []
        return [int(x.strip()) for x in self.allowed_users_raw.split(",") if x.strip()]

    @property
    def tz(self) -> timezone:
        return timezone(timedelta(hours=self.timezone_offset_hours))

    @property
    def daily_logging_signals(self) -> list[str]:
        return [
            s.strip().lower()
            for s in self.daily_logging_signals_raw.split(",")
            if s.strip()
        ]

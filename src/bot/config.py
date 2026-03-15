import os
from dataclasses import dataclass, field
from datetime import timedelta, timezone


@dataclass
class BotConfig:
    token: str = ""
    allowed_user_ids: list[int] = field(default_factory=list)
    db_user_id: int = 1
    timezone_offset_hours: int = 1

    def __post_init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", self.token)
        allowed = os.getenv("TELEGRAM_ALLOWED_USERS", "")
        if allowed and not self.allowed_user_ids:
            self.allowed_user_ids = [
                int(x.strip()) for x in allowed.split(",") if x.strip()
            ]
        tz_offset = os.getenv("BOT_TIMEZONE_OFFSET_HOURS", "")
        if tz_offset:
            self.timezone_offset_hours = int(tz_offset)

    @property
    def tz(self) -> timezone:
        return timezone(timedelta(hours=self.timezone_offset_hours))

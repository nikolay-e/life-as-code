import datetime
import time

import requests
from sqlalchemy import select

from database import get_db_session_context
from date_utils import utcnow
from eight_sleep_schemas import EightSleepSessionData
from enums import DataSource, DataType
from errors import CredentialsDecryptionError, CredentialsNotFoundError
from logging_config import get_logger
from models import EightSleepSession, UserCredentials
from security import encrypt_data_for_user
from sync_manager import (
    extract_and_parse,
    get_provider_credentials,
    get_sync_date_range,
)

logger = get_logger(__name__)

AUTH_URL = "https://auth-api.8slp.net/v1/tokens"
API_BASE_URL = "https://client-api.8slp.net/v1"
CLIENT_ID = "0894c7f33bb94800a03f1f4df13a4f38"
CLIENT_SECRET = "f0954a3ed5763ba3d06834c73731a32f15f168f47d4f164751275def86db0c76"  # pragma: allowlist secret
REQUEST_TIMEOUT = 30
RATE_LIMIT_DELAY = 0.5
MAX_HISTORY_DAYS = 365
TRENDS_CHUNK_DAYS = 30


class EightSleepAPIClient:
    def __init__(
        self,
        email: str,
        password: str,
        access_token: str | None = None,
        user_id: int | None = None,
    ):
        self._email = email
        self._password = password
        self._access_token = access_token
        self._eight_sleep_user_id: str | None = None
        self._token_expires_at: datetime.datetime | None = None
        self._app_user_id = user_id
        self._session = requests.Session()

    def authenticate(self) -> None:
        response = self._session.post(
            AUTH_URL,
            data={
                "grant_type": "password",
                "username": self._email,
                "password": self._password,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        self._access_token = data["access_token"]
        self._eight_sleep_user_id = data.get("userId")
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = utcnow() + datetime.timedelta(seconds=expires_in)
        self._session.headers["Authorization"] = f"Bearer {self._access_token}"

        if self._app_user_id and self._access_token:
            self._store_token()

        logger.info(
            "eight_sleep_authenticated",
            eight_sleep_user_id=self._eight_sleep_user_id,
        )

    def _store_token(self) -> None:
        if not self._app_user_id or not self._access_token:
            return
        try:
            encrypted_token = encrypt_data_for_user(
                self._access_token, self._app_user_id
            )
            with get_db_session_context() as db:
                creds = db.scalars(
                    select(UserCredentials).where(
                        UserCredentials.user_id == self._app_user_id
                    )
                ).first()
                if creds:
                    creds.encrypted_eight_sleep_access_token = encrypted_token
                    creds.eight_sleep_token_expires_at = self._token_expires_at
        except Exception as e:
            logger.warning("eight_sleep_token_store_failed", error=str(e))

    def _ensure_authenticated(self) -> None:
        if not self._access_token:
            self.authenticate()
            return
        if "Authorization" not in self._session.headers:
            self._session.headers["Authorization"] = f"Bearer {self._access_token}"
        if self._token_expires_at and utcnow() >= self._token_expires_at:
            logger.info("eight_sleep_token_expired_refreshing")
            self.authenticate()

    def _get_user_id(self) -> str:
        if self._eight_sleep_user_id:
            return self._eight_sleep_user_id

        self._ensure_authenticated()
        response = self._session.get(
            f"{API_BASE_URL}/users/me",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        self._eight_sleep_user_id = data.get("userId", data.get("id", ""))
        return self._eight_sleep_user_id  # type: ignore[return-value]

    def get_sleep_trends(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> list[dict]:
        self._ensure_authenticated()
        eight_sleep_user_id = self._get_user_id()

        all_trends: list[dict] = []
        chunk_start = start_date

        while chunk_start <= end_date:
            chunk_end = min(
                chunk_start + datetime.timedelta(days=TRENDS_CHUNK_DAYS),
                end_date,
            )

            logger.info(
                "eight_sleep_fetching_trends",
                start=chunk_start.isoformat(),
                end=chunk_end.isoformat(),
            )

            response = self._session.get(
                f"{API_BASE_URL}/users/{eight_sleep_user_id}/trends",
                params={
                    "from": chunk_start.isoformat(),
                    "to": chunk_end.isoformat(),
                    "tz": "UTC",
                    "include-main": "false",
                    "include-all-sessions": "true",
                    "model-version": "v2",
                },
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list):
                all_trends.extend(data)
            elif isinstance(data, dict) and "days" in data:
                all_trends.extend(data["days"])

            logger.info(
                "eight_sleep_trends_fetched",
                chunk_start=chunk_start.isoformat(),
                chunk_end=chunk_end.isoformat(),
                count=len(data) if isinstance(data, list) else 0,
            )

            chunk_start = chunk_end + datetime.timedelta(days=1)

            if chunk_start <= end_date:
                time.sleep(RATE_LIMIT_DELAY)

        logger.info("eight_sleep_fetch_complete", total_nights=len(all_trends))
        return all_trends

    def close(self) -> None:
        self._session.close()


def sync_eight_sleep_data_for_user(
    user_id: int, days: int = 90, full_sync: bool = False
) -> dict:
    try:
        creds = get_provider_credentials(user_id, DataSource.EIGHT_SLEEP)
    except (CredentialsNotFoundError, CredentialsDecryptionError) as e:
        logger.error("eight_sleep_credentials_error", user_id=user_id, error=str(e))
        return {"error": str(e), "user_id": user_id}

    if not creds.eight_sleep_email or not creds.eight_sleep_password:
        return {"error": "Eight Sleep credentials not configured", "user_id": user_id}

    try:
        api_client = EightSleepAPIClient(
            email=creds.eight_sleep_email,
            password=creds.eight_sleep_password,
            access_token=creds.eight_sleep_access_token,
            user_id=user_id,
        )

        date_range = get_sync_date_range(
            days, full_sync, max_history_days=MAX_HISTORY_DAYS
        )

        logger.info(
            "eight_sleep_sync_started",
            user_id=user_id,
            sync_type=date_range.sync_type,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
            full_sync=full_sync,
        )

        sync_result = extract_and_parse(
            api_call_func=lambda: api_client.get_sleep_trends(
                start_date=date_range.start_date,
                end_date=date_range.end_date,
            ),
            parser_class=EightSleepSessionData,
            model_class=EightSleepSession,
            unique_fields=["date", "source"],
            user_id=user_id,
            source=DataSource.EIGHT_SLEEP,
            data_type=DataType.SLEEP,
        )

        summary = {
            "user_id": user_id,
            "sync_date": utcnow().isoformat(),
            "sync_type": date_range.sync_type,
            "source": "eight_sleep",
            "data_type": "sleep",
            "success": sync_result.success,
            "records_processed": sync_result.records_processed,
            "records_created": sync_result.records_created,
            "records_updated": sync_result.records_updated,
            "records_skipped": sync_result.records_skipped,
            "errors": sync_result.errors[:5],
            "error_count": len(sync_result.errors),
        }

        logger.info(
            "eight_sleep_sync_completed",
            user_id=user_id,
            records_processed=summary["records_processed"],
            records_created=summary["records_created"],
            success=summary["success"],
        )
        return summary

    except Exception as e:
        logger.error("eight_sleep_sync_failed", user_id=user_id, error=str(e))
        return {"error": str(e), "user_id": user_id}


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
        full_sync = "--full" in sys.argv

        result = sync_eight_sleep_data_for_user(user_id, days, full_sync=full_sync)
        print(f"Sync result: {result}")
    else:
        print("Usage: python pull_eight_sleep_data.py <user_id> [days] [--full]")

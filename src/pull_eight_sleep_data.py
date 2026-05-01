import datetime
import time

import requests
from sqlalchemy import select

from database import get_db_session_context
from date_utils import parse_iso_date, utcnow
from eight_sleep_schemas import EightSleepSessionData
from enums import DataSource, DataType
from errors import CredentialsDecryptionError, CredentialsNotFoundError
from logging_config import get_logger
from models import HRV, EightSleepSession, HeartRate, Sleep, UserCredentials
from security import encrypt_data_for_user
from sync_manager import (
    extract_and_parse,
    get_provider_credentials,
    get_sync_date_range,
    upsert_data,
)

logger = get_logger(__name__)

AUTH_URL = "https://auth-api.8slp.net/v1/tokens"
API_BASE_URL = "https://client-api.8slp.net/v1"
# Sleep Fitness / Quality / Routine scores live on a different host than /trends.
# Verified live 2026-04-29: GET app-api.8slp.net/v1/users/{id}/metrics/summary?metrics=all
# returns {"days": [{"date": "...", "metrics": [{"name": "sfs", "value": "93"}, ...]}]}.
# Also confirmed by mikeg0/eightctl audit (2026-03-15).
METRICS_BASE_URL = "https://app-api.8slp.net/v1"
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
        token_expires_at: datetime.datetime | None = None,
    ):
        self._email = email
        self._password = password
        self._access_token = access_token
        self._eight_sleep_user_id: str | None = None
        self._token_expires_at = token_expires_at
        self._app_user_id = user_id
        self._session = requests.Session()

    def authenticate(self) -> None:
        # Eight Sleep's /v1/tokens rejects requests that carry BOTH a Bearer
        # token and client credentials in the body with HTTP 400
        # "duplicate client credentials". When re-authenticating after token
        # expiry or 401, the stale Authorization header is still on the
        # session — drop it before sending fresh credentials.
        self._session.headers.pop("Authorization", None)
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
        if not response.ok:
            logger.error(
                "eight_sleep_auth_failed",
                status=response.status_code,
                body=response.text[:500],
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

    def _request_with_reauth(
        self, method: str, url: str, **kwargs
    ) -> requests.Response:
        self._ensure_authenticated()
        response = self._session.request(method, url, **kwargs)
        if response.status_code == 401:
            logger.info("eight_sleep_token_rejected_reauthenticating")
            self.authenticate()
            response = self._session.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    def _get_user_id(self) -> str:
        if self._eight_sleep_user_id:
            return self._eight_sleep_user_id

        response = self._request_with_reauth(
            "GET",
            f"{API_BASE_URL}/users/me",
            timeout=REQUEST_TIMEOUT,
        )
        data = response.json()

        user_data = data.get("user", data) if isinstance(data, dict) else data
        user_id = (
            user_data.get("userId")
            or user_data.get("id")
            or data.get("userId")
            or data.get("id")
        )

        if not user_id:
            logger.error(
                "eight_sleep_user_id_not_found",
                response_keys=(
                    list(data.keys()) if isinstance(data, dict) else type(data).__name__
                ),
            )
            raise ValueError("Eight Sleep user ID not found in /users/me response")

        self._eight_sleep_user_id = str(user_id)
        return self._eight_sleep_user_id

    def get_sleep_trends(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> list[dict]:
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

            response = self._request_with_reauth(
                "GET",
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

    @staticmethod
    def _parse_metrics_day(day: dict) -> tuple[str, dict[str, str]] | None:
        date_iso = day.get("date")
        metrics_list = day.get("metrics")
        if not date_iso or not isinstance(metrics_list, list):
            return None
        metrics_map: dict[str, str] = {}
        for entry in metrics_list:
            if isinstance(entry, dict) and "name" in entry and "value" in entry:
                metrics_map[str(entry["name"])] = str(entry["value"])
        if not metrics_map:
            return None
        return str(date_iso), metrics_map

    def _request_metrics_summary(
        self,
        eight_sleep_user_id: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> dict | None:
        try:
            response = self._request_with_reauth(
                "GET",
                f"{METRICS_BASE_URL}/users/{eight_sleep_user_id}/metrics/summary",
                params={
                    "from": start_date.isoformat(),
                    "to": end_date.isoformat(),
                    "metrics": "all",
                    "tz": "UTC",
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            detail = exc.response.text[:200] if exc.response is not None else None
            logger.warning(
                "eight_sleep_metrics_summary_failed",
                status=status,
                detail=detail,
            )
            return None
        data = response.json()
        return data if isinstance(data, dict) else None

    def get_metrics_summary(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> dict[str, dict[str, str]]:
        """Fetch daily Sleep Fitness / Quality / Routine scores from app-api.

        Eight Sleep's /trends endpoint on client-api does NOT carry sleepFitnessScore.
        The mobile app reads it from app-api.8slp.net/v1/users/<id>/metrics/summary,
        which returns {"days": [{"date": "YYYY-MM-DD", "metrics": [
            {"name": "sfs",   "value": "93"},
            {"name": "sqs",   "value": "90"},
            {"name": "srs",   "value": "96"},
            ... ]}]}.

        Returns: {date_iso: {metric_name: str_value}} keyed by ISO date.
        Empty dict on auth/permission failure (logged, non-fatal — caller falls
        back to whatever /trends provided).
        """
        eight_sleep_user_id = self._get_user_id()
        data = self._request_metrics_summary(eight_sleep_user_id, start_date, end_date)
        if data is None:
            return {}
        days = data.get("days")
        if not isinstance(days, list):
            return {}
        out = self._collect_metrics_days(days)
        logger.info("eight_sleep_metrics_summary_fetched", days=len(out))
        return out

    @classmethod
    def _collect_metrics_days(cls, days: list) -> dict[str, dict[str, str]]:
        out: dict[str, dict[str, str]] = {}
        for day in days:
            if not isinstance(day, dict):
                continue
            parsed = cls._parse_metrics_day(day)
            if parsed is None:
                continue
            date_iso, metrics_map = parsed
            out[date_iso] = metrics_map
        return out

    def close(self) -> None:
        self._session.close()


def _write_eight_sleep_normalized(
    user_id: int,
    start_date: datetime.date | None,
    end_date: datetime.date,
) -> None:
    with get_db_session_context() as db:
        query = select(EightSleepSession).where(
            EightSleepSession.user_id == user_id,
            EightSleepSession.date <= end_date,
        )
        if start_date:
            query = query.where(EightSleepSession.date >= start_date)

        for ses in db.scalars(query):
            if ses.hrv is not None:
                upsert_data(
                    db,
                    HRV,
                    {"date": ses.date, "source": "eight_sleep", "hrv_avg": ses.hrv},
                    ["date", "source"],
                    user_id,
                )
            if ses.heart_rate is not None:
                upsert_data(
                    db,
                    HeartRate,
                    {
                        "date": ses.date,
                        "source": "eight_sleep",
                        "resting_hr": int(ses.heart_rate),
                    },
                    ["date", "source"],
                    user_id,
                )

            def _sec_to_min(seconds):
                return round(seconds / 60.0, 1) if seconds is not None else None

            sleep_data = {
                "date": ses.date,
                "source": "eight_sleep",
                "total_sleep_minutes": _sec_to_min(ses.sleep_duration_seconds),
                "deep_minutes": _sec_to_min(ses.deep_duration_seconds),
                "light_minutes": _sec_to_min(ses.light_duration_seconds),
                "rem_minutes": _sec_to_min(ses.rem_duration_seconds),
                "respiratory_rate": ses.respiratory_rate,
                "sleep_score": ses.score,
                "sleep_start_time": ses.sleep_start_time,
                "sleep_end_time": ses.sleep_end_time,
            }
            if sleep_data["total_sleep_minutes"] is not None:
                upsert_data(db, Sleep, sleep_data, ["date", "source"], user_id)

        db.commit()
        logger.info("eight_sleep_normalized_write_complete", user_id=user_id)


def _safe_int_score(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _apply_scores_to_row(
    row: EightSleepSession, sfs: int | None, sqs: int | None, srs: int | None
) -> None:
    if sfs is not None:
        row.sleep_fitness_score = sfs
    if sqs is not None:
        row.sleep_quality_score = sqs
    if srs is not None:
        row.sleep_routine_score = srs


def _apply_day_scores(db, user_id: int, date_iso: str, metrics: dict[str, str]) -> bool:
    try:
        session_date = parse_iso_date(date_iso)
    except (ValueError, TypeError):
        return False

    sfs = _safe_int_score(metrics.get("sfs"))
    sqs = _safe_int_score(metrics.get("sqs"))
    srs = _safe_int_score(metrics.get("srs"))
    if sfs is None and sqs is None and srs is None:
        return False

    row = db.scalars(
        select(EightSleepSession).where(
            EightSleepSession.user_id == user_id,
            EightSleepSession.date == session_date,
        )
    ).first()
    if row is None:
        return False

    _apply_scores_to_row(row, sfs, sqs, srs)
    return True


def _apply_metrics_summary_to_sessions(
    user_id: int, metrics_by_date: dict[str, dict[str, str]]
) -> None:
    """Backfill sleep_fitness_score / sleep_routine_score / sleep_quality_score
    on existing eight_sleep_sessions rows from the metrics/summary endpoint.

    metrics_by_date keys are ISO date strings; values are {"sfs": "93", ...}.
    Only writes when the row exists (so trends sync remains the source of truth
    for non-score columns) and only when the new value is non-null.
    """
    if not metrics_by_date:
        return

    updated = 0
    with get_db_session_context() as db:
        for date_iso, metrics in metrics_by_date.items():
            if _apply_day_scores(db, user_id, date_iso, metrics):
                updated += 1

    logger.info(
        "eight_sleep_metrics_summary_applied", user_id=user_id, sessions_updated=updated
    )


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
            token_expires_at=creds.eight_sleep_token_expires_at,
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

        # Backfill the score columns from the metrics/summary endpoint, which
        # is the only place sfs/sqs/srs are exposed (see METRICS_BASE_URL note).
        # Non-fatal: if the endpoint fails or returns empty, the trends sync
        # above still landed everything else.
        if sync_result.success:
            try:
                metrics_by_date = api_client.get_metrics_summary(
                    start_date=date_range.start_date,
                    end_date=date_range.end_date,
                )
                if metrics_by_date:
                    _apply_metrics_summary_to_sessions(user_id, metrics_by_date)
            except Exception:
                logger.exception(
                    "eight_sleep_metrics_summary_apply_failed", user_id=user_id
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

        if summary["success"]:
            try:
                _write_eight_sleep_normalized(
                    user_id, date_range.start_date, date_range.end_date
                )
            except Exception:
                logger.exception("eight_sleep_normalized_write_failed", user_id=user_id)

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

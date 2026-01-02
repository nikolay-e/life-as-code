import time
from typing import Any

import requests
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RATE_LIMIT_DELAY = 0.5


class RateLimitError(Exception):
    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limited, retry after {retry_after}s")


class AuthenticationError(Exception):
    pass


def log_retry_attempt(retry_state: RetryCallState) -> None:
    if retry_state.attempt_number > 1:
        logger.warning(
            "http_request_retry",
            attempt=retry_state.attempt_number,
            exception=(
                str(retry_state.outcome.exception()) if retry_state.outcome else None
            ),
        )


class HTTPClient:
    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        rate_limit_delay: float = DEFAULT_RATE_LIMIT_DELAY,
    ):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _build_url(self, endpoint: str) -> str:
        endpoint = endpoint.lstrip("/")
        return f"{self.base_url}/{endpoint}"

    def _handle_response(self, response: requests.Response) -> dict | list | None:
        if response.status_code == 200:
            result: dict | list = response.json()
            return result

        if response.status_code == 401:
            raise AuthenticationError(f"Authentication failed: {response.status_code}")

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            raise RateLimitError(retry_after)

        if response.status_code == 404:
            return None

        logger.error(
            "http_request_failed",
            status_code=response.status_code,
            response_text=response.text[:200],
        )
        response.raise_for_status()
        return None

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict | list | None:
        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type((requests.RequestException, RateLimitError)),
            before_sleep=log_retry_attempt,
            reraise=True,
        )
        def _do_request() -> dict | list | None:
            headers = {**self.headers, **(extra_headers or {})}
            response = self.session.get(
                self._build_url(endpoint),
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            return self._handle_response(response)

        try:
            result: dict | list | None = _do_request()
            return result
        except RateLimitError as e:
            logger.warning("http_rate_limited", retry_after=e.retry_after)
            time.sleep(e.retry_after)
            result = _do_request()
            return result

    def post(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict | list | None:
        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type(requests.RequestException),
            before_sleep=log_retry_attempt,
            reraise=True,
        )
        def _do_request() -> dict | list | None:
            headers = {**self.headers, **(extra_headers or {})}
            response = self.session.post(
                self._build_url(endpoint),
                data=data,
                json=json_data,
                headers=headers,
                timeout=self.timeout,
            )
            return self._handle_response(response)

        result: dict | list | None = _do_request()
        return result

    def get_with_rate_limit(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict | list | None:
        result = self.get(endpoint, params)
        if self.rate_limit_delay > 0:
            time.sleep(self.rate_limit_delay)
        return result

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "HTTPClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

import logging
import time

import anthropic

logger = logging.getLogger(__name__)


def create_with_retry(
    client: anthropic.Anthropic,
    max_retries: int = 3,
    **kwargs,
) -> anthropic.types.Message:
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return client.messages.create(**kwargs)
        except anthropic.RateLimitError as e:
            last_error = e
            wait = min(2**attempt * 2, 30)
            logger.warning("rate_limited attempt=%d wait=%ds", attempt, wait)
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                last_error = e
                wait = min(2**attempt, 10)
                logger.warning(
                    "server_error=%d attempt=%d wait=%ds",
                    e.status_code,
                    attempt,
                    wait,
                )
                time.sleep(wait)
            else:
                raise
        except anthropic.APIConnectionError as e:
            last_error = e
            wait = min(2**attempt, 10)
            logger.warning("connection_error attempt=%d wait=%ds", attempt, wait)
            time.sleep(wait)
    raise last_error  # type: ignore[misc]

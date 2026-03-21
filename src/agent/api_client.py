import logging

import anthropic
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)


def _is_retryable(error: BaseException) -> bool:
    if isinstance(error, (anthropic.RateLimitError, anthropic.APIConnectionError)):
        return True
    if isinstance(error, anthropic.APIStatusError) and error.status_code >= 500:
        return True
    return False


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential_jitter(initial=2, max=30),
    retry=retry_if_exception(_is_retryable),
    reraise=True,
    before_sleep=lambda rs: logger.warning(
        "retry attempt=%d error=%s", rs.attempt_number, rs.outcome.exception()
    ),
)
def create_with_retry(
    client: anthropic.Anthropic,
    **kwargs,
) -> anthropic.types.Message:
    return client.messages.create(**kwargs)

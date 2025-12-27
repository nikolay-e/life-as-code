import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["5000 per hour"],
    storage_uri=REDIS_URL,
    storage_options={"socket_connect_timeout": 3, "socket_timeout": 3},
    strategy="fixed-window",
    in_memory_fallback_enabled=True,
)

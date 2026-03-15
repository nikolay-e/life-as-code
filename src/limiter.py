import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

STORAGE_URI = os.getenv("REDIS_URL", "memory://")

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["5000 per hour"],
    storage_uri=STORAGE_URI,
    strategy="fixed-window",
)

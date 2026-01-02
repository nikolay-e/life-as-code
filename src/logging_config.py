import logging
import os
import re
import socket
import sys
import time
import uuid
from collections.abc import MutableMapping
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, cast

import structlog
from structlog.typing import Processor, WrappedLogger

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.engine import Engine

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)

APP_NAME = "life-as-code"
HOSTNAME = socket.gethostname()

SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "api_key",
        "apikey",
        "token",
        "access_token",
        "refresh_token",
        "auth",
        "authorization",
        "bearer",
        "private_key",
        "credential",
        "credentials",
        "session_id",
        "cookie",
        "csrf",
        "state",
        "code",
        "fernet",
        "encryption_key",
        "client_secret",
    }
)

SENSITIVE_PATTERNS = [
    (
        re.compile(r"password\s*[:=]\s*['\"]?[^'\"\s]+", re.IGNORECASE),
        "[PASSWORD_REDACTED]",
    ),
    (re.compile(r"token\s*[:=]\s*['\"]?[^'\"\s]+", re.IGNORECASE), "[TOKEN_REDACTED]"),
    (
        re.compile(r"api[_-]?key\s*[:=]\s*['\"]?[^'\"\s]+", re.IGNORECASE),
        "[API_KEY_REDACTED]",
    ),
    (
        re.compile(
            r"Bearer\s+[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+", re.IGNORECASE
        ),
        "[BEARER_TOKEN_REDACTED]",
    ),
]


def _is_sensitive_key(key: str) -> bool:
    key_lower = key.lower()
    return any(sensitive in key_lower for sensitive in SENSITIVE_KEYS)


def _redact_value(value: Any, key: str | None = None) -> Any:
    if key and _is_sensitive_key(key):
        if isinstance(value, str) and len(value) > 0:
            return "[REDACTED]"
        if isinstance(value, (int, float)) and value != 0:
            return "[REDACTED]"
        return value

    if isinstance(value, str):
        for pattern, replacement in SENSITIVE_PATTERNS:
            value = pattern.sub(replacement, value)
        return value

    if isinstance(value, dict):
        return {k: _redact_value(v, k) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return type(value)(_redact_value(item) for item in value)

    return value


def redact_sensitive_data(
    _logger: WrappedLogger, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in list(event_dict.keys()):
        if key in ("timestamp", "level", "logger", "service", "request_id", "event"):
            continue
        event_dict[key] = _redact_value(event_dict[key], key)
    return event_dict


def add_request_id(
    _logger: WrappedLogger, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    request_id = request_id_var.get()
    if request_id:
        event_dict["request_id"] = request_id
    user_id = user_id_var.get()
    if user_id:
        event_dict["user_id"] = user_id
    return event_dict


def add_app_context(
    _logger: WrappedLogger, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    from settings import get_settings_safe

    s = get_settings_safe()
    event_dict["service"] = APP_NAME
    event_dict["version"] = s.app_version if s else "unknown"
    event_dict["commit"] = s.commit_short if s else "unknown"
    event_dict["environment"] = os.getenv("FLASK_ENV", "development")
    event_dict["hostname"] = HOSTNAME
    return event_dict


def configure_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "console")
    is_production = os.getenv("FLASK_ENV", "production") == "production"

    renderer: Processor
    if log_format == "json" or is_production:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    # Build processor chain - use dict_tracebacks for JSON (structured exceptions)
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        add_app_context,
        add_request_id,
        redact_sensitive_data,
    ]

    # Add structured exception formatting for JSON logs (better for log aggregation)
    if log_format == "json" or is_production:
        processors.append(structlog.processors.dict_tracebacks)

    processors.append(renderer)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level),
        force=True,
    )

    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.orm").setLevel(logging.WARNING)
    logging.getLogger("garminconnect").setLevel(logging.WARNING)
    logging.getLogger("garth").setLevel(logging.WARNING)
    logging.getLogger("dash").setLevel(logging.WARNING)
    logging.getLogger("flask_limiter").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


def set_log_level(level: str) -> bool:
    level_upper = level.upper()
    if level_upper not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        return False
    numeric_level = getattr(logging, level_upper)
    logging.getLogger().setLevel(numeric_level)
    get_logger("logging_config").info("log_level_changed", new_level=level_upper)
    return True


def get_current_log_level() -> str:
    return logging.getLevelName(logging.getLogger().level)


def init_request_logging(app: "Flask") -> None:
    from flask import g, request
    from flask_login import current_user

    @app.before_request
    def set_request_id():
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
        request_id_var.set(req_id)
        g.request_id = req_id
        g.request_start_time = time.time()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=req_id,
            path=request.path,
            method=request.method,
        )

        if hasattr(current_user, "id") and current_user.is_authenticated:
            user_id_var.set(current_user.id)
            structlog.contextvars.bind_contextvars(user_id=current_user.id)

    @app.after_request
    def log_request(response):
        excluded_paths = (
            "/health",
            "/dashboard/_dash",
            "/assets/",
            "/static/",
            "/favicon.ico",
        )
        if any(request.path.startswith(p) for p in excluded_paths):
            return response

        logger = get_logger("http")
        duration_ms = None
        if hasattr(g, "request_start_time"):
            duration_ms = round((time.time() - g.request_start_time) * 1000, 2)

        log_data = {
            "status_code": response.status_code,
            "content_length": response.content_length,
        }
        if duration_ms is not None:
            log_data["duration_ms"] = duration_ms

        if response.status_code >= 500:
            logger.error("request_failed", **log_data)
        elif response.status_code >= 400:
            logger.warning("request_client_error", **log_data)
        else:
            logger.info("request_completed", **log_data)

        return response


SLOW_QUERY_THRESHOLD_MS = float(os.getenv("SLOW_QUERY_THRESHOLD_MS", "500"))


def init_slow_query_logging(engine: "Engine") -> None:
    from sqlalchemy import event

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, _cursor, _stmt, _params, _context, _executemany):
        conn.info.setdefault("query_start_time", []).append(time.time())

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, _cursor, statement, _params, _context, _executemany):
        start_times = conn.info.get("query_start_time", [])
        if not start_times:
            return
        total_time_ms = (time.time() - start_times.pop()) * 1000
        if total_time_ms > SLOW_QUERY_THRESHOLD_MS:
            logger = get_logger("database.slow_query")
            statement_preview = statement[:500] if statement else ""
            logger.warning(
                "slow_query_detected",
                duration_ms=round(total_time_ms, 2),
                statement_preview=statement_preview,
                threshold_ms=SLOW_QUERY_THRESHOLD_MS,
            )


def init_db_event_logging(engine: "Engine") -> None:
    from sqlalchemy import event

    logger = get_logger("database.pool")

    @event.listens_for(engine, "connect")
    def on_connect(_dbapi_conn, _conn_record):
        logger.debug("connection_created")

    @event.listens_for(engine, "checkout")
    def on_checkout(_dbapi_conn, _conn_record, _conn_proxy):
        logger.debug(
            "connection_checkout",
            pool_size=engine.pool.size(),
            checked_out=engine.pool.checkedout(),
        )

    @event.listens_for(engine, "checkin")
    def on_checkin(_dbapi_conn, _conn_record):
        logger.debug("connection_returned")

    @event.listens_for(engine, "invalidate")
    def on_invalidate(_dbapi_conn, _conn_record, exception):
        logger.warning(
            "connection_invalidated",
            error_type=type(exception).__name__ if exception else None,
        )

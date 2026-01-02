import os

from flask import Flask, jsonify, request
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import select
from werkzeug.middleware.proxy_fix import ProxyFix

from api import api
from database import SessionLocal, check_db_connection, init_db
from errors import APIError
from limiter import limiter
from logging_config import configure_logging, get_logger, init_request_logging
from migrations_init import init_migrate
from models import User
from routes import UserModel, register_routes
from settings import get_settings

configure_logging()
logger = get_logger(__name__)

_settings = get_settings()
logger.info(
    "app_startup",
    version=_settings.app_version,
    build_date=_settings.build_date,
    commit=_settings.commit_short,
)


def _validate_required_env_vars():
    missing = []
    if not os.getenv("SECRET_KEY"):
        missing.append("SECRET_KEY")
    if not os.getenv("FERNET_KEY"):
        missing.append("FERNET_KEY")
    if missing:
        raise ValueError(
            f"Required environment variables not set: {', '.join(missing)}. "
            "Please set them in your .env file."
        )


_validate_required_env_vars()

server = Flask(__name__)

# ProxyFix middleware for handling reverse proxy headers (Traefik, nginx)
# x_for=1: Trust 1 level of X-Forwarded-For (fixes request.remote_addr)
# x_proto=1: Trust X-Forwarded-Proto (fixes request.scheme for HTTPS detection)
# x_host=1: Trust X-Forwarded-Host (fixes request.host)
# x_prefix=1: Trust X-Forwarded-Prefix (fixes URL generation)
server.wsgi_app = ProxyFix(server.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)  # type: ignore[method-assign]

server.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
server.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max request size

# Security: Session cookie configuration
server.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV") == "production"
server.config["SESSION_COOKIE_HTTPONLY"] = True
server.config["SESSION_COOKIE_SAMESITE"] = "Lax"
server.config["PERMANENT_SESSION_LIFETIME"] = 1800  # 30 minutes

# Initialize Flask-Migrate for database migrations
init_migrate(server)


def _cleanup_orphaned_syncs():
    from enums import SyncStatus
    from models import DataSync

    try:
        with SessionLocal() as db:
            orphaned = (
                db.query(DataSync)
                .filter(DataSync.status == SyncStatus.IN_PROGRESS)
                .all()
            )
            if orphaned:
                for sync in orphaned:
                    sync.status = SyncStatus.ERROR
                    sync.error_message = "Sync interrupted by application restart"
                db.commit()
                logger.info("orphaned_syncs_cleaned", count=len(orphaned))
    except Exception as e:
        logger.error("orphaned_syncs_cleanup_error", error=str(e))


# Initialize database
logger.info("Initializing database...")
if check_db_connection():
    init_db()
    logger.info("Database ready")
    _cleanup_orphaned_syncs()
else:
    logger.error("Database connection failed")
    exit(1)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access the dashboard."

# Initialize Flask-Limiter for rate limiting
limiter.init_app(server)

# CSRF Protection
server.config["WTF_CSRF_CHECK_DEFAULT"] = False
csrf = CSRFProtect(server)


@server.before_request
def csrf_protect():
    # Skip CSRF for API routes (already handled by blueprint exemption)
    if request.path.startswith("/api/"):
        return None
    # Skip CSRF for GET, HEAD, OPTIONS, TRACE
    if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
        return None
    # Apply CSRF protection for other routes
    csrf.protect()


# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    from database import get_db_session_context

    with get_db_session_context() as db:
        user = db.scalars(select(User).filter_by(id=int(user_id))).first()
        if user:
            return UserModel(user.id, user.username)
        return None


# Health check endpoint for Kubernetes probes
@server.route("/health")
@limiter.exempt
def health():
    try:
        # Check database connection
        with SessionLocal() as db:
            from sqlalchemy import text

            db.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "version": _settings.app_version,
            "build_date": _settings.build_date,
            "commit": _settings.commit_short,
            "database": "connected",
        }, 200
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "version": _settings.app_version,
            "error": str(e),
        }, 503


# Initialize request logging with correlation IDs
init_request_logging(server)


# Security headers middleware
@server.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if os.getenv("FLASK_ENV") == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response


def _create_problem_response(
    error_type: str,
    title: str,
    status: int,
    detail: str | None = None,
    extra: dict | None = None,
):
    problem = {
        "type": f"https://api.life-as-code/problems/{error_type}",
        "title": title,
        "status": status,
        "instance": request.path,
    }
    if detail:
        problem["detail"] = detail
    if extra:
        problem.update(extra)
    response = jsonify(problem)
    response.status_code = status
    response.headers["Content-Type"] = "application/problem+json"
    return response


@server.errorhandler(APIError)
def handle_api_error(error: APIError):
    logger.error(
        "api_error",
        code=error.code.value,
        category=error.category.value,
        status=error.status,
        detail=error.detail,
        path=request.path,
    )
    response = jsonify(error.to_problem_detail(instance=request.path))
    response.status_code = error.status
    response.headers["Content-Type"] = "application/problem+json"
    return response


@server.errorhandler(404)
def not_found_error(error):
    logger.warning("not_found", path=request.path, method=request.method)
    return _create_problem_response(
        error_type="not-found",
        title="Not Found",
        status=404,
        detail=f"The requested resource '{request.path}' was not found",
    )


@server.errorhandler(500)
def internal_error(error):
    logger.exception("internal_server_error", path=request.path, method=request.method)
    return _create_problem_response(
        error_type="internal-error",
        title="Internal Server Error",
        status=500,
        detail="An unexpected error occurred",
    )


@server.errorhandler(429)
def ratelimit_handler(error):
    logger.warning(
        "rate_limit_exceeded",
        path=request.path,
        ip=request.remote_addr,
        limit=str(error.description),
    )
    return _create_problem_response(
        error_type="rate-limit-exceeded",
        title="Too Many Requests",
        status=429,
        detail="Rate limit exceeded. Please try again later.",
        extra={"retry_after": 60},
    )


# Register Flask routes
register_routes(server, limiter)

# Register API blueprint for React frontend
server.register_blueprint(api)
csrf.exempt(api)

# Export app for gunicorn
app = server

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    # nosemgrep: python.flask.security.audit.app-run-param-config.avoid_app_run_with_bad_host
    server.run(
        host="0.0.0.0",  # nosec B104 - Required for Docker
        port=8080,
        debug=debug_mode,
    )

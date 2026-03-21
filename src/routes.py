import datetime
import os
import secrets

import requests
from flask import flash, redirect, render_template_string, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired

from database import get_db_session_context
from date_utils import utcnow
from logging_config import get_logger
from models import User, UserCredentials
from security import encrypt_data_for_user, verify_password

logger = get_logger(__name__)

SETTINGS_REDIRECT = "/dashboard/settings"


class UserModel:
    """User model for Flask-Login compatibility."""

    def __init__(self, user_id: int, username: str):
        self.id = user_id
        self.username = username

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


def _authenticate_user(form):
    with get_db_session_context() as db:
        user = db.scalars(select(User).filter_by(username=form.username.data)).first()
        if (
            user
            and form.password.data
            and verify_password(form.password.data, user.password_hash)
        ):
            user_model = UserModel(user.id, user.username)
            login_user(user_model)
            logger.info(
                "login_success",
                username=form.username.data,
                user_id=user.id,
            )
            return redirect("/dashboard/")
        logger.warning(
            "login_failed",
            username=form.username.data,
            reason="invalid_credentials",
            ip=request.remote_addr,
        )
        flash("Invalid username or password")
    return None


def _render_login_page(form):
    # nosemgrep: python.flask.security.audit.render-template-string.render-template-string
    return render_template_string(
        """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Life-as-Code - Login</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                   background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                   height: 100vh; margin: 0; display: flex; align-items: center; justify-content: center; }
            .login-container { background: white; padding: 2rem; border-radius: 10px;
                              box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 400px; max-width: 90%; }
            .logo { text-align: center; margin-bottom: 2rem; }
            .logo h1 { color: #333; margin: 0; }
            .logo p { color: #666; margin: 5px 0 0 0; }
            .form-group { margin-bottom: 1rem; }
            .form-group label { display: block; margin-bottom: 5px; font-weight: bold; color: #333; }
            .form-group input { width: 100%; padding: 12px; border: 1px solid #ddd;
                               border-radius: 5px; font-size: 16px; box-sizing: border-box; }
            .btn { background: #667eea; color: white; border: none; padding: 12px 24px;
                   border-radius: 5px; cursor: pointer; width: 100%; font-size: 16px; }
            .btn:hover { background: #5a6fd8; }
            .alert { background: #f8d7da; color: #721c24; padding: 10px;
                     border-radius: 5px; margin-bottom: 1rem; }
            .footer { text-align: center; margin-top: 2rem; color: #666; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="logo">
                <h1>🏥 Life-as-Code</h1>
                <p>Health Analytics Portal</p>
            </div>

            {% with messages = get_flashed_messages() %}
                {% if messages %}
                    <div class="alert">{{ messages[0] }}</div>
                {% endif %}
            {% endwith %}

            <form method="post">
                {{ form.hidden_tag() }}
                <div class="form-group">
                    {{ form.username.label(class="") }}
                    {{ form.username(class="", required=True) }}
                </div>
                <div class="form-group">
                    {{ form.password.label(class="") }}
                    {{ form.password(class="", required=True) }}
                </div>
                <button type="submit" class="btn">Login</button>
            </form>

            <div class="footer">
                <p>Contact your administrator for account access.</p>
            </div>
        </div>
    </body>
    </html>
    """,
        form=form,
    )


def _build_whoop_auth_url(client_id, redirect_uri, state):
    from urllib.parse import quote

    scope = quote("offline read:recovery read:sleep read:workout read:cycles")
    return (
        f"https://api.prod.whoop.com/oauth/oauth2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri={quote(redirect_uri)}"
        f"&response_type=code"
        f"&scope={scope}"
        f"&state={state}"
    )


def _validate_whoop_callback_state(state):
    import time

    stored_state = session.pop("whoop_oauth_state", None)
    state_ts = session.pop("whoop_oauth_state_ts", None)
    if not state or state != stored_state:
        logger.error(
            "whoop_oauth_state_mismatch",
            has_received_state=bool(state),
            has_stored_state=bool(stored_state),
        )
        flash("Invalid OAuth state - please try again")
        return False
    if state_ts and (time.time() - state_ts) > 300:
        logger.error("whoop_oauth_state_expired")
        flash("OAuth session expired - please try again")
        return False
    return True


def _exchange_whoop_token(code, client_id, client_secret, redirect_uri):
    logger.info("whoop_token_exchange_started")
    response = requests.post(
        "https://api.prod.whoop.com/oauth/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    if response.status_code != 200:
        logger.error(
            "whoop_token_exchange_failed",
            status_code=response.status_code,
        )
        return None
    tokens = response.json()
    logger.info(
        "whoop_token_exchange_successful",
        expires_in=tokens.get("expires_in"),
    )
    return tokens


def _save_whoop_tokens(tokens):
    with get_db_session_context() as db:
        creds = db.scalars(
            select(UserCredentials).where(UserCredentials.user_id == current_user.id)
        ).first()

        if not creds:
            logger.info("creating_new_user_credentials")
            creds = UserCredentials(user_id=current_user.id)
            db.add(creds)

        encrypted_token = encrypt_data_for_user(tokens["access_token"], current_user.id)
        encrypted_refresh = encrypt_data_for_user(
            tokens["refresh_token"], current_user.id
        )

        logger.info(
            "whoop_credentials_encrypted",
            has_access_token=bool(encrypted_token),
            has_refresh_token=bool(encrypted_refresh),
        )

        creds.encrypted_whoop_access_token = encrypted_token
        creds.encrypted_whoop_refresh_token = encrypted_refresh
        creds.whoop_token_expires_at = utcnow() + datetime.timedelta(
            seconds=tokens.get("expires_in", 3600)
        )

        db.commit()
        logger.info("whoop_credentials_saved")


def _login_handler(form: "LoginForm"):
    if form.validate_on_submit():
        try:
            result = _authenticate_user(form)
            if result is not None:
                return result
        except Exception as e:
            logger.exception("login_error", username=form.username.data, error=str(e))
            flash("An error occurred during login")
    return _render_login_page(form)


def _whoop_callback_handler():
    code = request.args.get("code")
    error = request.args.get("error")
    state = request.args.get("state")

    logger.info(
        "whoop_callback_received",
        has_code=bool(code),
        has_state=bool(state),
    )

    if error:
        error_desc = request.args.get("error_description", error)
        logger.error("whoop_oauth_error", error_type=error)
        flash(f"Whoop authorization failed: {error_desc}")
        return redirect(SETTINGS_REDIRECT)

    if not _validate_whoop_callback_state(state):
        return redirect(SETTINGS_REDIRECT)

    if not code:
        flash("Authorization code not received")
        return redirect(SETTINGS_REDIRECT)

    try:
        client_id = os.getenv("WHOOP_CLIENT_ID")
        client_secret = os.getenv("WHOOP_CLIENT_SECRET")
        redirect_uri = os.getenv(
            "WHOOP_REDIRECT_URI", "http://localhost:8080/whoop/callback"
        )

        tokens = _exchange_whoop_token(code, client_id, client_secret, redirect_uri)
        if tokens is None:
            flash("Token exchange failed. Please try again.")
            return redirect(SETTINGS_REDIRECT)

        _save_whoop_tokens(tokens)

        flash("Whoop account connected successfully!")
        return redirect(SETTINGS_REDIRECT)

    except (requests.RequestException, KeyError, ValueError):
        logger.exception("whoop_connection_error")
        flash("Error connecting Whoop. Please try again.")
        return redirect(SETTINGS_REDIRECT)


def register_routes(server, limiter):
    @server.route("/login", methods=["GET", "POST"])
    @limiter.limit("3000 per hour")
    def login():
        return _login_handler(LoginForm())

    @server.route("/logout", methods=["GET"])
    @login_required
    @limiter.limit("3000 per hour")
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @server.route("/", methods=["GET"])
    def index():
        return redirect("/dashboard/")

    @server.route("/whoop/authorize", methods=["GET"])
    @login_required
    def whoop_authorize():
        client_id = os.getenv("WHOOP_CLIENT_ID")
        redirect_uri = os.getenv(
            "WHOOP_REDIRECT_URI", "http://localhost:8080/whoop/callback"
        )

        if not client_id:
            flash("Whoop integration not configured")
            return redirect(SETTINGS_REDIRECT)

        import time

        state = secrets.token_urlsafe(32)
        session["whoop_oauth_state"] = state
        session["whoop_oauth_state_ts"] = time.time()
        return redirect(_build_whoop_auth_url(client_id, redirect_uri, state))

    @server.route("/whoop/callback", methods=["GET"])
    @login_required
    def whoop_callback():
        return _whoop_callback_handler()

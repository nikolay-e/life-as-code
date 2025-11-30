"""
Flask routes for Life-as-Code application.
Handles authentication, health checks, and basic routing.
"""

import datetime
import os

import requests
from flask import flash, redirect, render_template_string, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired

from database import get_db_session_context
from models import User, UserCredentials
from security import encrypt_data_for_user, verify_password


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


def register_routes(server, limiter):
    """Register Flask routes with the server."""

    @server.route("/login", methods=["GET", "POST"])
    @limiter.limit("10 per minute")
    def login():
        form = LoginForm()
        if form.validate_on_submit():
            try:
                with get_db_session_context() as db:
                    user = db.scalars(
                        select(User).filter_by(username=form.username.data)
                    ).first()
                    if user and verify_password(form.password.data, user.password_hash):
                        user_model = UserModel(user.id, user.username)
                        login_user(user_model)
                        return redirect("/dashboard/")
                    flash("Invalid username or password")
            except Exception:
                flash("An error occurred during login")

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

    @server.route("/logout")
    @login_required
    @limiter.limit("5 per minute")
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @server.route("/healthz")
    @limiter.exempt
    def health_check():
        """Unauthenticated health endpoint for K8s probes."""
        try:
            from sqlalchemy import text

            with get_db_session_context() as db:
                db.execute(text("SELECT 1")).scalar()
                return {"status": "ok", "database": "connected"}, 200
        except Exception as e:
            return {"status": "error", "database": "disconnected", "error": str(e)}, 503

    @server.route("/")
    def index():
        return redirect("/dashboard/")

    @server.route("/whoop/authorize")
    @login_required
    def whoop_authorize():
        """Redirect to Whoop OAuth authorization."""
        client_id = os.getenv("WHOOP_CLIENT_ID")
        # nosemgrep: python.flask.security.audit.flask-url-for-external-true.flask-url-for-external-true
        redirect_uri = url_for("whoop_callback", _external=True)

        if not client_id:
            flash("Whoop integration not configured")
            return redirect("/dashboard/settings")

        auth_url = (
            f"https://api.prod.whoop.com/oauth/oauth2/auth"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&scope=offline read:recovery read:sleep read:workout read:cycles"
        )

        return redirect(auth_url)

    @server.route("/whoop/callback")
    @login_required
    def whoop_callback():
        """Handle Whoop OAuth callback."""
        code = request.args.get("code")
        error = request.args.get("error")

        if error:
            flash(f"Whoop authorization failed: {error}")
            return redirect("/dashboard/settings")

        if not code:
            flash("Authorization code not received")
            return redirect("/dashboard/settings")

        try:
            client_id = os.getenv("WHOOP_CLIENT_ID")
            client_secret = os.getenv("WHOOP_CLIENT_SECRET")
            # nosemgrep: python.flask.security.audit.flask-url-for-external-true.flask-url-for-external-true
            redirect_uri = url_for("whoop_callback", _external=True)

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
                flash(f"Token exchange failed: {response.text}")
                return redirect("/dashboard/settings")

            tokens = response.json()

            with get_db_session_context() as db:
                creds = db.scalars(
                    select(UserCredentials).where(
                        UserCredentials.user_id == current_user.id
                    )
                ).first()

                if not creds:
                    creds = UserCredentials(user_id=current_user.id)
                    db.add(creds)

                creds.encrypted_whoop_access_token = encrypt_data_for_user(
                    tokens["access_token"], current_user.id
                )
                creds.encrypted_whoop_refresh_token = encrypt_data_for_user(
                    tokens["refresh_token"], current_user.id
                )
                creds.whoop_token_expires_at = (
                    datetime.datetime.utcnow()
                    + datetime.timedelta(seconds=tokens.get("expires_in", 3600))
                )

                db.commit()

            flash("Whoop account connected successfully!")
            return redirect("/dashboard/settings")

        except Exception as e:
            flash(f"Error connecting Whoop: {str(e)}")
            return redirect("/dashboard/settings")

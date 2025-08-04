"""
Life-as-Code Multi-User Web Portal
Secure health analytics with user authentication and data isolation.
"""

import logging
import os

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, dcc, html
from flask import Flask, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import select

from callbacks import register_callbacks
from database import SessionLocal, check_db_connection, init_db
from layouts import get_authenticated_layout
from models import User
from routes import UserModel, register_routes

# Configure logging
logger = logging.getLogger(__name__)

# --- Flask Server & Authentication Setup ---
server = Flask(__name__)
server.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
if not server.config["SECRET_KEY"]:
    raise ValueError(
        "SECRET_KEY not set in environment. Please set it in your .env file."
    )

# Initialize database
print("🔧 Initializing database...")
if check_db_connection():
    init_db()
    print("✅ Database ready!")
else:
    print("❌ Database connection failed!")
    exit(1)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access the dashboard."

# Initialize Flask-Limiter for rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    app=server,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window",
)


# Rate limiting exemption for Dash routes
@limiter.request_filter
def dash_route_exempt():
    """Exempt Dash internal routes from rate limiting."""
    return request.endpoint and (
        request.endpoint.startswith("dash")
        or request.endpoint in ["_dash_assets.static", "_dash-update-component"]
    )


# CSRF Protection with Dash compatibility
class DashCSRFProtect(CSRFProtect):
    def init_app(self, app):
        super().init_app(app)
        # Exempt Dash callback endpoints from CSRF
        self.exempt("/_dash-update-component")
        self.exempt("/_dash-layout")
        self.exempt("/_dash-dependencies")


csrf = DashCSRFProtect(server)


# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login."""
    db = SessionLocal()
    try:
        user = db.scalars(select(User).filter_by(id=int(user_id))).first()
        if user:
            return UserModel(user.id, user.username)
        return None
    finally:
        db.close()


# Register Flask routes
register_routes(server, limiter)

# --- Dash App Setup ---
app = dash.Dash(
    __name__,
    server=server,
    url_base_pathname="/dashboard/",
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="Life-as-Code Health Analytics",
)

# Main app layout
app.layout = html.Div(
    [dcc.Location(id="url", refresh=False), html.Div(id="page-content")]
)


# Page routing callback
@callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname):
    """Handle page routing for authenticated users."""
    if pathname.startswith("/dashboard") and current_user.is_authenticated:
        return get_authenticated_layout()
    return html.Div(
        [
            html.H3("Access Denied"),
            html.P("Please log in to access the dashboard."),
            html.A("Login", href="/login"),
        ]
    )


# Register all Dash callbacks
register_callbacks(app)

if __name__ == "__main__":
    # Development server
    app.run_server(
        host="0.0.0.0",
        port=8080,
        debug=True,  # Set to False in production
        dev_tools_hot_reload=False,  # Disable in production
    )

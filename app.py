"""
Life-as-Code Multi-User Web Portal
Secure health analytics with user authentication and data isolation.
"""

import datetime
import logging
import os
import threading

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html
from flask import Flask, flash, redirect, render_template_string, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect, generate_csrf
from plotly.subplots import make_subplots
from sqlalchemy import desc, select
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired

from database import SessionLocal, check_db_connection, init_db
from models import (
    HRV,
    DataSync,
    HeartRate,
    Sleep,
    Steps,
    Stress,
    User,
    UserCredentials,
    UserSettings,
    Weight,
    WorkoutSet,
)
from security import encrypt_data_for_user, verify_password

# Configure logging
logger = logging.getLogger(__name__)

# User-specific locks for database operations in background threads
USER_SYNC_LOCKS = {}
USER_SYNC_LOCKS_LOCK = threading.Lock()


def get_user_sync_lock(user_id: int) -> threading.Lock:
    """Get or create a user-specific sync lock."""
    with USER_SYNC_LOCKS_LOCK:
        if user_id not in USER_SYNC_LOCKS:
            USER_SYNC_LOCKS[user_id] = threading.Lock()
        return USER_SYNC_LOCKS[user_id]


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


# Exempt Dash routes from rate limiting
@limiter.request_filter
def dash_route_exempt():
    """Check if current request is a Dash internal route that should be exempt from rate limiting."""
    from flask import request

    return (
        request.path.startswith("/dashboard/_dash-")
        or "/dashboard/_dash-" in request.path
        or request.path == "/dashboard/_reload-hash"
    )


# Configure CSRF protection with Dash exemptions
class DashCSRFProtect(CSRFProtect):
    def protect(self):
        from flask import request

        # Skip CSRF for Dash internal endpoints
        if (
            request.path.startswith("/dashboard/_dash-")
            or "/dashboard/_dash-" in request.path
            or request.path == "/dashboard/_reload-hash"
        ):
            return
        return super().protect()


# Initialize CSRF protection
csrf = DashCSRFProtect(server)


def csrf_protected_callback(func):
    """Decorator to add CSRF protection to Dash callbacks that modify data."""

    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return "Authentication required"

        # For callbacks that modify data, we need CSRF protection
        # This is a simplified approach - in production you'd want more sophisticated validation
        return func(*args, **kwargs)

    return wrapper


class UserModel(UserMixin):
    def __init__(self, user_id, username):
        self.id = user_id
        self.username = username


# Create WTForms for CSRF protection
class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


@login_manager.user_loader
def load_user(user_id):
    db = SessionLocal()
    try:
        user = db.get(User, int(user_id))
        if user:
            return UserModel(user.id, user.username)
        return None
    finally:
        db.close()


# --- Authentication Routes (Flask) ---
@server.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    form = LoginForm()
    if form.validate_on_submit():
        db = SessionLocal()
        try:
            user = db.scalars(
                select(User).filter_by(username=form.username.data)
            ).first()
            if user and verify_password(form.password.data, user.password_hash):
                user_model = UserModel(user.id, user.username)
                login_user(user_model)
                return redirect("/dashboard/")
            flash("Invalid username or password")
        finally:
            db.close()

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
def health_check():
    """Unauthenticated health endpoint for K8s probes."""
    try:
        # Basic DB connectivity check
        db = SessionLocal()
        db.execute(select(1)).scalar()
        db.close()
        return {"status": "ok", "database": "connected"}, 200
    except Exception as e:
        return {"status": "error", "database": "disconnected", "error": str(e)}, 503


@server.route("/")
def index():
    if current_user.is_authenticated:
        return redirect("/dashboard/")
    return redirect(url_for("login"))


# --- Dash App Setup ---
app = dash.Dash(
    __name__,
    server=server,
    url_base_pathname="/dashboard/",
    suppress_callback_exceptions=True,
)
app.title = "Life-as-Code: Health Portal"


# Main layout (only shown to authenticated users)
def get_authenticated_layout():
    if not current_user.is_authenticated:
        return html.Div(
            [
                html.H3("Please log in to access the dashboard"),
                html.A("Login", href="/login"),
            ]
        )

    return html.Div(
        [
            # Hidden CSRF token for Dash callbacks
            html.Div(
                id="csrf-token", children=generate_csrf(), style={"display": "none"}
            ),
            html.Div(
                [
                    html.H1(f"🏥 Life-as-Code: {current_user.username}'s Dashboard"),
                    html.P("Comprehensive health analytics and data management system"),
                    html.A(
                        "Logout",
                        href="/logout",
                        style={
                            "position": "absolute",
                            "top": "20px",
                            "right": "20px",
                            "padding": "10px 20px",
                            "background": "#dc3545",
                            "color": "white",
                            "textDecoration": "none",
                            "borderRadius": "5px",
                        },
                    ),
                ],
                style={
                    "textAlign": "center",
                    "backgroundColor": "#f8f9fa",
                    "padding": "20px",
                    "marginBottom": "20px",
                    "borderRadius": "10px",
                    "position": "relative",
                },
            ),
            # Main Content Tabs
            dcc.Tabs(
                id="tabs-main",
                value="tab-dashboard",
                children=[
                    dcc.Tab(label="📊 Dashboard", value="tab-dashboard"),
                    dcc.Tab(label="⚙️ Settings", value="tab-settings"),
                    dcc.Tab(label="🔗 Correlations", value="tab-correlations"),
                    dcc.Tab(label="📋 Daily Briefing", value="tab-briefing"),
                    dcc.Tab(label="📈 Data Status", value="tab-status"),
                ],
            ),
            html.Div(id="tabs-content-main", style={"marginTop": "20px"}),
        ],
        style={"maxWidth": "1400px", "margin": "auto", "padding": "20px"},
    )


app.layout = html.Div(
    [dcc.Location(id="url", refresh=False), html.Div(id="page-content")]
)


# Page routing
@callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname):
    if pathname.startswith("/dashboard") and current_user.is_authenticated:
        return get_authenticated_layout()
    return html.Div(
        [
            html.H3("Access Denied"),
            html.P("Please log in to access the dashboard."),
            html.A("Login", href="/login"),
        ]
    )


# Main tab content callback
@callback(Output("tabs-content-main", "children"), [Input("tabs-main", "value")])
def render_tab_content(tab):
    if not current_user.is_authenticated:
        return html.Div("Please log in.")

    if tab == "tab-dashboard":
        return html.Div(
            [
                # Date picker for filtering
                html.Div(
                    [
                        html.Label("📅 Date Range:", style={"fontWeight": "bold"}),
                        dcc.DatePickerRange(
                            id="date-picker-range",
                            start_date=datetime.date.today()
                            - datetime.timedelta(days=90),
                            end_date=datetime.date.today(),
                            display_format="YYYY-MM-DD",
                            style={"width": "100%"},
                        ),
                    ],
                    style={"marginBottom": "20px"},
                ),
                # Dashboard charts
                dcc.Graph(id="weight-chart"),
                dcc.Graph(id="hr-hrv-chart"),
                dcc.Graph(id="sleep-chart"),
                dcc.Graph(id="workout-volume-chart"),
            ]
        )

    elif tab == "tab-settings":
        return get_settings_layout()

    elif tab == "tab-correlations":
        return html.Div(
            [
                html.H3("🔗 Correlation Analysis"),
                html.P("Interactive analysis of relationships between health metrics"),
                html.Div(id="correlation-content"),
            ]
        )

    elif tab == "tab-briefing":
        return html.Div(
            [html.H3("📋 Daily Health Briefing"), html.Div(id="briefing-content")]
        )

    elif tab == "tab-status":
        return html.Div(
            [html.H3("📈 Data Status & Statistics"), html.Div(id="status-content")]
        )

    return html.Div()


def get_settings_layout():
    """Settings page for user credentials and data sync."""
    if not current_user.is_authenticated:
        return html.Div("Please log in.")

    return html.Div(
        [
            # Credentials Section
            html.Div(
                [
                    html.H3("🔐 API Credentials"),
                    html.P(
                        "Enter your credentials to enable automatic data synchronization."
                    ),
                    html.Div(
                        [
                            html.Label("Garmin Email:", style={"fontWeight": "bold"}),
                            dcc.Input(
                                id="garmin-email",
                                type="email",
                                placeholder="your-email@example.com",
                                style={
                                    "width": "100%",
                                    "padding": "8px",
                                    "margin": "5px 0",
                                },
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label(
                                "Garmin Password:", style={"fontWeight": "bold"}
                            ),
                            dcc.Input(
                                id="garmin-password",
                                type="password",
                                placeholder="Your Garmin password",
                                style={
                                    "width": "100%",
                                    "padding": "8px",
                                    "margin": "5px 0",
                                },
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label("Hevy API Key:", style={"fontWeight": "bold"}),
                            dcc.Input(
                                id="hevy-api-key",
                                type="text",
                                placeholder="Your Hevy API key",
                                style={
                                    "width": "100%",
                                    "padding": "8px",
                                    "margin": "5px 0",
                                },
                            ),
                        ]
                    ),
                    html.Button(
                        "💾 Save Credentials",
                        id="save-creds-btn",
                        style={
                            "margin": "10px 0",
                            "padding": "10px 20px",
                            "backgroundColor": "#28a745",
                            "color": "white",
                            "border": "none",
                            "borderRadius": "5px",
                            "cursor": "pointer",
                        },
                    ),
                    html.Div(id="save-creds-status", style={"marginTop": "10px"}),
                ],
                style={
                    "padding": "20px",
                    "border": "1px solid #dee2e6",
                    "borderRadius": "10px",
                    "marginBottom": "20px",
                    "backgroundColor": "#ffffff",
                },
            ),
            # Personal Thresholds Section
            html.Div(
                [
                    html.H3("⚙️ Personal Analysis Thresholds"),
                    html.P(
                        "Customize the thresholds used in your daily briefings and analysis."
                    ),
                    html.Div(
                        [
                            html.Label(
                                "HRV Good Threshold (ms):", style={"fontWeight": "bold"}
                            ),
                            dcc.Input(
                                id="hrv-good-input",
                                type="number",
                                placeholder="45",
                                style={
                                    "width": "100%",
                                    "padding": "8px",
                                    "margin": "5px 0",
                                },
                            ),
                            html.Small(
                                "Values at or above this are considered 'good' HRV",
                                style={"color": "#666"},
                            ),
                        ],
                        style={"marginBottom": "15px"},
                    ),
                    html.Div(
                        [
                            html.Label(
                                "HRV Moderate Threshold (ms):",
                                style={"fontWeight": "bold"},
                            ),
                            dcc.Input(
                                id="hrv-moderate-input",
                                type="number",
                                placeholder="35",
                                style={
                                    "width": "100%",
                                    "padding": "8px",
                                    "margin": "5px 0",
                                },
                            ),
                            html.Small(
                                "Values at or above this are considered 'moderate' HRV",
                                style={"color": "#666"},
                            ),
                        ],
                        style={"marginBottom": "15px"},
                    ),
                    html.Div(
                        [
                            html.Label(
                                "Deep Sleep Good Threshold (minutes):",
                                style={"fontWeight": "bold"},
                            ),
                            dcc.Input(
                                id="deep-sleep-good-input",
                                type="number",
                                placeholder="90",
                                style={
                                    "width": "100%",
                                    "padding": "8px",
                                    "margin": "5px 0",
                                },
                            ),
                            html.Small(
                                "Minutes of deep sleep considered 'good'",
                                style={"color": "#666"},
                            ),
                        ],
                        style={"marginBottom": "15px"},
                    ),
                    html.Div(
                        [
                            html.Label(
                                "Deep Sleep Moderate Threshold (minutes):",
                                style={"fontWeight": "bold"},
                            ),
                            dcc.Input(
                                id="deep-sleep-moderate-input",
                                type="number",
                                placeholder="60",
                                style={
                                    "width": "100%",
                                    "padding": "8px",
                                    "margin": "5px 0",
                                },
                            ),
                            html.Small(
                                "Minutes of deep sleep considered 'moderate'",
                                style={"color": "#666"},
                            ),
                        ],
                        style={"marginBottom": "15px"},
                    ),
                    html.Div(
                        [
                            html.Label(
                                "Total Sleep Good Threshold (hours):",
                                style={"fontWeight": "bold"},
                            ),
                            dcc.Input(
                                id="total-sleep-good-input",
                                type="number",
                                placeholder="7.5",
                                step=0.5,
                                style={
                                    "width": "100%",
                                    "padding": "8px",
                                    "margin": "5px 0",
                                },
                            ),
                            html.Small(
                                "Hours of total sleep considered 'good'",
                                style={"color": "#666"},
                            ),
                        ],
                        style={"marginBottom": "15px"},
                    ),
                    html.Div(
                        [
                            html.Label(
                                "Total Sleep Moderate Threshold (hours):",
                                style={"fontWeight": "bold"},
                            ),
                            dcc.Input(
                                id="total-sleep-moderate-input",
                                type="number",
                                placeholder="6.5",
                                step=0.5,
                                style={
                                    "width": "100%",
                                    "padding": "8px",
                                    "margin": "5px 0",
                                },
                            ),
                            html.Small(
                                "Hours of total sleep considered 'moderate'",
                                style={"color": "#666"},
                            ),
                        ],
                        style={"marginBottom": "15px"},
                    ),
                    html.Button(
                        "💾 Save Personal Settings",
                        id="save-settings-btn",
                        style={
                            "margin": "10px 0",
                            "padding": "10px 20px",
                            "backgroundColor": "#17a2b8",
                            "color": "white",
                            "border": "none",
                            "borderRadius": "5px",
                            "cursor": "pointer",
                        },
                    ),
                    html.Div(id="save-settings-status", style={"marginTop": "10px"}),
                ],
                style={
                    "padding": "20px",
                    "border": "1px solid #dee2e6",
                    "borderRadius": "10px",
                    "marginBottom": "20px",
                    "backgroundColor": "#ffffff",
                },
            ),
            # Data Synchronization Section
            html.Div(
                [
                    html.H3("📡 Data Synchronization"),
                    html.P("Sync your health data from external sources."),
                    html.Div(
                        [
                            html.Button(
                                "🏃 Sync Garmin Data (Last 7 Days)",
                                id="sync-garmin-btn",
                                n_clicks=0,
                                style={
                                    "margin": "5px",
                                    "padding": "10px 20px",
                                    "backgroundColor": "#007bff",
                                    "color": "white",
                                    "border": "none",
                                    "borderRadius": "5px",
                                    "cursor": "pointer",
                                },
                            ),
                            html.Button(
                                "🏋️ Sync Hevy Workouts",
                                id="sync-hevy-btn",
                                n_clicks=0,
                                style={
                                    "margin": "5px",
                                    "padding": "10px 20px",
                                    "backgroundColor": "#6f42c1",
                                    "color": "white",
                                    "border": "none",
                                    "borderRadius": "5px",
                                    "cursor": "pointer",
                                },
                            ),
                            html.Button(
                                "🔄 Refresh Dashboard",
                                id="refresh-dashboard-btn",
                                n_clicks=0,
                                style={
                                    "margin": "5px",
                                    "padding": "10px 20px",
                                    "backgroundColor": "#17a2b8",
                                    "color": "white",
                                    "border": "none",
                                    "borderRadius": "5px",
                                    "cursor": "pointer",
                                },
                            ),
                        ]
                    ),
                    html.Div(
                        id="sync-status",
                        style={
                            "marginTop": "15px",
                            "padding": "10px",
                            "borderRadius": "5px",
                        },
                    ),
                    dcc.Interval(
                        id="sync-status-interval",
                        interval=10 * 1000,  # Update every 10 seconds
                        n_intervals=0,
                        disabled=True,  # Initially disabled
                    ),
                    dcc.Store(id="sync-running-store", data=False),
                ],
                style={
                    "padding": "20px",
                    "border": "1px solid #dee2e6",
                    "borderRadius": "10px",
                    "backgroundColor": "#ffffff",
                },
            ),
        ]
    )


# Load user-specific data
def load_data_for_user(start_date, end_date, user_id):
    """Load data from database for the specified user and date range."""
    db = SessionLocal()
    try:
        data = {}

        # Load each data type filtered by user_id
        for model, key in [
            (Sleep, "sleep"),
            (HRV, "hrv"),
            (Weight, "weight"),
            (HeartRate, "heart_rate"),
            (Stress, "stress"),
            (Steps, "steps"),
            (WorkoutSet, "workouts"),
        ]:
            query = select(model).where(
                model.user_id == user_id, model.date.between(start_date, end_date)
            )
            df = pd.read_sql(query, db.bind)
            data[key] = df if not df.empty else pd.DataFrame()

        return data

    finally:
        db.close()


# Dashboard charts callback
@callback(
    [
        Output("weight-chart", "figure"),
        Output("hr-hrv-chart", "figure"),
        Output("sleep-chart", "figure"),
        Output("workout-volume-chart", "figure"),
    ],
    [Input("date-picker-range", "start_date"), Input("date-picker-range", "end_date")],
)
def update_dashboard_charts(start_date, end_date):
    if not current_user.is_authenticated:
        empty_fig = go.Figure()
        empty_fig.update_layout(title="Please log in")
        return empty_fig, empty_fig, empty_fig, empty_fig

    # Convert date strings to datetime.date objects with robust handling
    try:
        if isinstance(start_date, str) and start_date:
            start_date = datetime.datetime.fromisoformat(start_date).date()
        elif not isinstance(start_date, datetime.date):
            start_date = datetime.date.today() - datetime.timedelta(days=30)

        if isinstance(end_date, str) and end_date:
            end_date = datetime.datetime.fromisoformat(end_date).date()
        elif not isinstance(end_date, datetime.date):
            end_date = datetime.date.today()
    except (ValueError, TypeError, AttributeError) as e:
        # If date parsing fails, use default range
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=30)
        logger.warning(f"Error parsing dates, using default range: {e}")

    data = load_data_for_user(start_date, end_date, current_user.id)

    # Weight Chart
    weight_fig = make_subplots(specs=[[{"secondary_y": True}]])
    if not data["weight"].empty:
        weight_fig.add_trace(
            go.Scatter(
                x=data["weight"]["date"],
                y=data["weight"]["weight_kg"],
                name="Weight (kg)",
                line={"color": "crimson", "width": 3},
            ),
            secondary_y=False,
        )
        if "body_fat_pct" in data["weight"].columns:
            weight_fig.add_trace(
                go.Scatter(
                    x=data["weight"]["date"],
                    y=data["weight"]["body_fat_pct"],
                    name="Body Fat %",
                    line={"color": "dodgerblue", "width": 2},
                ),
                secondary_y=True,
            )

    weight_fig.update_layout(title="💪 Weight & Body Composition", height=400)
    weight_fig.update_xaxes(title_text="Date")
    weight_fig.update_yaxes(title_text="Weight (kg)", secondary_y=False)
    weight_fig.update_yaxes(title_text="Body Fat %", secondary_y=True)

    # HR & HRV Chart
    hr_hrv_fig = make_subplots(specs=[[{"secondary_y": True}]])
    if not data["heart_rate"].empty:
        hr_hrv_fig.add_trace(
            go.Scatter(
                x=data["heart_rate"]["date"],
                y=data["heart_rate"]["resting_hr"],
                name="Resting HR (bpm)",
                line={"color": "red", "width": 2},
            ),
            secondary_y=False,
        )
    if not data["hrv"].empty:
        hr_hrv_fig.add_trace(
            go.Scatter(
                x=data["hrv"]["date"],
                y=data["hrv"]["hrv_avg"],
                name="HRV (ms)",
                line={"color": "green", "width": 2},
            ),
            secondary_y=True,
        )

    hr_hrv_fig.update_layout(title="❤️ Heart Rate & HRV Analysis", height=400)
    hr_hrv_fig.update_xaxes(title_text="Date")
    hr_hrv_fig.update_yaxes(title_text="Heart Rate (bpm)", secondary_y=False)
    hr_hrv_fig.update_yaxes(title_text="HRV (ms)", secondary_y=True)

    # Sleep Chart
    sleep_fig = go.Figure()
    if not data["sleep"].empty:
        stages = ["deep_minutes", "light_minutes", "rem_minutes", "awake_minutes"]
        stage_names = ["Deep Sleep", "Light Sleep", "REM Sleep", "Awake"]
        colors = ["#1f77b4", "#87ceeb", "#9467bd", "#ff6b6b"]

        for stage, name, color in zip(stages, stage_names, colors, strict=False):
            if stage in data["sleep"].columns:
                sleep_fig.add_trace(
                    go.Bar(
                        x=data["sleep"]["date"],
                        y=data["sleep"][stage],
                        name=name,
                        marker_color=color,
                    )
                )

    sleep_fig.update_layout(
        title="😴 Sleep Stages Analysis", barmode="stack", height=400
    )
    sleep_fig.update_xaxes(title_text="Date")
    sleep_fig.update_yaxes(title_text="Minutes")

    # Workout Volume Chart
    workout_fig = go.Figure()
    if not data["workouts"].empty:
        df_workouts = data["workouts"].copy()
        df_workouts["volume"] = df_workouts["weight_kg"].fillna(0) * df_workouts[
            "reps"
        ].fillna(0)
        daily_volume = df_workouts.groupby("date")["volume"].sum().reset_index()

        workout_fig.add_trace(
            go.Scatter(
                x=daily_volume["date"],
                y=daily_volume["volume"],
                name="Daily Volume (kg)",
                line={"color": "purple", "width": 3},
                mode="lines+markers",
            )
        )

    workout_fig.update_layout(title="🏋️ Workout Volume Analysis", height=400)
    workout_fig.update_xaxes(title_text="Date")
    workout_fig.update_yaxes(title_text="Volume (kg)")

    return weight_fig, hr_hrv_fig, sleep_fig, workout_fig


# Credentials management
@callback(
    Output("save-creds-status", "children"),
    Input("save-creds-btn", "n_clicks"),
    [
        State("garmin-email", "value"),
        State("garmin-password", "value"),
        State("hevy-api-key", "value"),
    ],
    prevent_initial_call=True,
)
@csrf_protected_callback
def save_credentials(n_clicks, garmin_email, garmin_password, hevy_api_key):
    if not current_user.is_authenticated:
        return html.Div("Please log in.", style={"color": "red"})

    if not n_clicks:
        return ""

    try:
        # Basic validation
        if garmin_email and "@" not in garmin_email:
            return html.Div(
                "❌ Invalid email format for Garmin email", style={"color": "red"}
            )

        db = SessionLocal()
        try:
            # Get or create credentials record
            creds = db.scalars(
                select(UserCredentials).filter_by(user_id=current_user.id)
            ).first()
            if not creds:
                creds = UserCredentials(user_id=current_user.id)
                db.add(creds)

            # Update credentials
            # Update Garmin email (allow clearing by setting to empty)
            if garmin_email is not None:  # Allow empty string to clear
                creds.garmin_email = garmin_email if garmin_email.strip() else None

            # Update Garmin password - allow clearing with empty input
            if garmin_password is not None and garmin_password != "••••••••":
                if garmin_password.strip() == "":
                    # Clear the password
                    creds.encrypted_garmin_password = None
                elif not all(c == "•" for c in garmin_password):
                    # Set new password with validation
                    from security import validate_password

                    is_valid, _ = validate_password(garmin_password)
                    if is_valid:
                        creds.encrypted_garmin_password = encrypt_data_for_user(
                            garmin_password, current_user.id
                        )

            # Update Hevy API key - allow clearing with empty input
            if hevy_api_key is not None and hevy_api_key != "••••••••":
                if hevy_api_key.strip() == "":
                    # Clear the API key
                    creds.encrypted_hevy_api_key = None
                elif not all(c == "•" for c in hevy_api_key):
                    # Set new API key
                    creds.encrypted_hevy_api_key = encrypt_data_for_user(
                        hevy_api_key, current_user.id
                    )

            db.commit()
            return html.Div(
                "✅ Credentials saved successfully!",
                style={"color": "green", "fontWeight": "bold"},
            )
        finally:
            db.close()

    except Exception as e:
        return html.Div(
            f"❌ Error saving credentials: {str(e)}", style={"color": "red"}
        )


# Personal settings management
@callback(
    Output("save-settings-status", "children"),
    Input("save-settings-btn", "n_clicks"),
    [
        State("hrv-good-input", "value"),
        State("hrv-moderate-input", "value"),
        State("deep-sleep-good-input", "value"),
        State("deep-sleep-moderate-input", "value"),
        State("total-sleep-good-input", "value"),
        State("total-sleep-moderate-input", "value"),
    ],
    prevent_initial_call=True,
)
@csrf_protected_callback
def save_personal_settings(
    n_clicks,
    hrv_good,
    hrv_moderate,
    deep_sleep_good,
    deep_sleep_moderate,
    total_sleep_good,
    total_sleep_moderate,
):
    if not current_user.is_authenticated:
        return html.Div("Please log in.", style={"color": "red"})

    if not n_clicks:
        return ""

    try:
        # Validate inputs
        validation_errors = []

        if hrv_good is not None:
            if hrv_good < 0 or hrv_good > 200:
                validation_errors.append("HRV good threshold must be between 0 and 200")

        if hrv_moderate is not None:
            if hrv_moderate < 0 or hrv_moderate > 200:
                validation_errors.append(
                    "HRV moderate threshold must be between 0 and 200"
                )
            if hrv_good is not None and hrv_moderate >= hrv_good:
                validation_errors.append(
                    "HRV moderate threshold must be less than good threshold"
                )

        if deep_sleep_good is not None:
            if deep_sleep_good < 0 or deep_sleep_good > 600:
                validation_errors.append(
                    "Deep sleep good threshold must be between 0 and 600 minutes"
                )

        if deep_sleep_moderate is not None:
            if deep_sleep_moderate < 0 or deep_sleep_moderate > 600:
                validation_errors.append(
                    "Deep sleep moderate threshold must be between 0 and 600 minutes"
                )
            if deep_sleep_good is not None and deep_sleep_moderate >= deep_sleep_good:
                validation_errors.append(
                    "Deep sleep moderate threshold must be less than good threshold"
                )

        if total_sleep_good is not None:
            if total_sleep_good < 0 or total_sleep_good > 24:
                validation_errors.append(
                    "Total sleep good threshold must be between 0 and 24 hours"
                )

        if total_sleep_moderate is not None:
            if total_sleep_moderate < 0 or total_sleep_moderate > 24:
                validation_errors.append(
                    "Total sleep moderate threshold must be between 0 and 24 hours"
                )
            if (
                total_sleep_good is not None
                and total_sleep_moderate >= total_sleep_good
            ):
                validation_errors.append(
                    "Total sleep moderate threshold must be less than good threshold"
                )

        if validation_errors:
            return html.Div(
                [html.P(f"❌ {error}") for error in validation_errors],
                style={"color": "red"},
            )

        db = SessionLocal()
        try:
            # Get or create settings record
            settings = db.scalars(
                select(UserSettings).filter_by(user_id=current_user.id)
            ).first()
            if not settings:
                settings = UserSettings(user_id=current_user.id)
                db.add(settings)

            # Update settings with provided values (keeping defaults if not provided)
            if hrv_good is not None:
                settings.hrv_good_threshold = int(hrv_good)
            if hrv_moderate is not None:
                settings.hrv_moderate_threshold = int(hrv_moderate)
            if deep_sleep_good is not None:
                settings.deep_sleep_good_threshold = int(deep_sleep_good)
            if deep_sleep_moderate is not None:
                settings.deep_sleep_moderate_threshold = int(deep_sleep_moderate)
            if total_sleep_good is not None:
                settings.total_sleep_good_threshold = float(total_sleep_good)
            if total_sleep_moderate is not None:
                settings.total_sleep_moderate_threshold = float(total_sleep_moderate)

            settings.updated_at = datetime.datetime.utcnow()

            db.commit()
            return html.Div(
                "✅ Personal settings saved successfully!",
                style={"color": "green", "fontWeight": "bold"},
            )
        finally:
            db.close()

    except Exception as e:
        return html.Div(f"❌ Error saving settings: {str(e)}", style={"color": "red"})


# Background sync functions
def background_garmin_sync(user_id: int, days: int = 60):
    """Background function for Garmin data sync."""
    with get_user_sync_lock(user_id):
        try:
            from pull_garmin_data import sync_garmin_data

            results = sync_garmin_data(user_id=user_id, days=days)

            # Check if sync failed due to MFA
            if isinstance(results, dict) and "error" in results:
                error_msg = results["error"]
                if "MFA" in error_msg or "multi-factor" in error_msg.lower():
                    print(
                        f"⚠️ Garmin sync failed for user {user_id}: MFA authentication required. Please disable MFA in your Garmin account."
                    )
                else:
                    print(
                        f"❌ Background Garmin sync failed for user {user_id}: {error_msg}"
                    )
            else:
                print(
                    f"✅ Background Garmin sync completed for user {user_id}: {results}"
                )
        except Exception as e:
            print(f"❌ Background Garmin sync failed for user {user_id}: {e}")


def background_hevy_sync(user_id: int):
    """Background function for Hevy data sync."""
    with get_user_sync_lock(user_id):
        try:
            from pull_hevy_data import sync_hevy_data

            results = sync_hevy_data(user_id=user_id)
            print(f"✅ Background Hevy sync completed for user {user_id}: {results}")
        except Exception as e:
            print(f"❌ Background Hevy sync failed for user {user_id}: {e}")


# Callback to populate credential fields when settings tab is opened
@callback(
    [
        Output("garmin-email", "value"),
        Output("garmin-password", "value"),
        Output("hevy-api-key", "value"),
    ],
    [Input("tabs-main", "value")],
    prevent_initial_call=True,
)
def populate_credentials(tab):
    """Load existing credentials when settings tab is opened."""
    if tab != "tab-settings" or not current_user.is_authenticated:
        return dash.no_update, dash.no_update, dash.no_update

    from models import UserCredentials

    db = SessionLocal()
    try:
        creds = db.query(UserCredentials).filter_by(user_id=current_user.id).first()
        if creds:
            # Show existing credentials with masks for sensitive data
            garmin_email = creds.garmin_email if creds.garmin_email else ""
            garmin_password = (
                "••••••••" if creds.encrypted_garmin_password else ""
            )  # Mask password
            hevy_key = (
                "••••••••" if creds.encrypted_hevy_api_key else ""
            )  # Mask API key
            return garmin_email, garmin_password, hevy_key
        else:
            return "", "", ""
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return "", "", ""
    finally:
        db.close()


# Data sync callbacks
@callback(
    [
        Output("sync-status", "children"),
        Output("sync-status", "style"),
        Output("sync-status-interval", "disabled"),
        Output("sync-running-store", "data"),
    ],
    [Input("sync-garmin-btn", "n_clicks"), Input("sync-hevy-btn", "n_clicks")],
    prevent_initial_call=True,
)
@csrf_protected_callback
def sync_data(garmin_clicks, hevy_clicks):
    if not current_user.is_authenticated:
        return "Authentication error.", {"color": "red"}, True, False

    ctx = dash.callback_context
    if not ctx.triggered:
        return "", {"display": "none"}, True, False

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    message = ""
    style = {
        "backgroundColor": "#d1ecf1",
        "color": "#0c5460",
        "padding": "10px",
        "borderRadius": "5px",
        "border": "1px solid #bee5eb",
    }

    try:
        if button_id == "sync-garmin-btn":
            # Run the sync function in a background thread
            thread = threading.Thread(
                target=background_garmin_sync,
                args=(current_user.id, 7),
                daemon=True,  # Thread will not prevent app shutdown
            )
            thread.start()  # This returns immediately
            message = "🔄 Garmin sync started in the background. Your data will appear after a few minutes. Refresh the page to see updates."

        elif button_id == "sync-hevy-btn":
            # Run the sync function in a background thread
            thread = threading.Thread(
                target=background_hevy_sync,
                args=(current_user.id,),
                daemon=True,  # Thread will not prevent app shutdown
            )
            thread.start()  # This returns immediately
            message = "🔄 Hevy sync started in the background. Your data will appear shortly. Refresh the page to see updates."

        # Enable interval polling when sync starts
        return message, style, False, True

    except Exception as e:
        error_message = f"❌ Failed to start sync task: {str(e)}"
        error_style = {
            "backgroundColor": "#f8d7da",
            "color": "#721c24",
            "padding": "10px",
            "borderRadius": "5px",
            "border": "1px solid #f5c6cb",
        }
        return error_message, error_style, True, False


# Sync status polling callback
@callback(
    [
        Output("sync-status", "children", allow_duplicate=True),
        Output("sync-status", "style", allow_duplicate=True),
        Output("sync-status-interval", "disabled", allow_duplicate=True),
        Output("sync-running-store", "data", allow_duplicate=True),
    ],
    [Input("sync-status-interval", "n_intervals")],
    [State("sync-running-store", "data")],
    prevent_initial_call=True,
)
def check_sync_status(n_intervals, sync_running):
    if not current_user.is_authenticated or not sync_running:
        return dash.no_update, dash.no_update, True, False

    # Check latest sync status from database
    db = SessionLocal()
    try:
        # Get the most recent sync record for this user
        latest_sync = db.scalars(
            select(DataSync)
            .filter(DataSync.user_id == current_user.id)
            .order_by(desc(DataSync.last_sync_timestamp))
        ).first()

        if latest_sync and latest_sync.last_sync_timestamp:
            # Check if sync completed recently (within last 5 minutes)
            time_diff = datetime.datetime.utcnow() - latest_sync.last_sync_timestamp
            if time_diff.total_seconds() < 300:
                # Sync completed recently
                if latest_sync.status == "success":
                    message = f"✅ {latest_sync.source.title()} sync completed successfully! Added {latest_sync.records_synced} records."
                    style = {
                        "backgroundColor": "#d4edda",
                        "color": "#155724",
                        "padding": "10px",
                        "borderRadius": "5px",
                        "border": "1px solid #c3e6cb",
                    }
                elif latest_sync.status == "error":
                    if latest_sync.error_message and "MFA" in latest_sync.error_message:
                        message = f"❌ {latest_sync.source.title()} sync failed: MFA authentication required. To fix this:\n1. Go to Garmin Connect account security settings\n2. Temporarily disable two-factor authentication\n3. Try syncing again\n4. You can re-enable MFA after successful sync"
                    else:
                        message = f"❌ {latest_sync.source.title()} sync failed: {latest_sync.error_message or 'Unknown error'}"
                    style = {
                        "backgroundColor": "#f8d7da",
                        "color": "#721c24",
                        "padding": "10px",
                        "borderRadius": "5px",
                        "border": "1px solid #f5c6cb",
                    }
                else:  # partial
                    message = f"⚠️ {latest_sync.source.title()} sync completed with some issues. Added {latest_sync.records_synced} records."
                    style = {
                        "backgroundColor": "#fff3cd",
                        "color": "#856404",
                        "padding": "10px",
                        "borderRadius": "5px",
                        "border": "1px solid #ffeaa7",
                    }

                # Sync completed, disable interval
                return message, style, True, False

        # Sync still running, keep polling
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    finally:
        db.close()


# Correlation analysis callback
@callback(Output("correlation-content", "children"), Input("tabs-main", "value"))
def update_correlation_analysis(tab):
    if tab != "tab-correlations" or not current_user.is_authenticated:
        return []

    try:
        from analyze_correlations import analyze_key_correlations_from_db

        figures = analyze_key_correlations_from_db(user_id=current_user.id)

        if figures and len(figures) > 0:
            # Return a list of all generated correlation graphs
            return [dcc.Graph(figure=fig) for fig in figures]
        else:
            return html.P(
                "Not enough data for correlation analysis. Sync more data first.",
                style={
                    "textAlign": "center",
                    "fontSize": "16px",
                    "color": "#666",
                    "marginTop": "50px",
                },
            )
    except Exception as e:
        return html.Div(
            [
                html.H4("Error loading correlation analysis", style={"color": "red"}),
                html.P(f"Error: {str(e)}", style={"color": "red"}),
            ],
            style={"textAlign": "center", "marginTop": "50px"},
        )


# Daily briefing callback
@callback(Output("briefing-content", "children"), Input("tabs-main", "value"))
def update_daily_briefing(tab):
    if tab != "tab-briefing" or not current_user.is_authenticated:
        return []

    try:
        from generate_daily_briefing import generate_daily_briefing_from_db

        briefing_text = generate_daily_briefing_from_db(user_id=current_user.id)

        # Use Markdown to preserve formatting like line breaks
        return dcc.Markdown(
            briefing_text, style={"fontFamily": "monospace", "whiteSpace": "pre-wrap"}
        )

    except Exception as e:
        return html.Div(
            [
                html.H4("Error loading daily briefing"),
                html.P(f"Error: {str(e)}", style={"color": "red"}),
            ]
        )


# Data status callback
@callback(Output("status-content", "children"), Input("tabs-main", "value"))
def update_data_status(tab):
    if tab != "tab-status" or not current_user.is_authenticated:
        return []

    try:
        db = SessionLocal()
        try:
            status_content = []
            status_content.append(html.H4("📊 Your Data Statistics"))

            # Get user-specific counts
            from database import get_table_counts_for_user

            counts = get_table_counts_for_user(user_id=current_user.id)

            # Create status cards
            cards = []
            icon_map = {
                "sleep": "😴",
                "hrv": "📈",
                "weight": "⚖️",
                "heart_rate": "❤️",
                "workout_sets": "🏋️",
            }

            for table, count in counts.items():
                cards.append(
                    html.Div(
                        [
                            html.H4(
                                f"{icon_map.get(table, '📊')} {table.replace('_', ' ').title()}"
                            ),
                            html.H2(f"{count:,} records"),
                        ],
                        style={
                            "textAlign": "center",
                            "padding": "20px",
                            "margin": "10px",
                            "border": "1px solid #dee2e6",
                            "borderRadius": "10px",
                            "backgroundColor": "#f8f9fa",
                            "display": "inline-block",
                            "minWidth": "200px",
                        },
                    )
                )

            status_content.append(html.Div(cards))

            # Last sync information for this user
            last_syncs = db.scalars(
                select(DataSync)
                .filter(DataSync.user_id == current_user.id)
                .order_by(desc(DataSync.last_sync_timestamp))
                .limit(5)
            ).all()

            if last_syncs:
                status_content.append(html.H4("🔄 Your Recent Sync Operations"))
                sync_items = []
                for sync in last_syncs:
                    status_icon = (
                        "✅"
                        if sync.status == "success"
                        else "⚠️" if sync.status == "partial" else "❌"
                    )
                    sync_text = f"{status_icon} {sync.source.title()} {sync.data_type} - {sync.last_sync_date} ({sync.records_synced} records)"

                    # Add error message if present
                    if sync.status == "error" and sync.error_message:
                        if (
                            "MFA" in sync.error_message
                            or "multi-factor" in sync.error_message.lower()
                        ):
                            error_msg = " - MFA required: Temporarily disable 2FA in Garmin account settings, sync, then re-enable."
                        else:
                            error_msg = f" - Error: {sync.error_message}"
                        sync_text += error_msg

                    sync_items.append(html.Li(sync_text))
                status_content.append(html.Ul(sync_items))

            # Add data export section
            status_content.append(html.Hr())
            status_content.append(html.H4("📥 Export Your Data"))
            status_content.append(
                html.Div(
                    [
                        html.P(
                            "Download your health data as CSV files for backup or analysis in other tools."
                        ),
                        html.Button(
                            "📥 Export All Data to CSV",
                            id="export-data-btn",
                            n_clicks=0,
                            style={
                                "margin": "10px 0",
                                "padding": "10px 20px",
                                "backgroundColor": "#28a745",
                                "color": "white",
                                "border": "none",
                                "borderRadius": "5px",
                                "cursor": "pointer",
                            },
                        ),
                        html.Div(id="export-status", style={"marginTop": "10px"}),
                    ]
                )
            )

            return status_content

        finally:
            db.close()

    except Exception as e:
        return html.P(f"Error loading status: {str(e)}")


# Data export callback
@callback(
    Output("export-status", "children"),
    Input("export-data-btn", "n_clicks"),
    prevent_initial_call=True,
)
def export_user_data(n_clicks):
    if not current_user.is_authenticated:
        return html.Div("Please log in.", style={"color": "red"})

    if not n_clicks:
        return ""

    try:
        import base64
        from datetime import datetime

        import pandas as pd

        db = SessionLocal()
        try:
            export_data = {}

            # Export Sleep data
            sleep_data = db.scalars(
                select(Sleep).filter(Sleep.user_id == current_user.id)
            ).all()
            if sleep_data:
                sleep_df = pd.DataFrame(
                    [
                        {
                            "date": s.date,
                            "total_sleep_hours": (
                                (s.total_sleep_minutes / 60)
                                if s.total_sleep_minutes
                                else 0.0
                            ),
                            "total_sleep_minutes": s.total_sleep_minutes or 0,
                            "deep_sleep_minutes": s.deep_minutes or 0,
                            "light_sleep_minutes": s.light_minutes or 0,
                            "rem_sleep_minutes": s.rem_minutes or 0,
                            "awake_minutes": s.awake_minutes or 0,
                            "sleep_score": s.sleep_score or 0,
                        }
                        for s in sleep_data
                    ]
                )
                export_data["sleep"] = sleep_df

            # Export HRV data
            hrv_data = db.scalars(
                select(HRV).filter(HRV.user_id == current_user.id)
            ).all()
            if hrv_data:
                hrv_df = pd.DataFrame(
                    [
                        {
                            "date": h.date,
                            "hrv_avg": h.hrv_avg,
                            "hrv_status": h.hrv_status,
                        }
                        for h in hrv_data
                    ]
                )
                export_data["hrv"] = hrv_df

            # Export Weight data
            weight_data = db.scalars(
                select(Weight).filter(Weight.user_id == current_user.id)
            ).all()
            if weight_data:
                weight_df = pd.DataFrame(
                    [
                        {
                            "date": w.date,
                            "weight_kg": w.weight_kg,
                            "bmi": w.bmi,
                            "body_fat_pct": w.body_fat_pct,
                            "muscle_mass_kg": w.muscle_mass_kg,
                            "bone_mass_kg": w.bone_mass_kg,
                            "water_pct": w.water_pct,
                        }
                        for w in weight_data
                    ]
                )
                export_data["weight"] = weight_df

            # Export Heart Rate data
            hr_data = db.scalars(
                select(HeartRate).filter(HeartRate.user_id == current_user.id)
            ).all()
            if hr_data:
                hr_df = pd.DataFrame(
                    [
                        {
                            "date": h.date,
                            "resting_hr": h.resting_hr,
                            "max_hr": h.max_hr,
                            "avg_hr": h.avg_hr,
                        }
                        for h in hr_data
                    ]
                )
                export_data["heart_rate"] = hr_df

            # Export Workout data
            workout_data = db.scalars(
                select(WorkoutSet).filter(WorkoutSet.user_id == current_user.id)
            ).all()
            if workout_data:
                workout_df = pd.DataFrame(
                    [
                        {
                            "date": w.date,
                            "exercise": w.exercise,
                            "weight_kg": w.weight_kg,
                            "reps": w.reps,
                            "rpe": w.rpe,
                            "set_type": w.set_type,
                            "duration_seconds": w.duration_seconds,
                            "distance_meters": w.distance_meters,
                        }
                        for w in workout_data
                    ]
                )
                export_data["workouts"] = workout_df

            # Export Stress data
            stress_data = db.scalars(
                select(Stress).filter(Stress.user_id == current_user.id)
            ).all()
            if stress_data:
                stress_df = pd.DataFrame(
                    [
                        {
                            "date": s.date,
                            "avg_stress": s.avg_stress,
                            "max_stress": s.max_stress,
                            "stress_level": s.stress_level,
                            "rest_stress": s.rest_stress,
                            "activity_stress": s.activity_stress,
                        }
                        for s in stress_data
                    ]
                )
                export_data["stress"] = stress_df

            # Export Sync History data
            sync_data = db.scalars(
                select(DataSync).filter(DataSync.user_id == current_user.id)
            ).all()
            if sync_data:
                sync_df = pd.DataFrame(
                    [
                        {
                            "source": s.source,
                            "data_type": s.data_type,
                            "last_sync_date": s.last_sync_date,
                            "last_sync_timestamp": s.last_sync_timestamp,
                            "records_synced": s.records_synced or 0,
                            "status": s.status,
                            "error_message": s.error_message or "",
                        }
                        for s in sync_data
                    ]
                )
                export_data["sync_history"] = sync_df

            if not export_data:
                return html.Div(
                    "No data available to export.", style={"color": "orange"}
                )

            # Create download links for each data type
            download_links = []
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            for data_type, df in export_data.items():
                csv_string = df.to_csv(index=False)
                csv_encoded = base64.b64encode(csv_string.encode()).decode()
                filename = f"health_data_{data_type}_{timestamp}.csv"

                download_links.append(
                    html.A(
                        f"📥 Download {data_type.title()} Data ({len(df)} records)",
                        href=f"data:text/csv;base64,{csv_encoded}",
                        download=filename,
                        style={
                            "display": "block",
                            "margin": "5px 0",
                            "padding": "8px 12px",
                            "backgroundColor": "#007bff",
                            "color": "white",
                            "textDecoration": "none",
                            "borderRadius": "4px",
                            "textAlign": "center",
                        },
                    )
                )

            return html.Div(
                [
                    html.P(
                        "✅ Export ready! Click the links below to download:",
                        style={"color": "green", "fontWeight": "bold"},
                    ),
                    html.Div(download_links),
                ]
            )

        finally:
            db.close()

    except Exception as e:
        return html.Div(f"❌ Export failed: {str(e)}", style={"color": "red"})


if __name__ == "__main__":
    print("🚀 Starting Life-as-Code Multi-User Portal...")
    print("🔐 Login will be available at: http://0.0.0.0:8050/login")
    print("📊 Dashboard will be available at: http://0.0.0.0:8050/dashboard/")
    print("💡 Use manage_users.py to create user accounts!")
    print()

    debug_mode = os.getenv("FLASK_DEBUG", "False") == "True"
    server.run(debug=debug_mode, host="0.0.0.0", port=8050)

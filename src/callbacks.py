import threading

import plotly.graph_objects as go
from dash import Input, Output, State, callback, callback_context
from flask_login import current_user
from plotly.subplots import make_subplots
from sqlalchemy import select

from data_loaders import (
    get_sleep_metrics,
    get_stress_categories,
    load_data_for_user,
)
from database import SessionLocal, get_db_session_context
from layouts import (
    get_briefing_tab_layout,
    get_correlations_tab_layout,
    get_dashboard_tab_layout,
    get_settings_layout,
    get_status_tab_layout,
)
from logging_config import get_logger
from models import UserCredentials, UserSettings

logger = get_logger(__name__)


def csrf_protected_callback(func):
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return "Not authenticated"
        return func(*args, **kwargs)

    return wrapper


def register_callbacks(app):
    # Main tab content callback
    @callback(Output("tabs-content-main", "children"), [Input("tabs-main", "value")])
    def render_tab_content(tab):
        if not current_user.is_authenticated:
            return "Please log in."

        if tab == "tab-dashboard":
            return get_dashboard_tab_layout()
        elif tab == "tab-settings":
            return get_settings_layout()
        elif tab == "tab-correlations":
            return get_correlations_tab_layout()
        elif tab == "tab-briefing":
            return get_briefing_tab_layout()
        elif tab == "tab-status":
            return get_status_tab_layout()

        return "Invalid tab"

    # Dashboard charts callback
    @callback(
        [
            Output("weight-chart", "figure"),
            Output("hr-hrv-chart", "figure"),
            Output("sleep-chart", "figure"),
            Output("whoop-recovery-chart", "figure"),
            Output("stress-chart", "figure"),
            Output("steps-chart", "figure"),
        ],
        [
            Input("date-picker-range", "start_date"),
            Input("date-picker-range", "end_date"),
        ],
    )
    def update_dashboard_charts(start_date, end_date):
        if not current_user.is_authenticated:
            empty_fig = go.Figure()
            empty_fig.update_layout(title="Please log in")
            return tuple([empty_fig] * 6)

        user_id = current_user.id
        data = load_data_for_user(start_date, end_date, user_id)

        # Weight Chart
        weight_fig = create_weight_chart(data["weight"])

        # HR/HRV Chart
        hr_hrv_fig = create_hr_hrv_chart(data["heart_rate"], data["hrv"])

        # Sleep Chart
        sleep_fig = create_sleep_chart(data["sleep"])

        # Whoop Recovery Chart
        whoop_recovery_fig = create_whoop_recovery_chart(data["whoop_recovery"])

        # Stress Chart
        stress_fig = create_stress_chart(data["stress"])

        # Steps Chart
        steps_fig = create_steps_chart(data["steps"])

        return (
            weight_fig,
            hr_hrv_fig,
            sleep_fig,
            whoop_recovery_fig,
            stress_fig,
            steps_fig,
        )

    # Credentials status callback (read-only display)
    @callback(
        Output("credentials-status-display", "children"),
        [Input("tabs-main", "value")],
    )
    def display_credentials_status(tab):
        if tab != "tab-settings" or not current_user.is_authenticated:
            return ""

        try:
            with get_db_session_context() as db:
                creds = db.scalars(
                    select(UserCredentials).where(
                        UserCredentials.user_id == current_user.id
                    )
                ).first()

                garmin_ok = bool(
                    creds and creds.garmin_email and creds.encrypted_garmin_password
                )
                hevy_ok = bool(creds and creds.encrypted_hevy_api_key)
                whoop_ok = bool(creds and creds.encrypted_whoop_access_token)

                from dash import html

                return html.Div(
                    [
                        html.Div(
                            [
                                html.Span(
                                    "✅ " if garmin_ok else "❌ ",
                                    style={"fontSize": "1.2em"},
                                ),
                                html.Strong("Garmin: "),
                                html.Span(
                                    "Configured" if garmin_ok else "Not configured"
                                ),
                            ],
                            style={"marginBottom": "8px"},
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "✅ " if hevy_ok else "❌ ",
                                    style={"fontSize": "1.2em"},
                                ),
                                html.Strong("Hevy: "),
                                html.Span(
                                    "Configured" if hevy_ok else "Not configured"
                                ),
                            ],
                            style={"marginBottom": "8px"},
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "✅ " if whoop_ok else "❌ ",
                                    style={"fontSize": "1.2em"},
                                ),
                                html.Strong("Whoop: "),
                                html.Span(
                                    "Configured" if whoop_ok else "Not configured"
                                ),
                            ]
                        ),
                    ]
                )

        except Exception as e:
            logger.error(f"Error loading credentials status: {e}")
            return "Error loading credentials status"

    # Personal settings callback
    @callback(
        Output("save-settings-status", "children"),
        [Input("save-settings-btn", "n_clicks")],
        [
            State("hrv-good-input", "value"),
            State("hrv-moderate-input", "value"),
            State("deep-sleep-good-input", "value"),
            State("deep-sleep-moderate-input", "value"),
            State("total-sleep-good-input", "value"),
            State("total-sleep-moderate-input", "value"),
        ],
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
        if n_clicks is None:
            return ""

        if not current_user.is_authenticated:
            return "❌ Not authenticated"

        user_id = current_user.id

        try:
            with get_db_session_context() as db:
                settings = db.scalars(
                    select(UserSettings).where(UserSettings.user_id == user_id)
                ).first()

                if not settings:
                    settings = UserSettings(user_id=user_id)
                    db.add(settings)

                # Update settings with provided values
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
                    settings.total_sleep_moderate_threshold = float(
                        total_sleep_moderate
                    )

                return "✅ Personal settings saved!"

        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return f"❌ Error saving settings: {str(e)}"

    def _run_sync_in_background(sync_func, source_name: str, user_id: int):
        def run_sync():
            try:
                result = sync_func(user_id)
                logger.info(
                    f"{source_name} sync completed for user {user_id}: {result}"
                )
            except Exception as e:
                logger.error(f"{source_name} sync failed for user {user_id}: {e}")
            finally:
                SessionLocal.remove()

        sync_thread = threading.Thread(target=run_sync, daemon=True)
        sync_thread.start()

    @callback(
        Output("sync-status", "children"),
        [
            Input("sync-garmin-btn", "n_clicks"),
            Input("sync-hevy-btn", "n_clicks"),
            Input("sync-whoop-btn", "n_clicks"),
        ],
    )
    @csrf_protected_callback
    def sync_data(garmin_clicks, hevy_clicks, whoop_clicks):
        if not any([garmin_clicks, hevy_clicks, whoop_clicks]):
            return ""

        ctx = callback_context
        if not ctx.triggered:
            return ""

        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        user_id = current_user.id

        sync_configs = {
            "garmin": {
                "module": "pull_garmin_data",
                "func": "sync_garmin_data_for_user",
                "icon": "🏃‍♂️",
                "name": "Garmin",
            },
            "hevy": {
                "module": "pull_hevy_data",
                "func": "sync_hevy_data_for_user",
                "icon": "🏋️‍♂️",
                "name": "Hevy",
            },
            "whoop": {
                "module": "pull_whoop_data",
                "func": "sync_whoop_data_for_user",
                "icon": "🟣",
                "name": "Whoop",
            },
        }

        for source, config in sync_configs.items():
            if source in button_id:
                try:
                    module = __import__(config["module"], fromlist=[config["func"]])
                    sync_func = getattr(module, config["func"])
                    _run_sync_in_background(sync_func, config["name"], user_id)
                    return f"{config['icon']} {config['name']} sync started... (Check Data Status tab for progress)"
                except Exception as e:
                    logger.error(f"Error starting {config['name']} sync: {e}")
                    return f"❌ Error starting sync: {str(e)}"

        return ""


def create_weight_chart(weight_df):
    if weight_df.empty:
        fig = go.Figure()
        fig.update_layout(title="📊 Weight Tracking - No Data Available")
        return fig

    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("Weight & BMI", "Body Composition"),
        vertical_spacing=0.1,
    )

    # Weight and BMI
    if "weight_kg" in weight_df.columns:
        fig.add_trace(
            go.Scatter(
                x=weight_df["date"],
                y=weight_df["weight_kg"],
                mode="lines+markers",
                name="Weight (kg)",
                line={"color": "#007bff"},
            ),
            row=1,
            col=1,
        )

    if "bmi" in weight_df.columns:
        fig.add_trace(
            go.Scatter(
                x=weight_df["date"],
                y=weight_df["bmi"],
                mode="lines+markers",
                name="BMI",
                line={"color": "#28a745"},
                yaxis="y2",
            ),
            row=1,
            col=1,
        )

    # Body composition
    for col, color in [("body_fat_pct", "#dc3545"), ("muscle_mass_kg", "#ffc107")]:
        if col in weight_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=weight_df["date"],
                    y=weight_df[col],
                    mode="lines+markers",
                    name=col.replace("_", " ").title(),
                    line={"color": color},
                ),
                row=2,
                col=1,
            )

    fig.update_layout(
        title="📊 Weight & Body Composition Tracking", height=600, showlegend=True
    )

    return fig


def create_hr_hrv_chart(hr_df, hrv_df):
    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("Heart Rate Metrics", "Heart Rate Variability"),
        vertical_spacing=0.1,
    )

    # Heart Rate
    if not hr_df.empty and "resting_hr" in hr_df.columns:
        fig.add_trace(
            go.Scatter(
                x=hr_df["date"],
                y=hr_df["resting_hr"],
                mode="lines+markers",
                name="Resting HR",
                line={"color": "#dc3545"},
            ),
            row=1,
            col=1,
        )

    # HRV
    if not hrv_df.empty and "hrv_avg" in hrv_df.columns:
        fig.add_trace(
            go.Scatter(
                x=hrv_df["date"],
                y=hrv_df["hrv_avg"],
                mode="lines+markers",
                name="HRV Average",
                line={"color": "#007bff"},
            ),
            row=2,
            col=1,
        )

    fig.update_layout(title="❤️ Heart Rate & HRV Analysis", height=600, showlegend=True)

    return fig


def create_sleep_chart(sleep_df):
    if sleep_df.empty:
        fig = go.Figure()
        fig.update_layout(title="😴 Sleep Analysis - No Data Available")
        return fig

    sleep_df = get_sleep_metrics(sleep_df)

    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("Sleep Duration & Score", "Sleep Stages"),
        vertical_spacing=0.1,
    )

    # Total sleep and score
    if "total_sleep_minutes" in sleep_df.columns:
        fig.add_trace(
            go.Scatter(
                x=sleep_df["date"],
                y=sleep_df["total_sleep_minutes"] / 60,  # Convert to hours
                mode="lines+markers",
                name="Total Sleep (hours)",
                line={"color": "#007bff"},
            ),
            row=1,
            col=1,
        )

    if "sleep_score" in sleep_df.columns:
        fig.add_trace(
            go.Scatter(
                x=sleep_df["date"],
                y=sleep_df["sleep_score"],
                mode="lines+markers",
                name="Sleep Score",
                line={"color": "#28a745"},
                yaxis="y2",
            ),
            row=1,
            col=1,
        )

    # Sleep stages
    for col, color in [
        ("deep_minutes", "#001f3f"),
        ("light_minutes", "#7FDBFF"),
        ("rem_minutes", "#B10DC9"),
    ]:
        if col in sleep_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=sleep_df["date"],
                    y=sleep_df[col] / 60,  # Convert to hours
                    mode="lines+markers",
                    name=col.replace("_minutes", "").replace("_", " ").title(),
                    line={"color": color},
                ),
                row=2,
                col=1,
            )

    fig.update_layout(title="😴 Sleep Analysis", height=600, showlegend=True)

    return fig


def create_stress_chart(stress_df):
    if stress_df.empty:
        fig = go.Figure()
        fig.update_layout(title="😰 Stress Analysis - No Data Available")
        return fig

    stress_df = get_stress_categories(stress_df)

    fig = go.Figure()

    if "avg_stress" in stress_df.columns:
        fig.add_trace(
            go.Scatter(
                x=stress_df["date"],
                y=stress_df["avg_stress"],
                mode="lines+markers",
                name="Average Stress",
                line={"color": "#ffc107"},
            )
        )

    fig.update_layout(
        title="😰 Daily Stress Levels", yaxis_title="Stress Level", height=400
    )

    return fig


def create_steps_chart(steps_df):
    if steps_df.empty:
        fig = go.Figure()
        fig.update_layout(title="🚶‍♂️ Activity Tracking - No Data Available")
        return fig

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if "total_steps" in steps_df.columns:
        fig.add_trace(
            go.Scatter(
                x=steps_df["date"],
                y=steps_df["total_steps"],
                mode="lines+markers",
                name="Daily Steps",
                line={"color": "#28a745"},
            ),
            secondary_y=False,
        )

    if "total_distance" in steps_df.columns:
        fig.add_trace(
            go.Scatter(
                x=steps_df["date"],
                y=steps_df["total_distance"],
                mode="lines+markers",
                name="Distance (km)",
                line={"color": "#007bff"},
            ),
            secondary_y=True,
        )

    fig.update_yaxes(title_text="Steps", secondary_y=False)
    fig.update_yaxes(title_text="Distance (km)", secondary_y=True)
    fig.update_layout(title="🚶‍♂️ Daily Steps & Distance", height=400)

    return fig


def create_whoop_recovery_chart(whoop_recovery_df):
    if whoop_recovery_df.empty:
        fig = go.Figure()
        fig.update_layout(title="🟣 Whoop Recovery - No Data Available")
        return fig

    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("Recovery Score & HRV", "Resting Heart Rate"),
        vertical_spacing=0.1,
    )

    if "recovery_score" in whoop_recovery_df.columns:
        fig.add_trace(
            go.Scatter(
                x=whoop_recovery_df["date"],
                y=whoop_recovery_df["recovery_score"],
                mode="lines+markers",
                name="Recovery Score",
                line={"color": "#9b59b6"},
            ),
            row=1,
            col=1,
        )

    if "hrv_rmssd" in whoop_recovery_df.columns:
        fig.add_trace(
            go.Scatter(
                x=whoop_recovery_df["date"],
                y=whoop_recovery_df["hrv_rmssd"],
                mode="lines+markers",
                name="HRV (rMSSD)",
                line={"color": "#3498db"},
                yaxis="y2",
            ),
            row=1,
            col=1,
        )

    if "resting_heart_rate" in whoop_recovery_df.columns:
        fig.add_trace(
            go.Scatter(
                x=whoop_recovery_df["date"],
                y=whoop_recovery_df["resting_heart_rate"],
                mode="lines+markers",
                name="Resting HR",
                line={"color": "#e74c3c"},
            ),
            row=2,
            col=1,
        )

    fig.update_layout(title="🟣 Whoop Recovery Analysis", height=600, showlegend=True)

    return fig

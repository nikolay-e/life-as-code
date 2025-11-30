import logging
import threading

import plotly.graph_objects as go
from dash import Input, Output, State, callback, callback_context
from flask_login import current_user
from plotly.subplots import make_subplots
from sqlalchemy import select

from data_loaders import (
    get_sleep_metrics,
    get_stress_categories,
    get_workout_volume_data,
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
from models import UserCredentials, UserSettings
from security import encrypt_data_for_user

logger = logging.getLogger(__name__)

# User-specific locks for database operations in background threads
USER_SYNC_LOCKS = {}
USER_SYNC_LOCKS_LOCK = threading.Lock()


def get_user_sync_lock(user_id: int) -> threading.Lock:
    with USER_SYNC_LOCKS_LOCK:
        if user_id not in USER_SYNC_LOCKS:
            USER_SYNC_LOCKS[user_id] = threading.Lock()
        return USER_SYNC_LOCKS[user_id]


def create_figure(data, traces, layout_kwargs):
    fig = go.Figure()
    for trace in traces:
        fig.add_trace(go.Scatter(**trace))
    fig.update_layout(**layout_kwargs)
    return fig


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
            Output("body-battery-chart", "figure"),
            Output("whoop-recovery-chart", "figure"),
            Output("workout-volume-chart", "figure"),
            Output("stress-chart", "figure"),
            Output("energy-chart", "figure"),
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
            return tuple([empty_fig] * 9)

        user_id = current_user.id
        data = load_data_for_user(start_date, end_date, user_id)

        # Weight Chart
        weight_fig = create_weight_chart(data["weight"])

        # HR/HRV Chart
        hr_hrv_fig = create_hr_hrv_chart(data["heart_rate"], data["hrv"])

        # Sleep Chart
        sleep_fig = create_sleep_chart(data["sleep"])

        # Body Battery Chart
        body_battery_fig = create_body_battery_chart(data["body_battery"])

        # Whoop Recovery Chart
        whoop_recovery_fig = create_whoop_recovery_chart(data["whoop_recovery"])

        # Workout Volume Chart
        workout_fig = create_workout_chart(data["workouts"])

        # Stress Chart
        stress_fig = create_stress_chart(data["stress"])

        # Energy Chart
        energy_fig = create_energy_chart(data["energy"])

        # Steps Chart
        steps_fig = create_steps_chart(data["steps"])

        return (
            weight_fig,
            hr_hrv_fig,
            sleep_fig,
            body_battery_fig,
            whoop_recovery_fig,
            workout_fig,
            stress_fig,
            energy_fig,
            steps_fig,
        )

    # Credentials callback
    @callback(
        Output("save-creds-status", "children"),
        [Input("save-creds-btn", "n_clicks")],
        [
            State("garmin-email", "value"),
            State("garmin-password", "value"),
            State("hevy-api-key", "value"),
        ],
    )
    @csrf_protected_callback
    def save_credentials(n_clicks, garmin_email, garmin_password, hevy_api_key):
        if n_clicks is None:
            return ""

        if not current_user.is_authenticated:
            return "❌ Not authenticated"

        user_id = current_user.id

        try:
            with get_db_session_context() as db:
                existing_creds = db.scalars(
                    select(UserCredentials).where(UserCredentials.user_id == user_id)
                ).first()

                if existing_creds:
                    if garmin_email:
                        existing_creds.garmin_email = garmin_email
                    if garmin_password:
                        existing_creds.encrypted_garmin_password = (
                            encrypt_data_for_user(garmin_password, user_id)
                        )
                    if hevy_api_key:
                        existing_creds.encrypted_hevy_api_key = encrypt_data_for_user(
                            hevy_api_key, user_id
                        )
                else:
                    new_creds = UserCredentials(
                        user_id=user_id,
                        garmin_email=garmin_email or "",
                        encrypted_garmin_password=encrypt_data_for_user(
                            garmin_password or "", user_id
                        ),
                        encrypted_hevy_api_key=encrypt_data_for_user(
                            hevy_api_key or "", user_id
                        ),
                    )
                    db.add(new_creds)

                return "✅ Credentials saved successfully!"

        except Exception as e:
            logger.error(f"Error saving credentials: {e}")
            return f"❌ Error saving credentials: {str(e)}"

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

    # Populate credentials callback
    @callback(
        [
            Output("garmin-email", "value"),
            Output("garmin-password", "value"),
            Output("hevy-api-key", "value"),
        ],
        [Input("tabs-main", "value")],
    )
    def populate_credentials(tab):
        if tab != "tab-settings" or not current_user.is_authenticated:
            return "", "", ""

        try:
            with get_db_session_context() as db:
                creds = db.scalars(
                    select(UserCredentials).where(
                        UserCredentials.user_id == current_user.id
                    )
                ).first()

                if creds:
                    return creds.garmin_email or "", "", ""  # Don't populate passwords
                return "", "", ""

        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            return "", "", ""

    # Sync data callbacks would go here but are complex
    # For now, keeping them minimal
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
        if ctx.triggered:
            button_id = ctx.triggered[0]["prop_id"].split(".")[0]
            user_id = current_user.id

            try:
                if "garmin" in button_id:
                    # Import here to avoid circular imports
                    import threading

                    from pull_garmin_data import sync_garmin_data_for_user

                    # Run sync in background thread
                    def run_garmin_sync():
                        try:
                            result = sync_garmin_data_for_user(user_id)
                            logger.info(
                                f"Garmin sync completed for user {user_id}: {result}"
                            )
                        except Exception as e:
                            logger.error(f"Garmin sync failed for user {user_id}: {e}")
                        finally:
                            SessionLocal.remove()

                    sync_thread = threading.Thread(target=run_garmin_sync)
                    sync_thread.daemon = True
                    sync_thread.start()

                    return "🏃‍♂️ Garmin sync started... (Check Data Status tab for progress)"

                elif "hevy" in button_id:
                    # Import here to avoid circular imports
                    import threading

                    from pull_hevy_data import sync_hevy_data_for_user

                    # Run sync in background thread
                    def run_hevy_sync():
                        try:
                            result = sync_hevy_data_for_user(user_id)
                            logger.info(
                                f"Heavy sync completed for user {user_id}: {result}"
                            )
                        except Exception as e:
                            logger.error(f"Heavy sync failed for user {user_id}: {e}")
                        finally:
                            SessionLocal.remove()

                    sync_thread = threading.Thread(target=run_hevy_sync)
                    sync_thread.daemon = True
                    sync_thread.start()

                    return (
                        "🏋️‍♂️ Heavy sync started... (Check Data Status tab for progress)"
                    )

                elif "whoop" in button_id:
                    # Import here to avoid circular imports
                    import threading

                    from pull_whoop_data import sync_whoop_data_for_user

                    # Run sync in background thread
                    def run_whoop_sync():
                        try:
                            result = sync_whoop_data_for_user(user_id)
                            logger.info(
                                f"Whoop sync completed for user {user_id}: {result}"
                            )
                        except Exception as e:
                            logger.error(f"Whoop sync failed for user {user_id}: {e}")
                        finally:
                            SessionLocal.remove()

                    sync_thread = threading.Thread(target=run_whoop_sync)
                    sync_thread.daemon = True
                    sync_thread.start()

                    return (
                        "🟣 Whoop sync started... (Check Data Status tab for progress)"
                    )

            except Exception as e:
                logger.error(f"Error starting sync: {e}")
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


def create_workout_chart(workouts_df):
    if workouts_df.empty:
        fig = go.Figure()
        fig.update_layout(title="🏋️‍♂️ Workout Analysis - No Data Available")
        return fig

    volume_data = get_workout_volume_data(workouts_df)

    if volume_data.empty:
        fig = go.Figure()
        fig.update_layout(title="🏋️‍♂️ Workout Analysis - No Volume Data")
        return fig

    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("Daily Training Volume", "Training Frequency"),
        vertical_spacing=0.1,
    )

    # Training volume
    fig.add_trace(
        go.Bar(
            x=volume_data["date"],
            y=volume_data["total_volume"],
            name="Volume (kg×reps)",
            marker_color="#007bff",
        ),
        row=1,
        col=1,
    )

    # Training frequency (sets per day)
    fig.add_trace(
        go.Bar(
            x=volume_data["date"],
            y=volume_data["total_sets"],
            name="Total Sets",
            marker_color="#28a745",
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        title="🏋️‍♂️ Workout Volume & Frequency", height=600, showlegend=True
    )

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


def create_energy_chart(energy_df):
    if energy_df.empty:
        fig = go.Figure()
        fig.update_layout(title="⚡ Energy Expenditure - No Data Available")
        return fig

    fig = go.Figure()

    for col, color in [("active_energy", "#dc3545"), ("basal_energy", "#007bff")]:
        if col in energy_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=energy_df["date"],
                    y=energy_df[col],
                    mode="lines+markers",
                    name=col.replace("_", " ").title(),
                    line={"color": color},
                )
            )

    fig.update_layout(
        title="⚡ Daily Energy Expenditure", yaxis_title="Calories", height=400
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


def create_body_battery_chart(body_battery_df):
    if body_battery_df.empty:
        fig = go.Figure()
        fig.update_layout(title="🔋 Body Battery - No Data Available")
        return fig

    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("Body Battery Range", "Daily Change"),
        vertical_spacing=0.1,
    )

    if "highest" in body_battery_df.columns and "lowest" in body_battery_df.columns:
        fig.add_trace(
            go.Scatter(
                x=body_battery_df["date"],
                y=body_battery_df["highest"],
                mode="lines+markers",
                name="Highest",
                line={"color": "#28a745"},
            ),
            row=1,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=body_battery_df["date"],
                y=body_battery_df["lowest"],
                mode="lines+markers",
                name="Lowest",
                line={"color": "#dc3545"},
            ),
            row=1,
            col=1,
        )

    if "charged" in body_battery_df.columns and "drained" in body_battery_df.columns:
        fig.add_trace(
            go.Bar(
                x=body_battery_df["date"],
                y=body_battery_df["charged"],
                name="Charged",
                marker_color="#28a745",
            ),
            row=2,
            col=1,
        )

        fig.add_trace(
            go.Bar(
                x=body_battery_df["date"],
                y=-body_battery_df["drained"],
                name="Drained",
                marker_color="#dc3545",
            ),
            row=2,
            col=1,
        )

    fig.update_layout(title="🔋 Garmin Body Battery", height=600, showlegend=True)

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

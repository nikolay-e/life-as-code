"""
Dash layouts for Life-as-Code application.
Contains the main authenticated layout and settings layout.
"""

import datetime

from dash import dcc, html
from flask_login import current_user
from flask_wtf.csrf import generate_csrf


def get_authenticated_layout():
    """Main authenticated layout with navigation tabs."""
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


def get_dashboard_tab_layout():
    """Dashboard tab with date picker and chart containers."""
    return html.Div(
        [
            # Date picker for filtering
            html.Div(
                [
                    html.Label("📅 Date Range:", style={"fontWeight": "bold"}),
                    dcc.DatePickerRange(
                        id="date-picker-range",
                        start_date=datetime.date.today() - datetime.timedelta(days=90),
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
            dcc.Graph(id="whoop-recovery-chart"),
            dcc.Graph(id="workout-volume-chart"),
            dcc.Graph(id="stress-chart"),
            dcc.Graph(id="steps-chart"),
        ]
    )


def get_settings_layout():
    """Settings page for user credentials and data sync."""
    if not current_user.is_authenticated:
        return html.Div("Please log in.")

    return html.Div(
        [
            # Credentials Status Section (Read-Only)
            html.Div(
                [
                    html.H3("🔐 API Credentials Status"),
                    html.Div(
                        [
                            html.P(
                                "Credentials are managed through environment variables for security.",
                                style={
                                    "color": "#0c5460",
                                    "backgroundColor": "#d1ecf1",
                                    "padding": "10px",
                                    "borderRadius": "5px",
                                },
                            ),
                            html.P(
                                "To update credentials, modify your .env file or Kubernetes secrets, then restart the application.",
                                style={"fontSize": "0.9em", "color": "#666"},
                            ),
                        ],
                        style={"marginBottom": "15px"},
                    ),
                    html.Div(id="credentials-status-display"),
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
            _get_thresholds_section(),
            # Data Sync Section
            _get_sync_section(),
            # Export Section
            _get_export_section(),
        ]
    )


def _get_thresholds_section():
    """Personal thresholds configuration section."""
    return html.Div(
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
                    "backgroundColor": "#007bff",
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
    )


def _get_sync_section():
    """Data synchronization section."""
    return html.Div(
        [
            html.H3("🔄 Data Synchronization"),
            html.P("Sync your data from external sources."),
            html.Div(
                [
                    html.Button(
                        "🏃‍♂️ Sync Garmin Data",
                        id="sync-garmin-btn",
                        style={
                            "margin": "10px 10px 10px 0",
                            "padding": "10px 20px",
                            "backgroundColor": "#007bff",
                            "color": "white",
                            "border": "none",
                            "borderRadius": "5px",
                            "cursor": "pointer",
                        },
                    ),
                    html.Button(
                        "🏋️‍♂️ Sync Heavy Workouts",
                        id="sync-hevy-btn",
                        style={
                            "margin": "10px",
                            "padding": "10px 20px",
                            "backgroundColor": "#28a745",
                            "color": "white",
                            "border": "none",
                            "borderRadius": "5px",
                            "cursor": "pointer",
                        },
                    ),
                ]
            ),
            html.Div(
                [
                    html.H4("🟣 WHOOP Integration", style={"marginTop": "20px"}),
                    html.A(
                        "🔗 Connect WHOOP Account",
                        href="/whoop/authorize",
                        style={
                            "display": "inline-block",
                            "margin": "10px 10px 10px 0",
                            "padding": "10px 20px",
                            "backgroundColor": "#6f42c1",
                            "color": "white",
                            "border": "none",
                            "borderRadius": "5px",
                            "cursor": "pointer",
                            "textDecoration": "none",
                            "fontWeight": "bold",
                        },
                    ),
                    html.Button(
                        "🔄 Sync WHOOP Data",
                        id="sync-whoop-btn",
                        style={
                            "margin": "10px",
                            "padding": "10px 20px",
                            "backgroundColor": "#9b59b6",
                            "color": "white",
                            "border": "none",
                            "borderRadius": "5px",
                            "cursor": "pointer",
                        },
                    ),
                ]
            ),
            html.Div(id="sync-status", style={"marginTop": "10px"}),
            dcc.Interval(
                id="sync-status-interval", interval=3000, n_intervals=0, disabled=True
            ),
            dcc.Store(id="sync-running", data=False),
        ],
        style={
            "padding": "20px",
            "border": "1px solid #dee2e6",
            "borderRadius": "10px",
            "marginBottom": "20px",
            "backgroundColor": "#ffffff",
        },
    )


def _get_export_section():
    """Data export section."""
    return html.Div(
        [
            html.H3("📁 Data Export"),
            html.P("Export your health data for backup or analysis."),
            html.Div(
                [
                    html.Button(
                        "📊 Export All Data",
                        id="export-all-btn",
                        style={
                            "margin": "10px 10px 10px 0",
                            "padding": "10px 20px",
                            "backgroundColor": "#6f42c1",
                            "color": "white",
                            "border": "none",
                            "borderRadius": "5px",
                            "cursor": "pointer",
                        },
                    ),
                    html.Button(
                        "📈 Export Recent (90 days)",
                        id="export-recent-btn",
                        style={
                            "margin": "10px",
                            "padding": "10px 20px",
                            "backgroundColor": "#fd7e14",
                            "color": "white",
                            "border": "none",
                            "borderRadius": "5px",
                            "cursor": "pointer",
                        },
                    ),
                ]
            ),
            html.Div(id="export-status", style={"marginTop": "10px"}),
        ],
        style={
            "padding": "20px",
            "border": "1px solid #dee2e6",
            "borderRadius": "10px",
            "marginBottom": "20px",
            "backgroundColor": "#ffffff",
        },
    )


def get_correlations_tab_layout():
    """Correlations analysis tab layout."""
    return html.Div(
        [
            html.H3("🔗 Correlation Analysis"),
            html.P("Interactive analysis of relationships between health metrics"),
            html.Div(id="correlation-content"),
        ]
    )


def get_briefing_tab_layout():
    """Daily briefing tab layout."""
    return html.Div(
        [html.H3("📋 Daily Health Briefing"), html.Div(id="briefing-content")]
    )


def get_status_tab_layout():
    """Data status tab layout."""
    return html.Div(
        [html.H3("📈 Data Status & Statistics"), html.Div(id="status-content")]
    )

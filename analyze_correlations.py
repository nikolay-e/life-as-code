"""
Visual Correlation Analysis - THE INSIGHT ENGINE
This script creates scatter plots and correlation visualizations to answer key questions:
- How does sleep affect workout performance?
- How does HRV correlate with objective recovery metrics?
- How do workout patterns affect sleep and recovery?
"""

import datetime

import pandas as pd
import plotly.express as px
from scipy import stats
from sqlalchemy import select

from database import SessionLocal
from models import HRV, Energy, HeartRate, Sleep, Steps, Stress, Weight, WorkoutSet


def load_data_from_database(user_id: int, days=90):
    """Load all data from the database for a specific user into pandas DataFrames for correlation analysis."""
    db = SessionLocal()
    try:
        # Date range for analysis
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=days)

        datasets = {}

        # Load each data type
        from typing import Any

        data_types: list[tuple[Any, str]] = [
            (Sleep, "sleep"),
            (HRV, "hrv"),
            (Weight, "weight"),
            (HeartRate, "heart_rate"),
            (Stress, "stress"),
            (Energy, "energy"),
            (Steps, "steps"),
            (WorkoutSet, "workouts"),
        ]

        for model, key in data_types:
            query = select(model).where(
                model.user_id == user_id,
                model.date.between(start_date, end_date),
            )
            df = pd.read_sql(query, db.bind)

            if not df.empty:
                datasets[key] = df
                print(f"✅ Loaded {len(df)} {key} records")
            else:
                datasets[key] = None
                print(f"⚠️ No {key} data found")

        return datasets

    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return {}
    finally:
        db.close()


def merge_datasets_by_date(datasets):
    """Merge datasets by date to create a unified DataFrame for analysis."""
    if not datasets:
        return pd.DataFrame()

    # Start with the first available dataset
    merged_df = None

    # Get base dates from any available dataset
    for _key, df in datasets.items():
        if df is not None and not df.empty:
            if merged_df is None:
                merged_df = df[["date"]].copy()
            break

    if merged_df is None:
        return pd.DataFrame()

    # Merge each dataset
    dataset_configs = [
        (
            "sleep",
            [
                "deep_minutes",
                "light_minutes",
                "rem_minutes",
                "total_sleep_minutes",
                "sleep_score",
            ],
        ),
        ("hrv", ["hrv_avg"]),
        ("weight", ["weight_kg", "bmi", "body_fat_pct"]),
        ("heart_rate", ["resting_hr", "max_hr", "avg_hr"]),
        ("stress", ["avg_stress", "max_stress"]),
        ("energy", ["active_energy", "basal_energy"]),
        ("steps", ["total_steps", "total_distance"]),
    ]

    for key, columns in dataset_configs:
        if datasets.get(key) is not None and not datasets[key].empty:
            df = datasets[key]
            # Select only the columns that exist in the dataset
            available_cols = ["date"] + [col for col in columns if col in df.columns]
            subset_df = df[available_cols]
            merged_df = pd.merge(merged_df, subset_df, on="date", how="left")

    # Handle workout data separately (needs aggregation)
    if datasets.get("workouts") is not None and not datasets["workouts"].empty:
        workout_df = datasets["workouts"]
        # Calculate daily workout metrics
        if "weight_kg" in workout_df.columns and "reps" in workout_df.columns:
            workout_df["volume"] = workout_df["weight_kg"].fillna(0) * workout_df[
                "reps"
            ].fillna(0)
            daily_volume = workout_df.groupby("date")["volume"].sum().reset_index()
            merged_df = pd.merge(merged_df, daily_volume, on="date", how="left")

        # Count of exercises per day
        daily_exercises = workout_df.groupby("date")["exercise"].nunique().reset_index()
        daily_exercises = daily_exercises.rename(columns={"exercise": "exercise_count"})
        merged_df = pd.merge(merged_df, daily_exercises, on="date", how="left")

    # Fill NaN values
    # Remove fillna(0) to allow pandas corr() to handle NaN values correctly

    print(
        f"📊 Merged dataset created with {len(merged_df)} records and {len(merged_df.columns)} columns"
    )
    return merged_df


def analyze_key_correlations_from_db(user_id: int):
    """
    Analyze key correlations and return a list of plotly figures for a specific user.
    This function can be called by the web app.
    """
    print(f"🔍 Starting correlation analysis for user_id: {user_id}...")

    # Load and merge data
    datasets = load_data_from_database(user_id=user_id, days=90)
    merged_df = merge_datasets_by_date(datasets)

    if merged_df.empty or len(merged_df) < 5:
        print("⚠️ Insufficient data for meaningful correlations")
        return []

    figures = []

    # Define correlation analyses to perform
    correlations_to_analyze = [
        {
            "x": "hrv_avg",
            "y": "sleep_score",
            "title": "📊 HRV vs Sleep Score",
            "x_label": "HRV Average (ms)",
            "y_label": "Sleep Score",
            "question": "Does HRV correlate with sleep quality?",
        },
        {
            "x": "total_sleep_minutes",
            "y": "hrv_avg",
            "title": "😴 Sleep Duration vs Next Day HRV",
            "x_label": "Total Sleep (minutes)",
            "y_label": "HRV Average (ms)",
            "question": "Does better sleep improve recovery?",
        },
        {
            "x": "volume",
            "y": "deep_minutes",
            "title": "🏋️ Workout Volume vs Deep Sleep",
            "x_label": "Daily Volume (kg)",
            "y_label": "Deep Sleep (minutes)",
            "question": "Do high-volume workouts affect sleep stages?",
        },
        {
            "x": "resting_hr",
            "y": "hrv_avg",
            "title": "❤️ Resting Heart Rate vs HRV",
            "x_label": "Resting HR (bpm)",
            "y_label": "HRV Average (ms)",
            "question": "How does resting heart rate relate to HRV?",
        },
        {
            "x": "avg_stress",
            "y": "sleep_score",
            "title": "😰 Stress vs Sleep Quality",
            "x_label": "Average Stress Level",
            "y_label": "Sleep Score",
            "question": "Does stress affect sleep quality?",
        },
        {
            "x": "avg_stress",
            "y": "hrv_avg",
            "title": "😰 Stress vs HRV Recovery",
            "x_label": "Average Stress Level",
            "y_label": "HRV Average (ms)",
            "question": "How does stress impact recovery (HRV)?",
        },
        {
            "x": "active_energy",
            "y": "total_sleep_minutes",
            "title": "🔥 Active Energy vs Sleep Duration",
            "x_label": "Active Energy (kcal)",
            "y_label": "Total Sleep (minutes)",
            "question": "Does higher activity lead to more sleep?",
        },
        {
            "x": "total_steps",
            "y": "active_energy",
            "title": "🚶 Steps vs Active Energy",
            "x_label": "Daily Steps",
            "y_label": "Active Energy (kcal)",
            "question": "How do steps correlate with energy expenditure?",
        },
    ]

    # Generate correlation plots
    for analysis in correlations_to_analyze:
        print(f"\n🔍 {analysis['question']}")

        # Check if both variables exist in the data
        if analysis["x"] not in merged_df.columns:
            print(f"   ⚠️ Variable '{analysis['x']}' not found in data")
            continue

        if analysis["y"] not in merged_df.columns:
            print(f"   ⚠️ Variable '{analysis['y']}' not found in data")
            continue

        # Filter out zero and null values for meaningful analysis
        plot_data = merged_df[
            (merged_df[analysis["x"]] > 0) & (merged_df[analysis["y"]] > 0)
        ].copy()

        if len(plot_data) < 5:
            print(f"   ⚠️ Insufficient valid data points ({len(plot_data)} found)")
            continue

        # Calculate correlation
        correlation, p_value = stats.pearsonr(
            plot_data[analysis["x"]], plot_data[analysis["y"]]
        )

        print(f"   📈 Correlation: {correlation:.3f} (p-value: {p_value:.3f})")

        # Create scatter plot with trendline
        fig = px.scatter(
            plot_data,
            x=analysis["x"],
            y=analysis["y"],
            title=f"{analysis['title']} (r={correlation:.3f})",
            labels={
                analysis["x"]: analysis["x_label"],
                analysis["y"]: analysis["y_label"],
            },
            trendline="ols" if len(plot_data) >= 5 else None,
        )

        # Customize layout
        fig.update_layout(
            showlegend=True, font={"size": 12}, plot_bgcolor="white", height=500
        )

        figures.append(fig)

    print(f"\n✅ Generated {len(figures)} correlation plots")
    return figures


def generate_correlation_report(user_id: int):
    """Generate a text report of key correlations for a specific user."""
    print(f"📋 Generating Correlation Analysis Report for user_id: {user_id}")
    print("=" * 50)

    datasets = load_data_from_database(user_id=user_id, days=90)
    merged_df = merge_datasets_by_date(datasets)

    if merged_df.empty:
        return "No data available for correlation analysis."

    report = []
    report.append("📅 Analysis Period: Last 90 days")
    report.append(f"📊 Records analyzed: {len(merged_df)}")
    report.append("")

    # Key metrics summary
    key_metrics = [
        "hrv_avg",
        "sleep_score",
        "total_sleep_minutes",
        "resting_hr",
        "volume",
        "avg_stress",
        "active_energy",
        "total_steps",
    ]
    available_metrics = [
        m for m in key_metrics if m in merged_df.columns and merged_df[m].sum() > 0
    ]

    if available_metrics:
        report.append("📈 Available Metrics Summary:")
        for metric in available_metrics:
            mean_val = merged_df[metric].mean()
            report.append(f"  • {metric}: {mean_val:.1f} avg")
        report.append("")

    # Correlation matrix for available metrics
    if len(available_metrics) >= 2:
        correlation_matrix = merged_df[available_metrics].corr()
        report.append("🔗 Key Correlations:")

        for i in range(len(available_metrics)):
            for j in range(i + 1, len(available_metrics)):
                metric1, metric2 = available_metrics[i], available_metrics[j]
                correlation = correlation_matrix.loc[metric1, metric2]
                if abs(correlation) > 0.3:  # Only report meaningful correlations
                    strength = (
                        "Strong"
                        if abs(correlation) > 0.7
                        else "Moderate" if abs(correlation) > 0.5 else "Weak"
                    )
                    direction = "positive" if correlation > 0 else "negative"
                    report.append(
                        f"  • {metric1} ↔ {metric2}: {strength} {direction} ({correlation:.3f})"
                    )

    return "\n".join(report)


if __name__ == "__main__":
    print("🧠 LIFE-AS-CODE CORRELATION ANALYSIS (Multi-User)")
    print(
        "This analyzes relationships between your health metrics to answer key questions:"
    )
    print("Note: This script now requires user authentication.")
    print("Use the web portal Correlations tab instead.")
    print()

    print("For testing purposes, you can still run this with a user ID:")
    user_id_input = input("Enter user ID for analysis (or press Enter to exit): ")

    if not user_id_input:
        print("Exiting...")
        exit(0)

    try:
        user_id = int(user_id_input)

        print("• How does sleep affect performance?")
        print("• How do workout patterns affect recovery?")
        print("• How does objective data correlate with performance?")
        print("• And much more...")
        print()

        figures = analyze_key_correlations_from_db(user_id)

        if figures:
            print(
                f"\n🎉 Analysis completed! Generated {len(figures)} interactive plots."
            )
            print("💡 Integrate these into your dashboard or save as HTML files.")
        else:
            print(
                "\n📊 No correlations could be generated. Try syncing more data first."
            )

        # Generate text report
        report = generate_correlation_report(user_id)
        print("\n" + report)

    except ValueError:
        print("❌ Invalid user ID. Please enter a number.")
        exit(1)
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        exit(1)

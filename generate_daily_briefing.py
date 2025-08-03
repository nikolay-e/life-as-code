"""
Proactive Daily Briefing System - THE OPTIMIZATION ENGINE
This script analyzes your latest data to provide actionable recommendations for today.
No more guessing - get data-driven guidance for training and recovery.
"""

import datetime
import io
from contextlib import redirect_stdout

from sqlalchemy import desc, select

from config import (
    HRV_THRESHOLDS,
    SLEEP_THRESHOLDS,
    TOTAL_SLEEP_THRESHOLDS,
    TRAINING_THRESHOLDS,
)
from database import SessionLocal
from models import HRV, HeartRate, Sleep, UserSettings, WorkoutSet


def get_user_thresholds(user_id: int) -> dict:
    """Get personalized thresholds for a user, falling back to config defaults."""
    db = SessionLocal()
    try:
        settings = db.scalars(select(UserSettings).filter_by(user_id=user_id)).first()

        if settings:
            return {
                "hrv_good": settings.hrv_good_threshold,
                "hrv_moderate": settings.hrv_moderate_threshold,
                "sleep_good": settings.deep_sleep_good_threshold,
                "sleep_moderate": settings.deep_sleep_moderate_threshold,
                "total_sleep_good": settings.total_sleep_good_threshold,
                "total_sleep_moderate": settings.total_sleep_moderate_threshold,
                "training_high_volume": settings.training_high_volume_threshold,
            }
        else:
            # Fallback to config defaults
            return {
                "hrv_good": HRV_THRESHOLDS.get("good", 45),
                "hrv_moderate": HRV_THRESHOLDS.get("moderate", 35),
                "sleep_good": SLEEP_THRESHOLDS.get("good", 90),
                "sleep_moderate": SLEEP_THRESHOLDS.get("moderate", 60),
                "total_sleep_good": TOTAL_SLEEP_THRESHOLDS.get("good", 7.5),
                "total_sleep_moderate": TOTAL_SLEEP_THRESHOLDS.get("moderate", 6.5),
                "training_high_volume": TRAINING_THRESHOLDS.get("high_volume_kg", 5000),
            }
    finally:
        db.close()


def load_latest_data(user_id: int):
    """Load the most recent data points from database for a specific user."""
    db = SessionLocal()
    try:
        data = {}

        # Load recent data points (last 7 days)
        lookback_date = datetime.date.today() - datetime.timedelta(days=7)

        # Get latest data for each type for this user
        data["sleep"] = db.scalars(
            select(Sleep)
            .filter(Sleep.user_id == user_id, Sleep.date >= lookback_date)
            .order_by(desc(Sleep.date))
        ).first()
        data["hrv"] = db.scalars(
            select(HRV)
            .filter(HRV.user_id == user_id, HRV.date >= lookback_date)
            .order_by(desc(HRV.date))
        ).first()
        data["heart_rate"] = db.scalars(
            select(HeartRate)
            .filter(HeartRate.user_id == user_id, HeartRate.date >= lookback_date)
            .order_by(desc(HeartRate.date))
        ).first()

        # Get recent workout volume (last 3 days) for this user
        recent_workouts = db.scalars(
            select(WorkoutSet).filter(
                WorkoutSet.user_id == user_id,
                WorkoutSet.date >= datetime.date.today() - datetime.timedelta(days=3),
            )
        ).all()

        if recent_workouts:
            total_volume = sum(
                float(w.weight_kg or 0) * float(w.reps or 0) for w in recent_workouts
            )
            data["workout_volume"] = total_volume
        else:
            data["workout_volume"] = 0.0

        return data, datetime.date.today()

    finally:
        db.close()


def analyze_recovery_status(data, user_thresholds):
    """Analyze recovery status from HRV, sleep, and heart rate metrics using personalized thresholds."""
    recovery_score = 0
    recovery_factors = []
    warnings = []

    # HRV Analysis
    if data["hrv"]:
        hrv_value = data["hrv"].hrv_avg
        if hrv_value >= user_thresholds["hrv_good"]:
            recovery_score += 3
            recovery_factors.append(f"✅ HRV looks good ({hrv_value:.0f}ms)")
        elif hrv_value >= user_thresholds["hrv_moderate"]:
            recovery_score += 1
            recovery_factors.append(f"⚠️ HRV is moderate ({hrv_value:.0f}ms)")
        else:
            recovery_score -= 2
            warnings.append(
                f"🚨 HRV is low ({hrv_value:.0f}ms) - high stress/poor recovery"
            )

    # Sleep Analysis
    if data["sleep"]:
        deep_sleep = data["sleep"].deep_minutes or 0
        total_sleep = data["sleep"].total_sleep_minutes or 0

        if deep_sleep >= user_thresholds["sleep_good"]:
            recovery_score += 2
            recovery_factors.append(f"✅ Deep sleep looks good ({deep_sleep:.0f} min)")
        elif deep_sleep >= user_thresholds["sleep_moderate"]:
            recovery_score += 1
            recovery_factors.append(f"⚠️ Deep sleep is okay ({deep_sleep:.0f} min)")
        elif deep_sleep > 0:
            recovery_score -= 1
            warnings.append(f"⚠️ Deep sleep is low ({deep_sleep:.0f} min)")

        if (
            total_sleep >= user_thresholds["total_sleep_good"] * 60
        ):  # Convert hours to minutes
            recovery_score += 1
            recovery_factors.append(
                f"✅ Sleep duration adequate ({total_sleep/60:.1f}h)"
            )
        elif total_sleep > 0:
            warnings.append(f"⚠️ Sleep duration short ({total_sleep/60:.1f}h)")
            recovery_score -= 1

    return recovery_score, recovery_factors, warnings


def generate_training_recommendations(recovery_score, data, user_thresholds):
    """Generate specific training recommendations based on recovery status and user thresholds."""
    recommendations = []

    if recovery_score >= 4:
        recommendations.append("💪 TRAIN HARD: You're well recovered - go for it!")
        recommendations.append("   • Target challenging loads today")
        recommendations.append("   • Good day for PR attempts or high intensity")
    elif recovery_score >= 2:
        recommendations.append("⚖️ MODERATE: Train at normal intensity")
        recommendations.append("   • Stick to planned sessions")
        recommendations.append("   • Monitor how you feel during training")
    elif recovery_score >= 0:
        recommendations.append("🛟 LIGHT: Consider easier session today")
        recommendations.append("   • Reduce intensity by 20-30%")
        recommendations.append("   • Focus on movement quality and technique")
    else:
        recommendations.append("🛌 REST: Your body needs recovery - don't overtrain")
        recommendations.append("   • Active recovery or complete rest")
        recommendations.append("   • Light stretching or walking only")

    # Workout volume considerations
    if data["workout_volume"] > user_thresholds["training_high_volume"]:
        recommendations.append("⚠️ HIGH VOLUME: Recent workouts were intense")
        recommendations.append("   • Consider deload or recovery focus today")

    return recommendations


def generate_daily_briefing_from_db(user_id: int):
    """Generate the complete daily briefing text for web display for a specific user."""
    f = io.StringIO()

    with redirect_stdout(f):
        data, today = load_latest_data(user_id)
        user_thresholds = get_user_thresholds(user_id)

        print(f"📅 Date: {today.strftime('%A, %B %d, %Y')}")
        print()

        # Recovery Analysis
        recovery_score, recovery_factors, warnings = analyze_recovery_status(
            data, user_thresholds
        )

        print("🔋 RECOVERY STATUS")
        print("-" * 20)

        if recovery_factors:
            for factor in recovery_factors:
                print(factor)

        if warnings:
            print("\n⚠️ RECOVERY WARNINGS:")
            for warning in warnings:
                print(warning)

        print(f"\n📊 Recovery Score: {recovery_score}/10")

        # Training Recommendations
        print("\n" + "🏋️ TRAINING RECOMMENDATIONS")
        print("-" * 28)
        training_recs = generate_training_recommendations(
            recovery_score, data, user_thresholds
        )
        for rec in training_recs:
            print(rec)

        # Key Actions for Today
        print("\n" + "🎯 TOP PRIORITIES TODAY")
        print("-" * 24)

        priorities = []

        if recovery_score <= 0:
            priorities.append("1. 🛌 REST: Your body needs recovery - don't overtrain")
        elif recovery_score <= 2:
            priorities.append("1. ⚖️ MODERATE: Train lighter, focus on form")
        else:
            priorities.append("1. 💪 TRAIN: You're recovered - seize the day")

        # Focus on training consistency
        priorities.append("2. 🎯 FOCUS: Maintain training routine")
        priorities.append("3. 📊 DATA: Keep tracking health metrics")

        for priority in priorities:
            print(priority)

        print("\n" + "=" * 50)
        print("💡 Remember: This is data-driven guidance, not rigid rules.")
        print("   Listen to your body and adjust as needed.")
        print("   The goal is long-term optimization, not daily perfection.")

    return f.getvalue()


def save_briefing_to_file(user_id: int):
    """Save the briefing to a file for reference for a specific user."""
    briefing_text = generate_daily_briefing_from_db(user_id)

    today = datetime.date.today()
    filename = f"daily_briefing_{today.strftime('%Y-%m-%d')}.txt"

    with open(filename, "w") as f:
        f.write(briefing_text)

    print(f"💾 Briefing saved to: {filename}")
    print(briefing_text)


if __name__ == "__main__":
    print("🧠 LIFE-AS-CODE: DAILY OPTIMIZATION BRIEFING (Multi-User)")
    print("This analyzes your latest data to provide actionable guidance.")
    print("Note: This script now requires user authentication.")
    print("Use the web portal Daily Briefing tab instead.")
    print()

    print("For testing purposes, you can still run this with a user ID:")
    user_id_input = input("Enter user ID for briefing (or press Enter to exit): ")

    if not user_id_input:
        print("Exiting...")
        exit(0)

    try:
        user_id = int(user_id_input)
        save_choice = input("Save briefing to file? (y/N): ").lower()

        if save_choice == "y":
            save_briefing_to_file(user_id)
        else:
            print(generate_daily_briefing_from_db(user_id))

    except ValueError:
        print("❌ Invalid user ID. Please enter a number.")
        exit(1)
    except Exception as e:
        print(f"❌ Error generating briefing: {e}")
        exit(1)

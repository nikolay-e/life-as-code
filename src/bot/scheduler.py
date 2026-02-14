import logging
from datetime import date, time

from telegram.ext import Application

from bot.config import BotConfig
from database import get_db_session_context
from models import Anomaly

logger = logging.getLogger(__name__)


def _get_agent():
    from agent.agent import HealthAgent

    return HealthAgent()


def schedule_push_notifications(app: Application, config: BotConfig):
    job_queue = app.job_queue

    if not config.allowed_user_ids:
        return

    chat_id = config.allowed_user_ids[0]
    tz = config.tz

    job_queue.run_daily(
        _push_daily_briefing,
        time=time(hour=7, minute=0, tzinfo=tz),
        data={"chat_id": chat_id, "user_id": config.db_user_id},
        name="daily_briefing",
    )

    job_queue.run_daily(
        _push_anomaly_alert,
        time=time(hour=22, minute=0, tzinfo=tz),
        data={"chat_id": chat_id, "user_id": config.db_user_id},
        name="anomaly_alert",
    )

    job_queue.run_daily(
        _push_weekly_report,
        time=time(hour=9, minute=0, tzinfo=tz),
        days=(0,),
        data={"chat_id": chat_id, "user_id": config.db_user_id},
        name="weekly_report",
    )


async def _push_daily_briefing(context):
    data = context.job.data
    try:
        agent = _get_agent()
        briefing = agent.daily_briefing(data["user_id"])
        await context.bot.send_message(
            chat_id=data["chat_id"],
            text=briefing,
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("daily_briefing_push_failed")


async def _push_anomaly_alert(context):
    data = context.job.data
    try:
        with get_db_session_context() as db:
            row = (
                db.query(Anomaly)
                .filter(
                    Anomaly.user_id == data["user_id"],
                    Anomaly.date == date.today(),
                )
                .first()
            )

        if not row:
            return

        anomaly = {
            "date": row.date,
            "anomaly_score": row.anomaly_score,
            "contributing_factors": row.contributing_factors,
        }
        agent = _get_agent()
        explanation = agent.explain_anomaly(data["user_id"], anomaly)

        await context.bot.send_message(
            chat_id=data["chat_id"],
            text=f"Score: {row.anomaly_score:.2f}\n\n{explanation}",
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("anomaly_alert_push_failed")


async def _push_weekly_report(context):
    data = context.job.data
    try:
        agent = _get_agent()
        report = agent.weekly_report(data["user_id"])
        await context.bot.send_message(
            chat_id=data["chat_id"],
            text=report,
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("weekly_report_push_failed")

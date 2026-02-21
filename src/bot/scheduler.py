import logging
from datetime import time, timedelta
from functools import partial

from telegram.ext import Application

from bot.config import BotConfig
from bot.formatters import send_markdown_safe
from database import get_db_session_context
from date_utils import utcnow

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
        time=time(hour=12, minute=0, tzinfo=tz),
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
        send = partial(context.bot.send_message, chat_id=data["chat_id"])
        await send_markdown_safe(send, briefing)
    except Exception:
        logger.exception("daily_briefing_push_failed")


async def _push_anomaly_alert(context):
    data = context.job.data
    try:
        from models import ClinicalAlertEvent

        with get_db_session_context() as db:
            new_alerts = (
                db.query(ClinicalAlertEvent)
                .filter_by(user_id=data["user_id"], status="open")
                .filter(ClinicalAlertEvent.acknowledged_at.is_(None))
                .order_by(ClinicalAlertEvent.first_detected_at.desc())
                .all()
            )

            if not new_alerts:
                cutoff = utcnow() - timedelta(hours=24)
                resolved = (
                    db.query(ClinicalAlertEvent)
                    .filter_by(user_id=data["user_id"], status="resolved")
                    .filter(ClinicalAlertEvent.resolved_at >= cutoff)
                    .all()
                )
                if not resolved:
                    return

                send = partial(context.bot.send_message, chat_id=data["chat_id"])
                for alert in resolved:
                    text = f"\u2705 *{alert.alert_type}* resolved"
                    await send_markdown_safe(send, text)
                return

            agent = _get_agent()
            send = partial(context.bot.send_message, chat_id=data["chat_id"])

            for alert in new_alerts:
                anomaly_data = {
                    "date": (
                        alert.first_detected_at.date()
                        if alert.first_detected_at
                        else None
                    ),
                    "anomaly_score": 0.8 if alert.severity == "critical" else 0.6,
                    "contributing_factors": alert.details_json or {},
                }
                explanation = agent.explain_anomaly(data["user_id"], anomaly_data)

                severity_emoji = {
                    "critical": "\U0001f534",
                    "alert": "\U0001f7e0",
                    "warning": "\U0001f7e1",
                }.get(alert.severity, "\u26a0\ufe0f")

                text = (
                    f"{severity_emoji} *{alert.alert_type}*"
                    f" ({alert.severity})\n\n{explanation}"
                )
                await send_markdown_safe(send, text)

            cutoff = utcnow() - timedelta(hours=24)
            resolved = (
                db.query(ClinicalAlertEvent)
                .filter_by(user_id=data["user_id"], status="resolved")
                .filter(ClinicalAlertEvent.resolved_at >= cutoff)
                .all()
            )
            for alert in resolved:
                text = f"\u2705 *{alert.alert_type}* resolved"
                await send_markdown_safe(send, text)

    except Exception:
        logger.exception("anomaly_alert_push_failed")


async def _push_weekly_report(context):
    data = context.job.data
    try:
        agent = _get_agent()
        report = agent.weekly_report(data["user_id"])
        send = partial(context.bot.send_message, chat_id=data["chat_id"])
        await send_markdown_safe(send, report)
    except Exception:
        logger.exception("weekly_report_push_failed")

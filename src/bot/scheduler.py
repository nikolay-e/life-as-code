import asyncio
from datetime import date, time, timedelta
from functools import partial

from telegram.ext import Application

from agent.bot_message_repo import save_message
from agent.prompts import build_daily_logging_prompt
from analytics.date_utils import local_today
from bot.config import BotConfig
from bot.formatters import send_markdown_safe
from database import get_db_session_context
from date_utils import utcnow
from logging_config import get_logger

logger = get_logger(__name__)


_SIGNAL_NAME_PATTERNS: dict[str, list[str]] = {
    "alcohol": ["alcohol"],
    "illness": ["illness"],
    "stress": ["stress"],
    "caffeine": ["caffeine", "coffee"],
}


def _signals_already_logged_today(
    user_id: int, today: date, signals: list[str]
) -> set[str]:
    from sqlalchemy import select

    from models import Intervention

    if not signals:
        return set()
    patterns: list[tuple[str, str]] = []
    for s in signals:
        for needle in _SIGNAL_NAME_PATTERNS.get(s, [s]):
            patterns.append((s, needle))
    if not patterns:
        return set()
    found: set[str] = set()
    with get_db_session_context() as db:
        rows = db.scalars(
            select(Intervention).where(
                Intervention.user_id == user_id,
                Intervention.start_date == today,
            )
        ).all()
        for row in rows:
            name_lc = (row.name or "").lower()
            for signal, needle in patterns:
                if needle in name_lc:
                    found.add(signal)
    return found


def _get_agent():
    from agent.agent import HealthAgent

    return HealthAgent()


def _sync_user_data_blocking(user_id: int) -> None:
    from scheduler import _get_sync_funcs, _sync_and_recompute

    sync_funcs = _get_sync_funcs()
    _sync_and_recompute(user_id, sync_funcs)


async def _presync_for_report(user_id: int, report_name: str) -> None:
    logger.info("bot_presync_starting", report=report_name, user_id=user_id)
    try:
        await asyncio.to_thread(_sync_user_data_blocking, user_id)
        logger.info("bot_presync_completed", report=report_name, user_id=user_id)
    except Exception:
        logger.exception("bot_presync_failed", report=report_name, user_id=user_id)


def schedule_push_notifications(app: Application, config: BotConfig):
    job_queue = app.job_queue

    if not config.allowed_user_ids:
        return

    chat_id = config.allowed_user_ids[0]
    tz = config.tz

    job_queue.run_daily(
        _push_daily_briefing,
        time=time(hour=14, minute=0, tzinfo=tz),
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
        time=time(hour=16, minute=0, tzinfo=tz),
        days=(0,),
        data={"chat_id": chat_id, "user_id": config.db_user_id},
        name="weekly_report",
    )

    if config.daily_logging_signals:
        job_queue.run_daily(
            _push_daily_logging_prompt,
            time=time(hour=config.daily_logging_hour, minute=0, tzinfo=tz),
            data={
                "chat_id": chat_id,
                "user_id": config.db_user_id,
                "signals": config.daily_logging_signals,
            },
            name="daily_logging_prompt",
        )


async def _push_daily_briefing(context):
    data = context.job.data
    await _presync_for_report(data["user_id"], "daily_briefing")
    try:
        agent = _get_agent()
        briefing = agent.daily_briefing(data["user_id"])
        save_message(
            data["user_id"],
            data["chat_id"],
            "assistant",
            briefing,
            source="daily_briefing_push",
        )
        send = partial(context.bot.send_message, chat_id=data["chat_id"])
        await send_markdown_safe(send, briefing)
    except Exception:
        logger.exception("daily_briefing_push_failed")


async def _push_anomaly_alert(context):
    data = context.job.data
    await _presync_for_report(data["user_id"], "anomaly_alert")
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
                    save_message(
                        data["user_id"],
                        data["chat_id"],
                        "assistant",
                        text,
                        source="alert_resolved_push",
                    )
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
                save_message(
                    data["user_id"],
                    data["chat_id"],
                    "assistant",
                    text,
                    source="anomaly_alert_push",
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
                save_message(
                    data["user_id"],
                    data["chat_id"],
                    "assistant",
                    text,
                    source="alert_resolved_push",
                )
                await send_markdown_safe(send, text)

    except Exception:
        logger.exception("anomaly_alert_push_failed")


async def _push_weekly_report(context):
    data = context.job.data
    await _presync_for_report(data["user_id"], "weekly_report")
    try:
        agent = _get_agent()
        report = agent.weekly_report(data["user_id"])
        save_message(
            data["user_id"],
            data["chat_id"],
            "assistant",
            report,
            source="weekly_report_push",
        )
        send = partial(context.bot.send_message, chat_id=data["chat_id"])
        await send_markdown_safe(send, report)
    except Exception:
        logger.exception("weekly_report_push_failed")


async def _push_daily_logging_prompt(context):
    data = context.job.data
    user_id = data["user_id"]
    chat_id = data["chat_id"]
    signals: list[str] = list(data.get("signals") or [])
    if not signals:
        return
    try:
        today = local_today()
        already = await asyncio.to_thread(
            _signals_already_logged_today, user_id, today, signals
        )
        pending = [s for s in signals if s not in already]
        if not pending:
            logger.info(
                "daily_logging_prompt_skipped_all_logged",
                user_id=user_id,
                date=str(today),
            )
            return
        text = build_daily_logging_prompt(pending)
        if not text:
            return
        save_message(
            user_id,
            chat_id,
            "assistant",
            text,
            source="daily_logging_prompt_push",
        )
        send = partial(context.bot.send_message, chat_id=chat_id)
        await send_markdown_safe(send, text)
    except Exception:
        logger.exception("daily_logging_prompt_push_failed")

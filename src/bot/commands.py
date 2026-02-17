import logging
from datetime import date

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import BotConfig
from bot.formatters import (
    format_forecast_table,
    send_markdown_safe,
    truncate_for_telegram,
)
from database import get_db_session_context
from models import Anomaly, Prediction

logger = logging.getLogger(__name__)


def _get_agent():
    from agent.agent import HealthAgent

    return HealthAgent()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_markdown_safe(
        update.message.reply_text,
        "*Life-as-Code Health Bot*\n\n"
        "/status — утренний брифинг\n"
        "/week — недельный отчёт\n"
        "/forecast — прогнозы (вес, HRV, сон)\n"
        "/anomalies — последние аномалии\n\n"
        "Или просто напиши вопрос:\n"
        "_Как мой сон за последний месяц?_\n"
        "_Почему HRV упал вчера?_\n"
        "_Сравни январь и февраль по шагам_",
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config: BotConfig = context.bot_data["config"]
    await update.message.reply_chat_action("typing")
    try:
        agent = _get_agent()
        briefing = agent.daily_briefing(config.db_user_id)
        await send_markdown_safe(
            update.message.reply_text, truncate_for_telegram(briefing)
        )
    except Exception:
        logger.exception("cmd_status_failed")
        await update.message.reply_text(
            "Ошибка при генерации брифинга. Попробуй позже."
        )


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config: BotConfig = context.bot_data["config"]
    await update.message.reply_chat_action("typing")
    try:
        agent = _get_agent()
        report = agent.weekly_report(config.db_user_id)
        await send_markdown_safe(
            update.message.reply_text, truncate_for_telegram(report)
        )
    except Exception:
        logger.exception("cmd_week_failed")
        await update.message.reply_text("Ошибка при генерации отчёта. Попробуй позже.")


async def cmd_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config: BotConfig = context.bot_data["config"]

    with get_db_session_context() as db:
        rows = (
            db.query(
                Prediction.metric,
                Prediction.target_date,
                Prediction.horizon_days,
                Prediction.p10,
                Prediction.p50,
                Prediction.p90,
            )
            .filter(
                Prediction.user_id == config.db_user_id,
                Prediction.target_date >= date.today(),
            )
            .order_by(Prediction.metric, Prediction.target_date)
            .all()
        )

    if not rows:
        await update.message.reply_text(
            "Нет активных прогнозов. ML pipeline ещё не запускался."
        )
        return

    text = format_forecast_table(rows)
    await send_markdown_safe(update.message.reply_text, text)


async def cmd_anomalies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config: BotConfig = context.bot_data["config"]

    with get_db_session_context() as db:
        rows = (
            db.query(Anomaly)
            .filter(Anomaly.user_id == config.db_user_id)
            .order_by(Anomaly.date.desc())
            .limit(5)
            .all()
        )

    if not rows:
        await update.message.reply_text("Аномалий не обнаружено")
        return

    top = {
        "date": rows[0].date,
        "anomaly_score": rows[0].anomaly_score,
        "contributing_factors": rows[0].contributing_factors,
    }

    await update.message.reply_chat_action("typing")
    try:
        agent = _get_agent()
        explanation = agent.explain_anomaly(config.db_user_id, top)
    except Exception:
        logger.exception("cmd_anomalies_explain_failed")
        explanation = "(не удалось получить анализ)"

    text = "*Последние аномалии:*\n\n"
    for r in rows:
        emoji = (
            "🔴" if r.anomaly_score > 0.8 else "🟡" if r.anomaly_score > 0.6 else "🟠"
        )
        text += f"{emoji} {r.date}: score {r.anomaly_score:.2f}\n"

    text += f"\n*Разбор последней:*\n{explanation}"
    await send_markdown_safe(update.message.reply_text, truncate_for_telegram(text))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config: BotConfig = context.bot_data["config"]
    await update.message.reply_chat_action("typing")
    try:
        agent = _get_agent()
        question = update.message.text
        answer = agent.ask(config.db_user_id, question)
        await send_markdown_safe(
            update.message.reply_text, truncate_for_telegram(answer)
        )
    except Exception:
        logger.exception("handle_message_failed")
        await update.message.reply_text("Ошибка при обработке вопроса. Попробуй позже.")

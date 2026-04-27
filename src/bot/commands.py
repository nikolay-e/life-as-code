from datetime import date

from telegram import Update
from telegram.ext import ContextTypes

from agent.bot_message_repo import save_message
from agent.conversation import ConversationStore
from bot.config import BotConfig
from bot.formatters import (
    format_forecast_table,
    send_markdown_safe,
    truncate_for_telegram,
)
from database import get_db_session_context
from logging_config import get_logger
from models import Anomaly, Prediction

logger = get_logger(__name__)


def _get_agent():
    from agent.agent import HealthAgent

    return HealthAgent()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Life-as-Code Health Bot\n\n"
        "/status -- утренний брифинг\n"
        "/week -- недельный отчет\n"
        "/forecast -- прогнозы (вес, HRV, сон)\n"
        "/anomalies -- последние аномалии\n"
        "/clear -- очистить историю диалога\n\n"
        "Или просто напиши вопрос:\n"
        "Как мой сон за последний месяц?\n"
        "Почему HRV упал вчера?\n"
        "Сравни январь и февраль по шагам",
    )


def _log_command(
    user_id: int,
    chat_id: int,
    command: str,
    telegram_message_id: int | None,
) -> None:
    save_message(
        user_id,
        chat_id,
        "user",
        command,
        source=command.lstrip("/") + "_command",
        telegram_message_id=telegram_message_id,
    )


def _log_bot_reply(
    user_id: int,
    chat_id: int,
    text: str,
    source: str,
) -> None:
    save_message(user_id, chat_id, "assistant", text, source=source)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config: BotConfig = context.bot_data["config"]
    chat_id = update.effective_chat.id
    _log_command(config.db_user_id, chat_id, "/status", update.message.message_id)
    await update.message.reply_chat_action("typing")
    try:
        agent = _get_agent()
        briefing = agent.daily_briefing(config.db_user_id)
        _log_bot_reply(config.db_user_id, chat_id, briefing, "daily_briefing")
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
    chat_id = update.effective_chat.id
    _log_command(config.db_user_id, chat_id, "/week", update.message.message_id)
    await update.message.reply_chat_action("typing")
    try:
        agent = _get_agent()
        report = agent.weekly_report(config.db_user_id)
        _log_bot_reply(config.db_user_id, chat_id, report, "weekly_report")
        await send_markdown_safe(
            update.message.reply_text, truncate_for_telegram(report)
        )
    except Exception:
        logger.exception("cmd_week_failed")
        await update.message.reply_text("Ошибка при генерации отчёта. Попробуй позже.")


async def cmd_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config: BotConfig = context.bot_data["config"]
    chat_id = update.effective_chat.id
    _log_command(config.db_user_id, chat_id, "/forecast", update.message.message_id)

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
        msg = "Нет активных прогнозов. ML pipeline ещё не запускался."
        _log_bot_reply(config.db_user_id, chat_id, msg, "forecast")
        await update.message.reply_text(msg)
        return

    text = format_forecast_table(rows)
    _log_bot_reply(config.db_user_id, chat_id, text, "forecast")
    await send_markdown_safe(update.message.reply_text, text)


async def cmd_anomalies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config: BotConfig = context.bot_data["config"]
    chat_id = update.effective_chat.id
    _log_command(config.db_user_id, chat_id, "/anomalies", update.message.message_id)

    with get_db_session_context() as db:
        rows = (
            db.query(Anomaly)
            .filter(Anomaly.user_id == config.db_user_id)
            .order_by(Anomaly.date.desc())
            .limit(5)
            .all()
        )

    if not rows:
        msg = "Аномалий не обнаружено"
        _log_bot_reply(config.db_user_id, chat_id, msg, "anomalies")
        await update.message.reply_text(msg)
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
        if r.anomaly_score > 0.8:
            emoji = "🔴"
        elif r.anomaly_score > 0.6:
            emoji = "🟡"
        else:
            emoji = "🟠"
        text += f"{emoji} {r.date}: score {r.anomaly_score:.2f}\n"

    text += f"\n*Разбор последней:*\n{explanation}"
    _log_bot_reply(config.db_user_id, chat_id, text, "anomalies")
    await send_markdown_safe(update.message.reply_text, truncate_for_telegram(text))


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config: BotConfig = context.bot_data["config"]
    store: ConversationStore = context.bot_data["conversations"]
    chat_id = update.effective_chat.id
    store.get(chat_id, user_id=config.db_user_id)
    store.clear(chat_id)
    await update.message.reply_text("История диалога очищена.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config: BotConfig = context.bot_data["config"]
    store: ConversationStore = context.bot_data["conversations"]
    chat_id = update.effective_chat.id

    await update.message.reply_chat_action("typing")
    try:
        agent = _get_agent()
        conversation = store.get(chat_id, user_id=config.db_user_id)
        answer = agent.chat(config.db_user_id, update.message.text, conversation)
        await send_markdown_safe(
            update.message.reply_text, truncate_for_telegram(answer)
        )
    except Exception:
        logger.exception("handle_message_failed")
        await update.message.reply_text("Ошибка при обработке вопроса. Попробуй позже.")

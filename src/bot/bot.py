import functools

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agent.conversation import ConversationStore
from bot.commands import (
    cmd_anomalies,
    cmd_clear,
    cmd_forecast,
    cmd_start,
    cmd_status,
    cmd_week,
    handle_message,
    handle_photo,
)
from bot.config import BotConfig
from bot.scheduler import schedule_push_notifications
from logging_config import get_logger

logger = get_logger(__name__)


def auth_required(func):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        config: BotConfig = context.bot_data["config"]
        if (
            config.allowed_user_ids
            and update.effective_user.id not in config.allowed_user_ids
        ):
            await update.message.reply_text("Unauthorized")
            return
        return await func(update, context)

    return wrapper


def create_bot(config: BotConfig | None = None) -> Application:
    if config is None:
        config = BotConfig()

    app = Application.builder().token(config.token).build()
    app.bot_data["config"] = config
    app.bot_data["conversations"] = ConversationStore()

    app.add_handler(CommandHandler("start", auth_required(cmd_start)))
    app.add_handler(CommandHandler("status", auth_required(cmd_status)))
    app.add_handler(CommandHandler("week", auth_required(cmd_week)))
    app.add_handler(CommandHandler("forecast", auth_required(cmd_forecast)))
    app.add_handler(CommandHandler("anomalies", auth_required(cmd_anomalies)))
    app.add_handler(CommandHandler("clear", auth_required(cmd_clear)))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            auth_required(handle_message),
        )
    )
    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            auth_required(handle_photo),
        )
    )

    schedule_push_notifications(app, config)

    return app

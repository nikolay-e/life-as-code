from bot.bot import create_bot
from bot.config import BotConfig
from logging_config import configure_logging


def main():
    configure_logging()
    config = BotConfig()
    app = create_bot(config)
    app.run_polling()


if __name__ == "__main__":
    main()

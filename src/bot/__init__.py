from bot.bot import create_bot
from bot.config import BotConfig


def main():
    config = BotConfig()
    app = create_bot(config)
    app.run_polling()


if __name__ == "__main__":
    main()

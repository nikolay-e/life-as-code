from logging_config import get_logger

logger = get_logger(__name__)

TELEGRAM_MAX_LENGTH = 4096


def truncate_for_telegram(text: str) -> str:
    if len(text) <= TELEGRAM_MAX_LENGTH:
        return text
    return text[: TELEGRAM_MAX_LENGTH - 20] + "\n\n(обрезано)"


async def send_markdown_safe(bot_send_fn, text: str):
    await bot_send_fn(text=text)


def format_forecast_table(rows: list[tuple]) -> str:
    by_metric: dict[str, list] = {}
    for metric, target_date, horizon, p10, p50, p90 in rows:
        if metric not in by_metric:
            by_metric[metric] = []
        by_metric[metric].append((target_date, horizon, p10, p50, p90))

    units = {
        "weight": "kg",
        "hrv": "ms",
        "rhr": "bpm",
        "sleep_total": "min",
        "steps": "",
    }

    text = "Прогнозы:\n\n"
    for metric, preds in by_metric.items():
        unit = units.get(metric, "")
        text += f"{metric}\n"
        for target_date, horizon, p10, p50, p90 in preds:
            text += f"  +{horizon}d ({target_date}): {p50:.0f} {unit} [{p10:.0f}-{p90:.0f}]\n"
        text += "\n"

    return text

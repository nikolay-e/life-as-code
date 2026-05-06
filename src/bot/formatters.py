import html

from telegram.constants import ParseMode

from logging_config import get_logger

logger = get_logger(__name__)

TELEGRAM_MAX_LENGTH = 4096
SAFE_TELEGRAM_LENGTH = 4000


def truncate_for_telegram(text: str) -> str:
    if len(text) <= TELEGRAM_MAX_LENGTH:
        return text
    return text[: TELEGRAM_MAX_LENGTH - 20] + "\n\n(обрезано)"


def escape_html(text: str) -> str:
    return html.escape(text, quote=False)


def _join_with(buf: str, segment: str, sep: str) -> str:
    return f"{buf}{sep}{segment}" if buf else segment


def _flush_oversize_paragraph(
    chunks: list[str], buf: str, paragraph: str, limit: int
) -> str:
    for line in paragraph.splitlines():
        candidate = _join_with(buf, line, "\n")
        if len(candidate) > limit and buf:
            chunks.append(buf)
            buf = line
        else:
            buf = candidate
    return buf


def split_for_telegram(text: str, limit: int = SAFE_TELEGRAM_LENGTH) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    buf = ""
    for paragraph in text.split("\n\n"):
        candidate = _join_with(buf, paragraph, "\n\n")
        if len(candidate) <= limit:
            buf = candidate
            continue
        if buf:
            chunks.append(buf)
            buf = ""
        if len(paragraph) > limit:
            buf = _flush_oversize_paragraph(chunks, buf, paragraph, limit)
        else:
            buf = paragraph
    if buf:
        chunks.append(buf)
    return chunks


async def send_markdown_safe(bot_send_fn, text: str):
    escaped = escape_html(text)
    for chunk in split_for_telegram(escaped):
        try:
            await bot_send_fn(text=chunk, parse_mode=ParseMode.HTML)
        except Exception:
            logger.exception("send_html_failed_falling_back_to_plain")
            await bot_send_fn(text=chunk)


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

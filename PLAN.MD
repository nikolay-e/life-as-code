# life-as-code: AI Architecture

## Принцип: каждой задаче — правильный инструмент

```
┌─────────────────────────────────────────────────────────┐
│                    PostgreSQL (3 года данных)            │
└──────┬──────────────────┬───────────────────┬───────────┘
       │                  │                   │
       ▼                  ▼                   ▼
┌──────────────┐  ┌───────────────┐  ┌────────────────┐
│   Chronos    │  │  Isolation    │  │  LLM Agent     │
│  (fine-tuned)│  │  Forest       │  │  (Claude API)  │
│              │  │               │  │                │
│  ЧТО БУДЕТ   │  │  ЧТО СТРАННО  │  │  ЧТО ЭТО ЗНАЧИТ│
│              │  │               │  │                │
│  forecast    │  │  anomaly      │  │  interpret     │
│  weight +14d │  │  detection    │  │  summarize     │
│  HRV trend   │  │  flag days    │  │  answer Q&A    │
│  sleep pred  │  │  z-scores     │  │  weekly report │
└──────┬───────┘  └───────┬───────┘  └────────┬───────┘
       │                  │                   │
       └──────────┬───────┘                   │
                  │                           │
                  ▼                           │
       ┌──────────────────┐                   │
       │  predictions DB  │───────────────────┘
       │  anomalies DB    │
       │  insights DB     │
       └────────┬─────────┘
                │
                ▼
       ┌──────────────────┐
       │  Telegram Bot    │
       │                  │
       │  ДОСТАВКА        │
       │                  │
       │  утренний брифинг│
       │  алерты аномалий │
       │  weekly report   │
       │  Q&A чат         │
       └──────────────────┘
```

### Что куда:

| Задача | Технология | Почему |
|--------|-----------|--------|
| Предсказание веса/HRV/сна на N дней | **Chronos** (fine-tuned) | Числовой forecast с confidence intervals. LLM не умеет считать тренды — hallucinate numbers |
| Обнаружение аномальных дней | **Isolation Forest** | Быстро, объяснимо (z-scores), детерминистично. LLM не видит статистическую картину всего dataset |
| "Почему у меня вчера HRV упал?" | **LLM** | Нужен контекст: тренировка накануне, мало сна, алкоголь. LLM связывает факты из разных метрик |
| Утренний брифинг | **LLM** | Генерация текста из структурированных данных — core competency LLM |
| Weekly/monthly отчёт с инсайтами | **LLM** | Нарратив, сравнения, рекомендации — не таблица чисел, а человеческий текст |
| "Как мой сон изменился за последний месяц?" | **LLM + SQL** | LLM генерирует SQL, получает данные, интерпретирует результат |
| Алерт: "Ты заболеваешь" | **Isolation Forest → LLM** | IF флагает аномалию, LLM объясняет что конкретно не так |
| Доставка всего вышеперечисленного | **Telegram Bot** | Push-канал + интерактивный Q&A |

---

## Компоненты

### 1. ML Pipeline (уже спланирован)

Без изменений — `src/ml/` с Chronos fine-tuned + Isolation Forest.
Выход: таблицы `predictions` и `anomalies` в Postgres.

### 2. LLM Agent — `src/agent/`

```
src/agent/
├── __init__.py
├── config.py          # API key, model, system prompt
├── context.py         # сборка контекста из DB для промпта
├── tools.py           # tool definitions для function calling
├── agent.py           # основной agent loop
├── prompts.py         # system prompts для разных задач
└── reports.py         # генерация daily/weekly отчётов
```

#### `src/agent/config.py`

```python
from dataclasses import dataclass

@dataclass
class AgentConfig:
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1024
    # Sonnet для daily tasks — быстро и дёшево
    # Можно переключить на Opus для deep analysis
```

#### `src/agent/context.py` — сборка данных для промпта

```python
from datetime import date, timedelta
from src.database import get_db_connection


def build_daily_context(user_id: int, target_date: date | None = None) -> dict:
    """Собрать все данные за день + контекст за последние 7 дней для LLM."""
    if target_date is None:
        target_date = date.today()

    conn = get_db_connection()
    ctx = {}

    # Вчерашние метрики
    ctx["today"] = _get_day_metrics(conn, user_id, target_date)

    # 7-day rolling averages для сравнения
    ctx["week_avg"] = _get_rolling_averages(conn, user_id, target_date, days=7)

    # 30-day rolling averages
    ctx["month_avg"] = _get_rolling_averages(conn, user_id, target_date, days=30)

    # Активные прогнозы
    ctx["forecasts"] = _get_active_forecasts(conn, user_id, target_date)

    # Аномалии за последние 3 дня
    ctx["recent_anomalies"] = _get_recent_anomalies(conn, user_id, target_date, days=3)

    # Последние тренировки
    ctx["recent_workouts"] = _get_recent_workouts(conn, user_id, target_date, days=3)

    conn.close()
    return ctx


def _get_day_metrics(conn, user_id: int, d: date) -> dict:
    """All metrics for a single day."""
    metrics = {}

    for table, columns in [
        ("steps", "total_steps, total_distance, active_minutes"),
        ("sleep", "total_sleep_minutes, deep_minutes, rem_minutes, light_minutes, awake_minutes, sleep_score"),
        ("heart_rate", "resting_hr, max_hr, avg_hr"),
        ("hrv", "hrv_avg"),
        ("weight", "weight_kg, body_fat_pct"),
        ("energy", "active_energy"),
    ]:
        cur = conn.cursor()
        cur.execute(
            f"SELECT {columns} FROM {table} WHERE user_id = %s AND date = %s LIMIT 1",
            (user_id, d)
        )
        row = cur.fetchone()
        if row:
            cols = [desc[0] for desc in cur.description]
            metrics[table] = dict(zip(cols, row))
        cur.close()

    return metrics


def _get_rolling_averages(conn, user_id: int, end_date: date, days: int) -> dict:
    start = end_date - timedelta(days=days)
    avgs = {}

    queries = {
        "steps": "SELECT AVG(total_steps) FROM steps WHERE user_id=%s AND date BETWEEN %s AND %s",
        "sleep": "SELECT AVG(total_sleep_minutes), AVG(deep_minutes) FROM sleep WHERE user_id=%s AND date BETWEEN %s AND %s",
        "rhr": "SELECT AVG(resting_hr) FROM heart_rate WHERE user_id=%s AND date BETWEEN %s AND %s",
        "hrv": "SELECT AVG(hrv_avg) FROM hrv WHERE user_id=%s AND date BETWEEN %s AND %s",
        "weight": "SELECT AVG(weight_kg) FROM weight WHERE user_id=%s AND date BETWEEN %s AND %s",
    }

    cur = conn.cursor()
    for key, query in queries.items():
        cur.execute(query, (user_id, start, end_date))
        row = cur.fetchone()
        if row:
            avgs[key] = [round(float(v), 1) if v else None for v in row]
    cur.close()

    return avgs


def _get_active_forecasts(conn, user_id: int, d: date) -> list[dict]:
    cur = conn.cursor()
    cur.execute("""
        SELECT metric, target_date, horizon_days, p10, p50, p90
        FROM predictions
        WHERE user_id = %s AND target_date >= %s
        ORDER BY metric, target_date
    """, (user_id, d))
    cols = [desc[0] for desc in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.close()
    return rows


def _get_recent_anomalies(conn, user_id: int, d: date, days: int) -> list[dict]:
    cur = conn.cursor()
    cur.execute("""
        SELECT date, anomaly_score, contributing_factors
        FROM anomalies
        WHERE user_id = %s AND date >= %s - interval '%s days' AND date <= %s
        ORDER BY date DESC
    """, (user_id, d, days, d))
    cols = [desc[0] for desc in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.close()
    return rows


def _get_recent_workouts(conn, user_id: int, d: date, days: int) -> list[dict]:
    cur = conn.cursor()
    cur.execute("""
        SELECT date, activity_type, duration_minutes, avg_hr, max_hr, calories
        FROM garmin_activities
        WHERE user_id = %s AND date >= %s - interval '%s days' AND date <= %s
        ORDER BY date DESC
    """, (user_id, d, days, d))
    cols = [desc[0] for desc in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.close()
    return rows
```

#### `src/agent/tools.py` — function calling для Q&A

```python
TOOLS = [
    {
        "name": "query_health_data",
        "description": "Query the user's health database. Returns raw data for a specific metric and date range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": ["steps", "sleep", "heart_rate", "hrv", "weight", "energy", "workouts"],
                    "description": "Which health metric to query"
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date (YYYY-MM-DD)"
                },
                "end_date": {
                    "type": "string",
                    "description": "End date (YYYY-MM-DD)"
                },
                "aggregation": {
                    "type": "string",
                    "enum": ["daily", "weekly", "monthly"],
                    "description": "How to aggregate the data"
                }
            },
            "required": ["metric", "start_date", "end_date"]
        }
    },
    {
        "name": "get_predictions",
        "description": "Get ML forecasts for a health metric.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": ["weight", "hrv", "rhr", "sleep_total", "steps"]
                },
                "horizon_days": {
                    "type": "integer",
                    "enum": [1, 7, 14]
                }
            },
            "required": ["metric"]
        }
    },
    {
        "name": "compare_periods",
        "description": "Compare health metrics between two time periods.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": ["steps", "sleep", "heart_rate", "hrv", "weight"]
                },
                "period_a_start": {"type": "string"},
                "period_a_end": {"type": "string"},
                "period_b_start": {"type": "string"},
                "period_b_end": {"type": "string"}
            },
            "required": ["metric", "period_a_start", "period_a_end", "period_b_start", "period_b_end"]
        }
    }
]
```

#### `src/agent/prompts.py`

```python
SYSTEM_PROMPT = """You are a personal health analytics assistant. You have access to
the user's wearable health data (Garmin, Apple Watch, WHOOP, Eight Sleep) spanning 3 years.

Your role:
- Interpret health metrics in context (not just read numbers)
- Spot patterns the user might miss (sleep↔training correlations, recovery trends)
- Give actionable insights, not generic health advice
- Be direct and concise — this goes to Telegram, not a medical report

You know the user is a software engineer, trains regularly, and tracks data obsessively.
Don't explain what HRV is — explain what HIS HRV means today.

Data conventions:
- Sleep: minutes (420 = 7 hours)
- Distance: meters
- Weight: kg
- HRV: ms (RMSSD)
- RHR: bpm

When comparing to averages, use percentage change and plain language.
Never say "consult a doctor" unless something is genuinely alarming.
Respond in Russian."""


DAILY_BRIEFING_PROMPT = """Generate a concise morning health briefing based on the data below.

Structure:
1. One-line overall status (emoji + short verdict)
2. Key metrics vs 7-day average (only mention notable deviations ≥10%)
3. If anomaly detected — explain what's off and likely why
4. If forecast available — mention notable trends
5. One actionable recommendation for today

Keep it under 200 words. Telegram format (markdown).

Data:
{context_json}"""


WEEKLY_REPORT_PROMPT = """Generate a weekly health report based on the data below.

Structure:
1. Week summary (overall trend: improving/stable/declining)
2. Best day and worst day — what made them different
3. Sleep quality trend
4. Training load vs recovery balance
5. Weight trend + forecast
6. Top insight the user probably didn't notice
7. One goal for next week

Keep it under 400 words. Telegram format (markdown).

Data:
{context_json}"""


ANOMALY_ALERT_PROMPT = """An anomaly was detected in health data. Explain it.

Anomaly date: {date}
Anomaly score: {score} (0-1, higher = more unusual)
Contributing factors (z-scores): {factors}

Recent context (last 3 days of data):
{recent_context}

Recent workouts:
{workouts}

Be specific about what's unusual and hypothesize WHY.
If multiple metrics are off in the same direction, note the pattern.
Keep it under 100 words."""
```

#### `src/agent/agent.py` — основной agent

```python
import json
import anthropic

from src.agent.config import AgentConfig
from src.agent.context import build_daily_context, build_weekly_context
from src.agent.tools import TOOLS, execute_tool
from src.agent.prompts import SYSTEM_PROMPT, DAILY_BRIEFING_PROMPT, WEEKLY_REPORT_PROMPT, ANOMALY_ALERT_PROMPT

import structlog
logger = structlog.get_logger()


class HealthAgent:
    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self.client = anthropic.Anthropic()  # ANTHROPIC_API_KEY from env

    def daily_briefing(self, user_id: int) -> str:
        """Generate morning health briefing."""
        ctx = build_daily_context(user_id)
        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": DAILY_BRIEFING_PROMPT.format(
                    context_json=json.dumps(ctx, default=str, ensure_ascii=False)
                ),
            }],
        )
        return response.content[0].text

    def weekly_report(self, user_id: int) -> str:
        """Generate weekly health report."""
        ctx = build_weekly_context(user_id)
        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens * 2,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": WEEKLY_REPORT_PROMPT.format(
                    context_json=json.dumps(ctx, default=str, ensure_ascii=False)
                ),
            }],
        )
        return response.content[0].text

    def explain_anomaly(self, user_id: int, anomaly: dict) -> str:
        """Explain a detected anomaly in natural language."""
        ctx = build_daily_context(user_id, target_date=anomaly["date"])
        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": ANOMALY_ALERT_PROMPT.format(
                    date=anomaly["date"],
                    score=anomaly["anomaly_score"],
                    factors=json.dumps(anomaly["contributing_factors"]),
                    recent_context=json.dumps(ctx["today"], default=str),
                    workouts=json.dumps(ctx["recent_workouts"], default=str),
                ),
            }],
        )
        return response.content[0].text

    def ask(self, user_id: int, question: str) -> str:
        """Answer a free-form question about health data using tools."""
        ctx = build_daily_context(user_id)
        messages = [{
            "role": "user",
            "content": f"Context (today's data): {json.dumps(ctx, default=str, ensure_ascii=False)}\n\nQuestion: {question}",
        }]

        # Agentic loop: let Claude call tools as needed
        while True:
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            # If no tool use, return text
            if response.stop_reason == "end_turn":
                text_blocks = [b.text for b in response.content if b.type == "text"]
                return "\n".join(text_blocks)

            # Process tool calls
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(user_id, block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    })

            messages.append({"role": "user", "content": tool_results})
```

### 3. Telegram Bot — `src/bot/`

```
src/bot/
├── __init__.py
├── config.py
├── bot.py             # python-telegram-bot handlers
├── commands.py        # /status, /week, /ask, /forecast
├── scheduler.py       # push notifications schedule
└── formatters.py      # markdown formatting for Telegram
```

#### `src/bot/config.py`

```python
from dataclasses import dataclass
import os

@dataclass
class BotConfig:
    token: str = ""
    allowed_user_ids: list[int] = None  # Telegram user IDs — whitelist
    db_user_id: int = 1  # mapping: Telegram user → DB user

    def __post_init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", self.token)
        allowed = os.getenv("TELEGRAM_ALLOWED_USERS", "")
        if allowed and self.allowed_user_ids is None:
            self.allowed_user_ids = [int(x) for x in allowed.split(",")]
```

#### `src/bot/bot.py`

```python
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes,
)

from src.bot.config import BotConfig
from src.bot.commands import (
    cmd_start, cmd_status, cmd_week, cmd_forecast,
    cmd_anomalies, handle_message,
)
from src.bot.scheduler import schedule_push_notifications

logger = logging.getLogger(__name__)


def auth_required(func):
    """Decorator: only allowed Telegram user IDs can use the bot."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        config: BotConfig = context.bot_data["config"]
        if config.allowed_user_ids and update.effective_user.id not in config.allowed_user_ids:
            await update.message.reply_text("⛔ Unauthorized")
            return
        return await func(update, context)
    return wrapper


def create_bot(config: BotConfig | None = None) -> Application:
    if config is None:
        config = BotConfig()

    app = Application.builder().token(config.token).build()
    app.bot_data["config"] = config

    # Commands
    app.add_handler(CommandHandler("start", auth_required(cmd_start)))
    app.add_handler(CommandHandler("status", auth_required(cmd_status)))
    app.add_handler(CommandHandler("week", auth_required(cmd_week)))
    app.add_handler(CommandHandler("forecast", auth_required(cmd_forecast)))
    app.add_handler(CommandHandler("anomalies", auth_required(cmd_anomalies)))

    # Free-form questions → LLM agent
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        auth_required(handle_message),
    ))

    # Scheduled push notifications
    schedule_push_notifications(app, config)

    return app
```

#### `src/bot/commands.py`

```python
import json
from telegram import Update
from telegram.ext import ContextTypes

from src.agent.agent import HealthAgent
from src.bot.formatters import format_forecast_table, truncate_for_telegram

agent = HealthAgent()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏥 *Life-as-Code Health Bot*\n\n"
        "Commands:\n"
        "/status — утренний брифинг\n"
        "/week — недельный отчёт\n"
        "/forecast — прогнозы (weight, HRV, sleep)\n"
        "/anomalies — последние аномалии\n\n"
        "Или просто напиши вопрос:\n"
        "_Как мой сон за последний месяц?_\n"
        "_Почему HRV упал вчера?_\n"
        "_Сравни январь и февраль по шагам_",
        parse_mode="Markdown",
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Morning briefing via LLM."""
    config = context.bot_data["config"]
    await update.message.reply_chat_action("typing")

    briefing = agent.daily_briefing(config.db_user_id)
    await update.message.reply_text(
        truncate_for_telegram(briefing),
        parse_mode="Markdown",
    )


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Weekly report via LLM."""
    config = context.bot_data["config"]
    await update.message.reply_chat_action("typing")

    report = agent.weekly_report(config.db_user_id)
    await update.message.reply_text(
        truncate_for_telegram(report),
        parse_mode="Markdown",
    )


async def cmd_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show active ML forecasts."""
    config = context.bot_data["config"]
    from src.database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT metric, target_date, horizon_days, p10, p50, p90
        FROM predictions
        WHERE user_id = %s AND target_date >= CURRENT_DATE
        ORDER BY metric, target_date
    """, (config.db_user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        await update.message.reply_text("Нет активных прогнозов. ML pipeline ещё не запускался.")
        return

    text = format_forecast_table(rows)
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_anomalies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent anomalies with LLM explanation."""
    config = context.bot_data["config"]
    from src.database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT date, anomaly_score, contributing_factors
        FROM anomalies
        WHERE user_id = %s
        ORDER BY date DESC LIMIT 5
    """, (config.db_user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        await update.message.reply_text("Аномалий не обнаружено 👍")
        return

    # LLM объясняет топ-аномалию
    top = {"date": rows[0][0], "anomaly_score": rows[0][1], "contributing_factors": rows[0][2]}
    explanation = agent.explain_anomaly(config.db_user_id, top)

    text = f"⚠️ *Последние аномалии:*\n\n"
    for date, score, factors in rows:
        emoji = "🔴" if score > 0.8 else "🟡" if score > 0.6 else "🟠"
        text += f"{emoji} {date}: score {score:.2f}\n"

    text += f"\n*Разбор последней:*\n{explanation}"
    await update.message.reply_text(
        truncate_for_telegram(text),
        parse_mode="Markdown",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Free-form question → LLM agent with tools."""
    config = context.bot_data["config"]
    await update.message.reply_chat_action("typing")

    question = update.message.text
    answer = agent.ask(config.db_user_id, question)

    await update.message.reply_text(
        truncate_for_telegram(answer),
        parse_mode="Markdown",
    )
```

#### `src/bot/scheduler.py` — push notifications

```python
from datetime import time
from telegram.ext import Application
from src.bot.config import BotConfig
from src.agent.agent import HealthAgent

agent = HealthAgent()


def schedule_push_notifications(app: Application, config: BotConfig):
    """
    Scheduled messages:
    - Daily 07:00  → morning briefing
    - Daily 22:00  → anomaly alert (if detected today)
    - Monday 09:00 → weekly report
    """
    job_queue = app.job_queue

    if not config.allowed_user_ids:
        return

    chat_id = config.allowed_user_ids[0]  # primary user

    # Morning briefing
    job_queue.run_daily(
        _push_daily_briefing,
        time=time(hour=7, minute=0),
        data={"chat_id": chat_id, "user_id": config.db_user_id},
        name="daily_briefing",
    )

    # Anomaly check (evening)
    job_queue.run_daily(
        _push_anomaly_alert,
        time=time(hour=22, minute=0),
        data={"chat_id": chat_id, "user_id": config.db_user_id},
        name="anomaly_alert",
    )

    # Weekly report (Monday morning)
    job_queue.run_daily(
        _push_weekly_report,
        time=time(hour=9, minute=0),
        days=(0,),  # Monday
        data={"chat_id": chat_id, "user_id": config.db_user_id},
        name="weekly_report",
    )


async def _push_daily_briefing(context):
    data = context.job.data
    briefing = agent.daily_briefing(data["user_id"])
    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=f"☀️ *Утренний брифинг*\n\n{briefing}",
        parse_mode="Markdown",
    )


async def _push_anomaly_alert(context):
    data = context.job.data
    from src.database import get_db_connection
    from datetime import date

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT date, anomaly_score, contributing_factors
        FROM anomalies
        WHERE user_id = %s AND date = %s
    """, (data["user_id"], date.today()))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return  # no anomaly today — no alert

    anomaly = {"date": row[0], "anomaly_score": row[1], "contributing_factors": row[2]}
    explanation = agent.explain_anomaly(data["user_id"], anomaly)

    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=f"⚠️ *Аномалия обнаружена*\n\nScore: {row[1]:.2f}\n\n{explanation}",
        parse_mode="Markdown",
    )


async def _push_weekly_report(context):
    data = context.job.data
    report = agent.weekly_report(data["user_id"])
    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=f"📊 *Недельный отчёт*\n\n{report}",
        parse_mode="Markdown",
    )
```

#### `src/bot/formatters.py`

```python
TELEGRAM_MAX_LENGTH = 4096


def truncate_for_telegram(text: str) -> str:
    if len(text) <= TELEGRAM_MAX_LENGTH:
        return text
    return text[:TELEGRAM_MAX_LENGTH - 20] + "\n\n_(обрезано)_"


def format_forecast_table(rows: list[tuple]) -> str:
    """Format prediction rows as readable Telegram message."""
    by_metric = {}
    for metric, target_date, horizon, p10, p50, p90 in rows:
        if metric not in by_metric:
            by_metric[metric] = []
        by_metric[metric].append((target_date, horizon, p10, p50, p90))

    units = {
        "weight": "кг", "hrv": "мс", "rhr": "уд/мин",
        "sleep_total": "мин", "steps": "шагов",
    }

    text = "📈 *Прогнозы:*\n\n"
    for metric, preds in by_metric.items():
        unit = units.get(metric, "")
        text += f"*{metric}*\n"
        for target_date, horizon, p10, p50, p90 in preds:
            text += f"  +{horizon}d ({target_date}): {p50:.0f} {unit} [{p10:.0f}–{p90:.0f}]\n"
        text += "\n"

    return text
```

---

## Docker / Dependencies

### Обновлённый `pyproject.toml`

```toml
[project.optional-dependencies]
ml = [
    "chronos-forecasting>=2.1.0",
    "torch>=2.2,<3",
    "transformers>=4.40",
    "scikit-learn>=1.5",
    "pandas>=2.2",
]
agent = [
    "anthropic>=0.40",
]
bot = [
    "python-telegram-bot[job-scheduler]>=21.0",
]
all = [
    "life-as-code[ml,agent,bot]",
]
```

### `docker-compose.override.yml`

```yaml
services:
  ml:
    build:
      context: .
      target: ml
    command: >
      sh -c "
        echo '=== Initial training ===';
        python -m src.ml.run --user-id 1 --train;
        echo '=== Daily loop ===';
        while true; do
          python -m src.ml.run --user-id 1;
          sleep 86400;
        done
      "
    environment:
      - DATABASE_URL=${DATABASE_URL}
    volumes:
      - ml-models:/app/models
    deploy:
      resources:
        limits:
          memory: 2G

  bot:
    build:
      context: .
      target: bot
    command: python -m src.bot
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_ALLOWED_USERS=${TELEGRAM_ALLOWED_USERS}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 256M  # bot + agent — lightweight

volumes:
  ml-models:
```

### Новые env vars в `.env`

```bash
# Telegram
TELEGRAM_BOT_TOKEN=...          # from @BotFather
TELEGRAM_ALLOWED_USERS=123456   # your Telegram user ID

# Claude API
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Стоимость Claude API

Sonnet для daily/weekly reports + ad-hoc Q&A:

| Задача | Tokens in/out | Calls/month | Cost/month |
|--------|-------------|-------------|------------|
| Daily briefing | ~2000/500 | 30 | ~$0.25 |
| Weekly report | ~4000/800 | 4 | ~$0.06 |
| Anomaly alerts | ~1500/300 | ~10 | ~$0.05 |
| Ad-hoc questions | ~2000/500 | ~30 | ~$0.25 |
| **Total** | | | **~$0.60/мес** |

---

## Полный порядок реализации

| Шаг | Что | Время |
|-----|-----|-------|
| **ML Pipeline** | | |
| 1 | Migration 014 (predictions + anomalies tables) | 1ч |
| 2 | `src/ml/` — config, data_loader, train, predict, anomaly, run | 5ч |
| 3 | Первый прогон `--train`, проверка MAE | 1ч |
| **LLM Agent** | | |
| 4 | `src/agent/context.py` — сборка данных из DB | 2ч |
| 5 | `src/agent/tools.py` + `agent.py` — agent loop с function calling | 2ч |
| 6 | `src/agent/prompts.py` + `reports.py` — daily/weekly промпты | 1ч |
| **Telegram Bot** | | |
| 7 | BotFather → token, `src/bot/bot.py` + commands | 2ч |
| 8 | `src/bot/scheduler.py` — push notifications | 1ч |
| 9 | Тестирование: /status, /week, free-form Q&A | 1ч |
| **Integration** | | |
| 10 | Docker compose, env vars, e2e test | 2ч |
| 11 | Frontend: confidence bands + anomaly markers (опционально) | 4ч |
| **Итого** | | **~22ч** |

Frontend (шаг 11) опционален — Telegram bot может полностью заменить
dashboard для daily use. Dashboard остаётся для deep dive и визуализации.

---

## Итоговая файловая структура

```
src/
├── ml/                    # числовые предсказания
│   ├── config.py
│   ├── data_loader.py
│   ├── train.py           # fine-tune Chronos
│   ├── predict.py         # forecasting
│   ├── anomaly.py         # Isolation Forest
│   └── run.py
├── agent/                 # интерпретация и NL
│   ├── config.py
│   ├── context.py         # DB → structured context
│   ├── tools.py           # function calling definitions
│   ├── agent.py           # Claude API agent loop
│   ├── prompts.py         # system/task prompts
│   └── reports.py         # daily/weekly generators
├── bot/                   # доставка
│   ├── config.py
│   ├── bot.py             # telegram handlers
│   ├── commands.py        # /status /week /forecast
│   ├── scheduler.py       # push notifications
│   └── formatters.py      # telegram markdown
├── app.py                 # existing Flask
├── api.py                 # existing + new /predictions, /anomalies
└── ...
```

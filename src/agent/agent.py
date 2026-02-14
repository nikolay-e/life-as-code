import json
from typing import Any

import anthropic
import structlog

from agent.config import AgentConfig
from agent.context import build_daily_context, build_weekly_context
from agent.prompts import (
    ANOMALY_ALERT_PROMPT,
    DAILY_BRIEFING_PROMPT,
    SYSTEM_PROMPT,
    WEEKLY_REPORT_PROMPT,
)
from agent.tools import TOOLS, execute_tool

logger = structlog.get_logger()


class HealthAgent:
    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self.client = anthropic.Anthropic()

    def daily_briefing(self, user_id: int) -> str:
        ctx = build_daily_context(user_id)
        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": DAILY_BRIEFING_PROMPT.format(
                        context_json=json.dumps(ctx, default=str, ensure_ascii=False)
                    ),
                }
            ],
        )
        return str(response.content[0].text)

    def weekly_report(self, user_id: int) -> str:
        ctx = build_weekly_context(user_id)
        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens * 2,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": WEEKLY_REPORT_PROMPT.format(
                        context_json=json.dumps(ctx, default=str, ensure_ascii=False)
                    ),
                }
            ],
        )
        return str(response.content[0].text)

    def explain_anomaly(self, user_id: int, anomaly: dict) -> str:
        ctx = build_daily_context(user_id, target_date=anomaly["date"])
        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": ANOMALY_ALERT_PROMPT.format(
                        date=anomaly["date"],
                        score=anomaly["anomaly_score"],
                        factors=json.dumps(anomaly["contributing_factors"]),
                        recent_context=json.dumps(ctx["today"], default=str),
                        workouts=json.dumps(ctx["recent_workouts"], default=str),
                    ),
                }
            ],
        )
        return str(response.content[0].text)

    def ask(self, user_id: int, question: str) -> str:
        ctx = build_daily_context(user_id)
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": (
                    f"Context (today's data): "
                    f"{json.dumps(ctx, default=str, ensure_ascii=False)}"
                    f"\n\nQuestion: {question}"
                ),
            }
        ]

        for _ in range(10):
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                text_blocks = [b.text for b in response.content if b.type == "text"]
                return "\n".join(text_blocks)

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info("tool_call", tool=block.name, input=block.input)
                    result = execute_tool(user_id, block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, default=str),
                        }
                    )

            messages.append({"role": "user", "content": tool_results})

        return "Не удалось получить ответ — превышен лимит вызовов инструментов."

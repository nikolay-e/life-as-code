import json
from datetime import date, datetime
from typing import Any

import anthropic
import structlog

from agent.api_client import create_with_retry
from agent.config import AgentConfig
from agent.context import build_chat_context, build_daily_context, build_weekly_context
from agent.conversation import Conversation
from agent.prompts import (
    ANOMALY_ALERT_PROMPT,
    CHAT_ADDENDUM,
    DAILY_BRIEFING_PROMPT,
    SYSTEM_PROMPT,
    WEEKLY_REPORT_PROMPT,
)
from agent.tools import TOOLS, execute_tool

logger = structlog.get_logger()


def _serialize_context(ctx: dict | list) -> str:
    def _strict_default(obj: object) -> object:
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if hasattr(obj, "model_dump"):
            return obj.model_dump(exclude_none=True)
        raise TypeError(f"Cannot serialize {type(obj).__name__}: {obj!r}")

    return json.dumps(ctx, default=_strict_default, ensure_ascii=False)


class HealthAgent:
    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self.client = anthropic.Anthropic()

    def daily_briefing(self, user_id: int) -> str:
        ctx = build_daily_context(user_id)
        response = create_with_retry(
            self.client,
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": DAILY_BRIEFING_PROMPT.format(
                        current_datetime=ctx.get("current_datetime", ""),
                        context_json=_serialize_context(ctx),
                    ),
                }
            ],
        )
        return str(response.content[0].text)

    def weekly_report(self, user_id: int) -> str:
        ctx = build_weekly_context(user_id)
        response = create_with_retry(
            self.client,
            model=self.config.model,
            max_tokens=self.config.max_tokens * 2,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": WEEKLY_REPORT_PROMPT.format(
                        current_datetime=ctx.get("current_datetime", ""),
                        context_json=_serialize_context(ctx),
                    ),
                }
            ],
        )
        return str(response.content[0].text)

    def explain_anomaly(self, user_id: int, anomaly: dict) -> str:
        ctx = build_daily_context(user_id, target_date=anomaly.get("date"))
        response = create_with_retry(
            self.client,
            model=self.config.model,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": ANOMALY_ALERT_PROMPT.format(
                        current_datetime=ctx.get("current_datetime", ""),
                        date=anomaly.get("date", ""),
                        score=anomaly.get("anomaly_score", ""),
                        factors=json.dumps(anomaly.get("contributing_factors", {})),
                        recent_context=_serialize_context(ctx.get("recent_days", [])),
                        workouts=_serialize_context(ctx.get("recent_workouts", [])),
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
                    f"{_serialize_context(ctx)}"
                    f"\n\nQuestion: {question}"
                ),
            }
        ]

        for _ in range(10):
            response = create_with_retry(
                self.client,
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
                            "content": (
                                _serialize_context(result)
                                if isinstance(result, dict)
                                else json.dumps(result)
                            ),
                        }
                    )

            messages.append({"role": "user", "content": tool_results})

        return "Не удалось получить ответ — превышен лимит вызовов инструментов."

    def chat(self, user_id: int, message: str, conversation: Conversation) -> str:
        if conversation.needs_context_refresh():
            context_summary = build_chat_context(user_id)
            conversation.add_user_message(f"[Health context update]\n{context_summary}")
            conversation.add_assistant_message("Обновил данные. Что хочешь узнать?")
            conversation.mark_context_refreshed()

        conversation.add_user_message(message)
        messages = conversation.get_messages()

        for _ in range(10):
            response = create_with_retry(
                self.client,
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=SYSTEM_PROMPT + CHAT_ADDENDUM,
                tools=TOOLS,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                text_blocks = [b.text for b in response.content if b.type == "text"]
                answer = "\n".join(text_blocks)
                conversation.add_assistant_message(response.content)
                return answer

            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info("tool_call", tool=block.name, input=block.input)
                    result = execute_tool(user_id, block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": (
                                _serialize_context(result)
                                if isinstance(result, dict)
                                else json.dumps(result)
                            ),
                        }
                    )

            messages.append({"role": "user", "content": tool_results})
            conversation.add_tool_exchange(assistant_content, tool_results)

        return "Не удалось получить ответ — превышен лимит вызовов инструментов."

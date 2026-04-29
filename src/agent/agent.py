import json
from collections.abc import Callable
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
        self.client = anthropic.Anthropic(max_retries=0)

    def daily_briefing(self, user_id: int) -> str:
        ctx = build_daily_context(user_id)
        response = create_with_retry(
            self.client,
            model=self.config.model,
            max_tokens=256,
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
            max_tokens=384,
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
            max_tokens=128,
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

    def _run_tool_loop(
        self,
        user_id: int,
        messages: list[dict[str, Any]],
        system_prompt: str,
        max_turns: int = 10,
        *,
        max_tokens: int | None = None,
        on_tool_exchange: (
            Callable[[list, list[dict[str, Any]] | None, dict[str, Any]], None] | None
        ) = None,
    ) -> str:
        effective_max_tokens = max_tokens or self.config.max_tokens
        for _ in range(max_turns):
            response = create_with_retry(
                self.client,
                model=self.config.model,
                max_tokens=effective_max_tokens,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            )
            meta = self._extract_response_meta(response)

            if response.stop_reason == "end_turn":
                return self._extract_final_text(
                    response.content, on_tool_exchange, meta
                )

            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results = self._execute_tool_calls(user_id, response.content)

            if not tool_results:
                return self._extract_final_text(
                    response.content, on_tool_exchange, meta
                )

            messages.append({"role": "user", "content": tool_results})
            if on_tool_exchange is not None:
                on_tool_exchange(assistant_content, tool_results, meta)

        return "Не удалось получить ответ — превышен лимит вызовов инструментов."

    @staticmethod
    def _extract_response_meta(response: Any) -> dict[str, Any]:
        usage = getattr(response, "usage", None)
        return {
            "model": getattr(response, "model", None),
            "stop_reason": getattr(response, "stop_reason", None),
            "request_id": getattr(response, "id", None),
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "cache_creation_input_tokens": getattr(
                usage, "cache_creation_input_tokens", None
            ),
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", None),
        }

    @staticmethod
    def _extract_final_text(
        content: list,
        on_tool_exchange: (
            Callable[[list, list[dict[str, Any]] | None, dict[str, Any]], None] | None
        ),
        meta: dict[str, Any],
    ) -> str:
        text_blocks = [b.text for b in content if b.type == "text"]
        if on_tool_exchange is not None:
            on_tool_exchange(content, None, meta)
        return "\n".join(text_blocks)

    @staticmethod
    def _execute_tool_calls(user_id: int, content: list) -> list[dict[str, Any]]:
        tool_results: list[dict[str, Any]] = []
        for block in content:
            if block.type == "tool_use":
                logger.info("tool_call", tool=block.name, input=block.input)
                result = execute_tool(user_id, block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": (
                            _serialize_context(result)
                            if isinstance(result, (dict, list))
                            else json.dumps(result)
                        ),
                    }
                )
        return tool_results

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
        return self._run_tool_loop(user_id, messages, SYSTEM_PROMPT)

    def chat(self, user_id: int, message: str, conversation: Conversation) -> str:
        if conversation.needs_context_refresh():
            context_summary = build_chat_context(user_id)
            conversation.add_user_message(f"[Health context update]\n{context_summary}")
            conversation.add_assistant_message("Обновил данные. Что хочешь узнать?")
            conversation.mark_context_refreshed()

        conversation.add_user_message(message)
        messages = conversation.get_messages()

        def _track_exchange(
            content: Any,
            tool_results: list[dict[str, Any]] | None,
            meta: dict[str, Any],
        ) -> None:
            if tool_results is not None:
                conversation.add_tool_exchange(content, tool_results, meta=meta)
            else:
                conversation.add_assistant_message(content, meta=meta)

        return self._run_tool_loop(
            user_id,
            messages,
            SYSTEM_PROMPT + CHAT_ADDENDUM,
            on_tool_exchange=_track_exchange,
        )

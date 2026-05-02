from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from agent.bot_message_repo import (
    load_recent_messages,
    save_message,
    soft_clear_chat,
)

MAX_HISTORY_MESSAGES = 20
CONTEXT_REFRESH_MINUTES = 30

logger = logging.getLogger(__name__)


@dataclass
class Conversation:
    user_id: int | None = None
    chat_id: int | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)
    last_context_at: datetime | None = None

    def add_user_message(
        self,
        content: Any,
        *,
        source: str = "chat",
        telegram_message_id: int | None = None,
    ) -> None:
        self.messages.append({"role": "user", "content": content})
        self._trim()
        self._persist(
            "user",
            content,
            source=source,
            telegram_message_id=telegram_message_id,
        )

    def add_assistant_message(
        self,
        content: Any,
        *,
        source: str = "chat",
        telegram_message_id: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        self.messages.append({"role": "assistant", "content": content})
        self._trim()
        self._persist(
            "assistant",
            content,
            source=source,
            telegram_message_id=telegram_message_id,
            **(meta or {}),
        )

    def add_tool_exchange(
        self,
        assistant_content: Any,
        tool_results: list[dict[str, Any]],
        *,
        meta: dict[str, Any] | None = None,
    ) -> None:
        self.messages.append({"role": "assistant", "content": assistant_content})
        self.messages.append({"role": "user", "content": tool_results})
        self._persist("assistant", assistant_content, **(meta or {}))
        self._persist("user", tool_results)

    def needs_context_refresh(self) -> bool:
        if self.last_context_at is None:
            return True
        elapsed = (datetime.now() - self.last_context_at).total_seconds()
        return elapsed > CONTEXT_REFRESH_MINUTES * 60

    def mark_context_refreshed(self) -> None:
        self.last_context_at = datetime.now()

    def get_messages(self) -> list[dict[str, Any]]:
        return list(self.messages)

    def clear(self) -> None:
        self.messages.clear()
        self.last_context_at = None
        if self.user_id is not None and self.chat_id is not None:
            try:
                soft_clear_chat(self.user_id, self.chat_id)
            except Exception:
                logger.exception(
                    "soft_clear_chat_failed user_id=%s chat_id=%s",
                    self.user_id,
                    self.chat_id,
                )

    def _persist(self, role: str, content: Any, **kwargs: Any) -> None:
        if self.user_id is None or self.chat_id is None:
            return
        save_message(self.user_id, self.chat_id, role, content, **kwargs)

    def _trim(self) -> None:
        max_items = MAX_HISTORY_MESSAGES * 2
        if len(self.messages) <= max_items:
            return

        target_start = len(self.messages) - max_items
        safe_cuts = [
            i
            for i, msg in enumerate(self.messages)
            if msg["role"] == "user" and isinstance(msg["content"], str)
        ]

        cut_index = target_start
        for idx in safe_cuts:
            if idx >= target_start:
                cut_index = idx
                break

        self.messages = self.messages[cut_index:]


class ConversationStore:
    def __init__(self) -> None:
        self._conversations: dict[int, Conversation] = {}

    def get(self, chat_id: int, user_id: int | None = None) -> Conversation:
        if chat_id not in self._conversations:
            conv = Conversation(user_id=user_id, chat_id=chat_id)
            if user_id is not None:
                try:
                    conv.messages = load_recent_messages(
                        user_id, chat_id, MAX_HISTORY_MESSAGES * 2
                    )
                except Exception:
                    logger.exception(
                        "load_recent_messages_failed user_id=%s chat_id=%s",
                        user_id,
                        chat_id,
                    )
            self._conversations[chat_id] = conv
        return self._conversations[chat_id]

    def clear(self, chat_id: int) -> None:
        if chat_id in self._conversations:
            self._conversations[chat_id].clear()

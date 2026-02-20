from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

MAX_HISTORY_MESSAGES = 20
CONTEXT_REFRESH_MINUTES = 30


@dataclass
class Conversation:
    messages: list[dict[str, Any]] = field(default_factory=list)
    last_context_at: datetime | None = None

    def add_user_message(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})
        self._trim()

    def add_assistant_message(self, content: Any) -> None:
        self.messages.append({"role": "assistant", "content": content})
        self._trim()

    def add_tool_exchange(
        self, assistant_content: Any, tool_results: list[dict[str, Any]]
    ) -> None:
        self.messages.append({"role": "assistant", "content": assistant_content})
        self.messages.append({"role": "user", "content": tool_results})

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

    def get(self, chat_id: int) -> Conversation:
        if chat_id not in self._conversations:
            self._conversations[chat_id] = Conversation()
        return self._conversations[chat_id]

    def clear(self, chat_id: int) -> None:
        if chat_id in self._conversations:
            self._conversations[chat_id].clear()

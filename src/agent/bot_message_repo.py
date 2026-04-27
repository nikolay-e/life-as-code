from __future__ import annotations

import logging
from typing import Any

from database import get_db_session_context
from date_utils import utcnow
from models import BotMessage

logger = logging.getLogger(__name__)


def _serialize_block(block: Any) -> Any:
    if isinstance(block, dict):
        return block
    if hasattr(block, "model_dump"):
        return block.model_dump(mode="json", exclude_none=True)
    return str(block)


def serialize_content(content: Any) -> Any:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return [_serialize_block(b) for b in content]
    return str(content)


def _flatten_dict_block(block: dict[str, Any]) -> str | None:
    block_type = block.get("type")
    if block_type == "text":
        text = block.get("text")
        return text or None
    if block_type == "tool_use":
        return f"[tool_use:{block.get('name', '?')}]"
    if block_type == "tool_result":
        inner = block.get("content")
        if isinstance(inner, str):
            return f"[tool_result] {inner[:200]}"
        return "[tool_result]"
    return None


def _flatten_object_block(block: Any) -> str | None:
    block_type = getattr(block, "type", None)
    if block_type == "text":
        return getattr(block, "text", None) or None
    if block_type == "tool_use":
        return f"[tool_use:{getattr(block, 'name', '?')}]"
    return None


def _flatten_block(block: Any) -> str | None:
    if isinstance(block, dict):
        return _flatten_dict_block(block)
    return _flatten_object_block(block)


def flatten_text(content: Any) -> str | None:
    if isinstance(content, str):
        return content or None
    if not isinstance(content, list):
        return None
    parts = [text for block in content if (text := _flatten_block(block))]
    return "\n".join(parts) if parts else None


def save_message(
    user_id: int,
    chat_id: int,
    role: str,
    content: Any,
    *,
    source: str = "chat",
    telegram_message_id: int | None = None,
    model: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cache_creation_input_tokens: int | None = None,
    cache_read_input_tokens: int | None = None,
    stop_reason: str | None = None,
    request_id: str | None = None,
) -> int | None:
    try:
        with get_db_session_context() as db:
            msg = BotMessage(
                user_id=user_id,
                chat_id=chat_id,
                role=role,
                content=serialize_content(content),
                text_preview=flatten_text(content),
                source=source,
                telegram_message_id=telegram_message_id,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_creation_input_tokens=cache_creation_input_tokens,
                cache_read_input_tokens=cache_read_input_tokens,
                stop_reason=stop_reason,
                request_id=request_id,
            )
            db.add(msg)
            db.flush()
            return msg.id  # type: ignore[no-any-return]
    except Exception:
        logger.exception(
            "save_bot_message_failed user_id=%s chat_id=%s role=%s source=%s",
            user_id,
            chat_id,
            role,
            source,
        )
        return None


def _is_replayable(role: str, content: Any) -> bool:
    if role not in ("user", "assistant"):
        return False
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        if role == "user":
            return False
        return all(isinstance(b, dict) and b.get("type") == "text" for b in content)
    return False


def load_recent_messages(
    user_id: int, chat_id: int, limit: int = 40
) -> list[dict[str, Any]]:
    with get_db_session_context() as db:
        rows = (
            db.query(BotMessage.role, BotMessage.content)
            .filter(
                BotMessage.user_id == user_id,
                BotMessage.chat_id == chat_id,
                BotMessage.cleared_at.is_(None),
                BotMessage.source == "chat",
            )
            .order_by(BotMessage.created_at.desc())
            .limit(limit * 2)
            .all()
        )
    rows = list(reversed(rows))
    replayable = [
        {"role": role, "content": content}
        for role, content in rows
        if _is_replayable(role, content)
    ]
    if len(replayable) > limit:
        replayable = replayable[-limit:]
    return replayable


def soft_clear_chat(user_id: int, chat_id: int) -> int:
    now = utcnow()
    with get_db_session_context() as db:
        rowcount: int = (
            db.query(BotMessage)
            .filter(
                BotMessage.user_id == user_id,
                BotMessage.chat_id == chat_id,
                BotMessage.cleared_at.is_(None),
            )
            .update({"cleared_at": now}, synchronize_session=False)
        )
        return rowcount

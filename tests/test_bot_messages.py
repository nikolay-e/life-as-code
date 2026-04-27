# pyright: reportGeneralTypeIssues=false, reportArgumentType=false
import os
import sys
from typing import cast

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent.bot_message_repo import (
    flatten_text,
    load_recent_messages,
    save_message,
    serialize_content,
    soft_clear_chat,
)
from agent.conversation import ConversationStore
from database import get_db_session_context
from models import BotMessage, User
from security import get_password_hash


@pytest.fixture
def bot_user(db_engine):
    with get_db_session_context() as db:
        user = User(
            username="bot-msg-test@example.com",
            password_hash=get_password_hash("test-pass-123"),
        )
        db.add(user)
        db.flush()
        user_id = cast(int, user.id)
    yield user_id
    with get_db_session_context() as db:
        db.query(BotMessage).filter(BotMessage.user_id == user_id).delete()
        db.query(User).filter(User.id == user_id).delete()


class TestSerialization:
    def test_serialize_string_content(self):
        assert serialize_content("hello") == "hello"

    def test_serialize_dict_blocks(self):
        blocks = [
            {"type": "text", "text": "hi"},
            {"type": "tool_use", "id": "t1", "name": "q", "input": {}},
        ]
        assert serialize_content(blocks) == blocks

    def test_serialize_object_with_model_dump(self):
        class FakeBlock:
            def model_dump(self, mode="json", exclude_none=True):
                return {"type": "text", "text": "from sdk"}

        result = serialize_content([FakeBlock()])
        assert result == [{"type": "text", "text": "from sdk"}]

    def test_flatten_text_string(self):
        assert flatten_text("plain text") == "plain text"

    def test_flatten_text_blocks(self):
        blocks = [
            {"type": "text", "text": "first"},
            {"type": "tool_use", "name": "query_health", "id": "t1", "input": {}},
            {"type": "text", "text": "second"},
        ]
        result = flatten_text(blocks)
        assert result is not None
        assert "first" in result
        assert "second" in result
        assert "tool_use:query_health" in result

    def test_flatten_text_returns_none_for_empty(self):
        assert flatten_text([]) is None
        assert flatten_text("") is None


class TestSaveAndLoad:
    def test_save_user_message(self, bot_user):
        chat_id = 10_001
        msg_id = save_message(
            bot_user,
            chat_id,
            "user",
            "Привет, как мой сон?",
            telegram_message_id=42,
        )
        assert msg_id is not None

        history = load_recent_messages(bot_user, chat_id)
        assert len(history) == 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Привет, как мой сон?"

    def test_save_assistant_message_with_token_usage(self, bot_user):
        chat_id = 10_002
        save_message(
            bot_user,
            chat_id,
            "assistant",
            "Сон в порядке.",
            model="claude-opus-4-7",
            input_tokens=100,
            output_tokens=20,
            cache_creation_input_tokens=50,
            cache_read_input_tokens=10,
            stop_reason="end_turn",
            request_id="msg_abc123",
        )
        with get_db_session_context() as db:
            row = (
                db.query(BotMessage)
                .filter(
                    BotMessage.user_id == bot_user,
                    BotMessage.chat_id == chat_id,
                )
                .one()
            )
            assert row.role == "assistant"
            assert row.model == "claude-opus-4-7"
            assert row.input_tokens == 100
            assert row.output_tokens == 20
            assert row.cache_creation_input_tokens == 50
            assert row.cache_read_input_tokens == 10
            assert row.stop_reason == "end_turn"
            assert row.request_id == "msg_abc123"

    def test_save_assistant_with_content_blocks(self, bot_user):
        chat_id = 10_003
        blocks = [
            {"type": "text", "text": "Сейчас посмотрю."},
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "query_health",
                "input": {"days": 7},
            },
        ]
        save_message(bot_user, chat_id, "assistant", blocks)
        with get_db_session_context() as db:
            row = (
                db.query(BotMessage)
                .filter(
                    BotMessage.user_id == bot_user,
                    BotMessage.chat_id == chat_id,
                )
                .one()
            )
            assert isinstance(row.content, list)
            assert row.content[0]["type"] == "text"
            assert row.content[1]["type"] == "tool_use"
            assert "Сейчас посмотрю" in row.text_preview
            assert "tool_use:query_health" in row.text_preview

    def test_load_filters_tool_exchanges(self, bot_user):
        chat_id = 10_004
        save_message(bot_user, chat_id, "user", "Покажи сон")
        save_message(
            bot_user,
            chat_id,
            "assistant",
            [{"type": "tool_use", "id": "t1", "name": "q", "input": {}}],
        )
        save_message(
            bot_user,
            chat_id,
            "user",
            [{"type": "tool_result", "tool_use_id": "t1", "content": "data"}],
        )
        save_message(bot_user, chat_id, "assistant", "Сон отличный")

        history = load_recent_messages(bot_user, chat_id)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Покажи сон"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Сон отличный"

    def test_load_filters_non_chat_source(self, bot_user):
        chat_id = 10_005
        save_message(bot_user, chat_id, "user", "chat msg", source="chat")
        save_message(
            bot_user, chat_id, "assistant", "briefing", source="daily_briefing_push"
        )
        history = load_recent_messages(bot_user, chat_id)
        assert len(history) == 1
        assert history[0]["content"] == "chat msg"


class TestSoftClear:
    def test_soft_clear_chat(self, bot_user):
        chat_id = 10_010
        save_message(bot_user, chat_id, "user", "first")
        save_message(bot_user, chat_id, "assistant", "reply")

        cleared = soft_clear_chat(bot_user, chat_id)
        assert cleared == 2

        history = load_recent_messages(bot_user, chat_id)
        assert history == []

        with get_db_session_context() as db:
            total = (
                db.query(BotMessage)
                .filter(
                    BotMessage.user_id == bot_user,
                    BotMessage.chat_id == chat_id,
                )
                .count()
            )
            assert total == 2

    def test_clear_isolates_to_chat(self, bot_user):
        save_message(bot_user, 10_020, "user", "chat A msg")
        save_message(bot_user, 10_021, "user", "chat B msg")

        soft_clear_chat(bot_user, 10_020)

        assert load_recent_messages(bot_user, 10_020) == []
        assert len(load_recent_messages(bot_user, 10_021)) == 1


class TestConversationStore:
    def test_hydrate_from_db_on_first_get(self, bot_user):
        chat_id = 20_001
        save_message(bot_user, chat_id, "user", "before restart")
        save_message(bot_user, chat_id, "assistant", "indeed")

        store = ConversationStore()
        conv = store.get(chat_id, user_id=bot_user)

        assert len(conv.messages) == 2
        assert conv.messages[0]["role"] == "user"
        assert conv.messages[0]["content"] == "before restart"
        assert conv.messages[1]["role"] == "assistant"
        assert conv.messages[1]["content"] == "indeed"

    def test_add_message_persists_to_db(self, bot_user):
        chat_id = 20_002
        store = ConversationStore()
        conv = store.get(chat_id, user_id=bot_user)
        conv.add_user_message("hello")
        conv.add_assistant_message("hi there")

        store2 = ConversationStore()
        conv2 = store2.get(chat_id, user_id=bot_user)
        assert len(conv2.messages) == 2
        assert conv2.messages[0]["content"] == "hello"
        assert conv2.messages[1]["content"] == "hi there"

    def test_clear_soft_deletes_history(self, bot_user):
        chat_id = 20_003
        store = ConversationStore()
        conv = store.get(chat_id, user_id=bot_user)
        conv.add_user_message("question")

        store.clear(chat_id)

        store2 = ConversationStore()
        conv2 = store2.get(chat_id, user_id=bot_user)
        assert conv2.messages == []

    def test_no_persistence_when_user_id_missing(self):
        store = ConversationStore()
        conv = store.get(99_999)
        conv.add_user_message("ephemeral")
        assert len(conv.messages) == 1

    def test_assistant_meta_persisted(self, bot_user):
        chat_id = 20_004
        store = ConversationStore()
        conv = store.get(chat_id, user_id=bot_user)
        conv.add_assistant_message(
            "answer",
            meta={
                "model": "claude-opus-4-7",
                "input_tokens": 200,
                "output_tokens": 50,
                "stop_reason": "end_turn",
                "request_id": "msg_xyz",
                "cache_creation_input_tokens": None,
                "cache_read_input_tokens": None,
            },
        )

        with get_db_session_context() as db:
            row = (
                db.query(BotMessage)
                .filter(
                    BotMessage.user_id == bot_user,
                    BotMessage.chat_id == chat_id,
                    BotMessage.role == "assistant",
                )
                .one()
            )
            assert row.model == "claude-opus-4-7"
            assert row.input_tokens == 200
            assert row.output_tokens == 50
            assert row.request_id == "msg_xyz"


class TestBotMessageModel:
    def test_cascade_delete_via_orm(self, db_session):
        user = User(
            username="bot-cascade-test@example.com",
            password_hash=get_password_hash("pass"),
        )
        db_session.add(user)
        db_session.commit()

        msg = BotMessage(
            user_id=user.id,
            chat_id=999,
            role="user",
            content="hello",
            source="chat",
        )
        db_session.add(msg)
        db_session.commit()
        uid = user.id

        db_session.delete(user)
        db_session.commit()

        remaining = db_session.query(BotMessage).filter_by(user_id=uid).all()
        assert remaining == []

    def test_role_check_constraint(self, db_session):
        from sqlalchemy.exc import IntegrityError

        user = User(
            username="bot-role-test@example.com",
            password_hash=get_password_hash("pass"),
        )
        db_session.add(user)
        db_session.commit()

        msg = BotMessage(
            user_id=user.id,
            chat_id=1,
            role="invalid_role",
            content="x",
        )
        db_session.add(msg)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

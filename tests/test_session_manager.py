"""
Unit tests for session_manager.py
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from session_manager import SessionManager, MAX_HISTORY_LENGTH


@pytest.fixture()
def sm(tmp_path):
    """SessionManager backed by a temp file."""
    return SessionManager(path=str(tmp_path / "TEST_SESSIONS.json"))


class TestSessionCreation:
    def test_creates_new_session(self, sm):
        sid = sm.get_or_create_session("user1", "telegram")
        assert sid == "telegram:user1"

    def test_same_session_returned_on_repeat(self, sm):
        sid1 = sm.get_or_create_session("u", "ch")
        sid2 = sm.get_or_create_session("u", "ch")
        assert sid1 == sid2

    def test_different_channels_are_separate(self, sm):
        s1 = sm.get_or_create_session("99", "telegram")
        s2 = sm.get_or_create_session("99", "discord")
        assert s1 != s2


class TestHistoryManagement:
    def test_add_and_retrieve_message(self, sm):
        sid = sm.get_or_create_session("u1", "ch")
        sm.add_message(sid, {"role": "user", "content": "Hello!"})
        history = sm.get_history(sid)
        assert len(history) == 1
        assert history[0]["content"] == "Hello!"

    def test_empty_history_for_new_session(self, sm):
        sid = sm.get_or_create_session("new_user", "ch")
        assert sm.get_history(sid) == []

    def test_history_for_unknown_session_is_empty(self, sm):
        assert sm.get_history("fake:session") == []

    def test_history_pruned_at_max_length(self, sm):
        sid = sm.get_or_create_session("heavy_user", "ch")
        for i in range(MAX_HISTORY_LENGTH + 20):
            sm.add_message(sid, {"role": "user", "content": str(i)})
        history = sm.get_history(sid)
        assert len(history) == MAX_HISTORY_LENGTH
        # Should keep the most recent messages
        assert history[-1]["content"] == str(MAX_HISTORY_LENGTH + 19)

    def test_clear_history(self, sm):
        sid = sm.get_or_create_session("u", "ch")
        sm.add_message(sid, {"role": "user", "content": "old"})
        result = sm.clear_history(sid)
        assert result is True
        assert sm.get_history(sid) == []

    def test_clear_history_on_unknown_session_returns_false(self, sm):
        assert sm.clear_history("ghost:session") is False


class TestSessionInfo:
    def test_info_contains_message_count(self, sm):
        sid = sm.get_or_create_session("u", "ch")
        sm.add_message(sid, {"role": "user", "content": "hi"})
        info = sm.session_info(sid)
        assert info["message_count"] == 1
        assert info["channel"] == "ch"
        assert info["client_id"] == "u"

    def test_info_for_unknown_session_is_none(self, sm):
        assert sm.session_info("nonexistent:id") is None


class TestPersistence:
    def test_sessions_survive_restart(self, tmp_path):
        path = str(tmp_path / "persist.json")
        sm1 = SessionManager(path=path)
        sid = sm1.get_or_create_session("abc", "telegram")
        sm1.add_message(sid, {"role": "user", "content": "remember me"})

        sm2 = SessionManager(path=path)
        history = sm2.get_history(sid)
        assert len(history) == 1
        assert history[0]["content"] == "remember me"
